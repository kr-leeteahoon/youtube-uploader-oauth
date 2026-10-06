"""TikTok Studio 업로드 플로우."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, Locator, Page

from . import selectors as sel
from .browser import (
    Scope,
    dump_debug,
    first_present,
    first_visible,
    open_channel,
    require,
    resolve_scope,
    write_note,
)
from .config import Channel
from .errors import NotLoggedIn, UploadFailed
from .session import is_logged_in

# TikTok Studio 의 예약 가능 범위. 너무 가까우면 거부당하므로 여유를 둔다.
MIN_SCHEDULE_AHEAD = timedelta(minutes=20)
MAX_SCHEDULE_AHEAD = timedelta(days=10)

# 영상 전송이 끝나기를 기다리는 시간. 길이와 회선에 따라 오래 걸린다.
UPLOAD_TIMEOUT_MS = 15 * 60 * 1000


@dataclass
class PostRequest:
    channel: Channel
    video: Path
    caption: str
    schedule_at: datetime | None = None
    privacy: str | None = None
    allow_comment: bool | None = None
    allow_duet: bool | None = None
    allow_stitch: bool | None = None
    dry_run: bool = False

    def resolved_privacy(self) -> str:
        return self.privacy or self.channel.default_privacy

    def resolved_toggles(self) -> dict[str, bool]:
        return {
            "comment": self.channel.allow_comment if self.allow_comment is None else self.allow_comment,
            "duet": self.channel.allow_duet if self.allow_duet is None else self.allow_duet,
            "stitch": self.channel.allow_stitch if self.allow_stitch is None else self.allow_stitch,
        }


def validate_schedule(when: datetime | None, *, now: datetime | None = None) -> None:
    """예약 시각이 TikTok 이 받아주는 범위인지 미리 거른다."""
    if when is None:
        return
    now = now or datetime.now()
    delta = when - now
    if delta < MIN_SCHEDULE_AHEAD:
        raise UploadFailed(
            f"예약 시각이 너무 가깝습니다: {when:%Y-%m-%d %H:%M}\n"
            f"  지금부터 최소 {int(MIN_SCHEDULE_AHEAD.total_seconds() // 60)}분 뒤여야 합니다."
        )
    if delta > MAX_SCHEDULE_AHEAD:
        raise UploadFailed(
            f"예약 시각이 너무 멉니다: {when:%Y-%m-%d %H:%M}\n"
            f"  TikTok 은 최대 {MAX_SCHEDULE_AHEAD.days}일 뒤까지만 예약할 수 있습니다."
        )


def post_video(
    request: PostRequest,
    *,
    headless: bool = False,
    slow_mo: int = 0,
    keep_open: bool = False,
) -> str:
    """영상 하나를 올린다. 성공하면 사람이 읽을 결과 문자열을 돌려준다."""
    if not request.video.exists():
        raise UploadFailed(f"영상 파일이 없습니다: {request.video}")
    validate_schedule(request.schedule_at)

    name = request.channel.name
    with open_channel(name, headless=headless, slow_mo=slow_mo) as (_context, page):
        if not is_logged_in(page):
            raise NotLoggedIn(
                f"'{name}' 채널이 로그인되어 있지 않습니다.\n"
                f"  먼저 'tiktok-upload login --channel {name}' 을 실행하세요."
            )

        page.goto(sel.UPLOAD_URL, wait_until="domcontentloaded")
        scope = resolve_scope(page, sel.UPLOAD_IFRAME)

        _attach_video(scope, page, name, request.video)
        _wait_for_upload(scope, page, name)
        _set_caption(scope, page, name, request.caption)
        _set_privacy(scope, page, name, request.resolved_privacy())
        _set_interactions(scope, page, name, request.resolved_toggles())

        if request.schedule_at is not None:
            _set_schedule(scope, page, name, request.schedule_at)

        if request.dry_run:
            dump = dump_debug(page, name, "dry-run")
            write_note(dump, "request.txt", _describe(request))
            if keep_open:
                print("dry-run: 게시 버튼을 누르지 않았습니다. 브라우저를 확인하세요.")
                page.pause()
            return f"dry-run 완료. 게시하지 않았습니다. 확인용 덤프: {dump}"

        _click_post(scope, page, name)
        _wait_for_success(scope, page, name)

    when = (
        f"{request.schedule_at:%Y-%m-%d %H:%M} 예약"
        if request.schedule_at
        else "즉시 게시"
    )
    return f"'{name}' 에 업로드 완료 ({when})"


# --- 단계별 구현 ---------------------------------------------------------


def _attach_video(scope: Scope, page: Page, channel: str, video: Path) -> None:
    file_input = first_present(scope, sel.FILE_INPUT)
    if file_input is None:
        dump = dump_debug(page, channel, "file-input")
        raise UploadFailed(
            f"파일 입력 요소를 찾지 못했습니다. 업로드 페이지가 제대로 열리지 않은 것 같습니다.\n"
            f"  디버그 덤프: {dump}"
        )
    file_input.set_input_files(str(video))


def _wait_for_upload(scope: Scope, page: Page, channel: str) -> None:
    """전송이 끝나 편집 UI가 뜰 때까지 기다린다."""
    marker = first_visible(scope, sel.UPLOAD_COMPLETE_MARKER, timeout=60_000)
    if marker is None:
        # 미리보기 마커를 못 찾아도 캡션 편집기가 뜨면 전송은 받아들여진 것이다.
        marker = first_visible(scope, sel.CAPTION_EDITOR, timeout=30_000)
    if marker is None:
        dump = dump_debug(page, channel, "upload-wait")
        raise UploadFailed(f"업로드가 시작되지 않았습니다. 디버그 덤프: {dump}")

    # 진행 표시가 남아 있으면 사라질 때까지 기다린다.
    progress = first_visible(scope, sel.UPLOAD_PROGRESS_MARKER, timeout=2_000)
    if progress is not None:
        try:
            progress.wait_for(state="hidden", timeout=UPLOAD_TIMEOUT_MS)
        except PlaywrightError as exc:
            dump = dump_debug(page, channel, "upload-stuck")
            raise UploadFailed(
                f"업로드가 제한 시간 안에 끝나지 않았습니다. 디버그 덤프: {dump}"
            ) from exc


def _set_caption(scope: Scope, page: Page, channel: str, caption: str) -> None:
    """DraftJS 편집기에 캡션을 넣는다.

    해시태그를 치면 자동완성 팝업이 떠서 다음 입력을 삼키므로, 태그마다
    Escape 로 팝업을 닫고 넘어간다.
    """
    editor = require(
        scope, sel.CAPTION_EDITOR, "캡션 편집기", page=page, channel=channel, timeout=30_000
    )
    editor.click()

    # 파일명이 기본으로 채워져 있다. 지우고 시작한다.
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.press("Delete")

    tokens = caption.split(" ")
    for index, token in enumerate(tokens):
        if token:
            editor.type(token, delay=25)
            if token.startswith(("#", "@")):
                page.wait_for_timeout(500)
                page.keyboard.press("Escape")
        if index != len(tokens) - 1:
            editor.type(" ")


def _set_privacy(scope: Scope, page: Page, channel: str, privacy: str) -> None:
    dropdown = first_visible(scope, sel.PRIVACY_DROPDOWN, timeout=5_000)
    if dropdown is None:
        # 공개 범위 UI를 못 찾으면 기본값으로 올라간다. 조용히 넘어가지 않는다.
        dump = dump_debug(page, channel, "privacy-dropdown")
        raise UploadFailed(
            f"공개 범위 선택 UI를 찾지 못했습니다. 의도하지 않은 범위로 게시될 수 있어 중단합니다.\n"
            f"  디버그 덤프: {dump}"
        )

    dropdown.click()
    labels = sel.PRIVACY_OPTION[privacy]
    for label in labels:
        option = scope.get_by_text(label, exact=True).first
        try:
            option.wait_for(state="visible", timeout=2_000)
            option.click()
            return
        except PlaywrightError:
            continue

    dump = dump_debug(page, channel, "privacy-option")
    raise UploadFailed(
        f"공개 범위 '{privacy}' 항목을 고르지 못했습니다. 찾은 라벨 후보: {labels}\n"
        f"  디버그 덤프: {dump}"
    )


def _set_interactions(scope: Scope, page: Page, channel: str, desired: dict[str, bool]) -> None:
    for key, want in desired.items():
        toggle = first_visible(scope, sel.INTERACTION_TOGGLES[key], timeout=3_000)
        if toggle is None:
            # 듀엣·이어찍기는 영상 길이나 계정 설정에 따라 아예 안 뜰 수 있다.
            print(f"  경고: '{key}' 허용 설정을 찾지 못해 건너뜁니다.")
            continue
        _set_toggle(toggle, want)


def _set_toggle(locator: Locator, desired: bool) -> None:
    """체크박스든 커스텀 스위치든 원하는 상태로 맞춘다."""
    current: bool | None = None
    try:
        current = locator.is_checked()
    except PlaywrightError:
        aria = locator.get_attribute("aria-checked")
        if aria is not None:
            current = aria == "true"
    if current is None or current != desired:
        locator.click()


def _set_schedule(scope: Scope, page: Page, channel: str, when: datetime) -> None:
    switch = require(
        scope, sel.SCHEDULE_SWITCH, "예약 게시 스위치", page=page, channel=channel
    )
    _set_toggle(switch, True)

    date_input = require(
        scope, sel.SCHEDULE_DATE_INPUT, "예약 날짜 입력", page=page, channel=channel
    )
    _fill_or_pick(
        scope, page, channel, date_input, f"{when:%Y-%m-%d}", sel.SCHEDULE_DAY_CELL,
        {"day": str(when.day)}, "예약 날짜",
    )

    time_input = require(
        scope, sel.SCHEDULE_TIME_INPUT, "예약 시간 입력", page=page, channel=channel
    )
    _fill_or_pick(
        scope, page, channel, time_input, f"{when:%H:%M}", sel.SCHEDULE_HOUR_CELL,
        {"value": f"{when.hour:02d}"}, "예약 시각",
        follow_up=(sel.SCHEDULE_MINUTE_CELL, {"value": f"{when.minute:02d}"}),
    )

    _verify_schedule(scope, page, channel, when)


def _fill_or_pick(
    scope: Scope,
    page: Page,
    channel: str,
    field: Locator,
    text: str,
    cell_templates: list[str],
    substitutions: dict[str, str],
    what: str,
    *,
    follow_up: tuple[list[str], dict[str, str]] | None = None,
) -> None:
    """입력 칸에 직접 쓰고, 읽기 전용이면 피커에서 칸을 클릭한다."""
    try:
        field.fill(text)
        if (field.input_value() or "").strip():
            page.keyboard.press("Enter")
            return
    except PlaywrightError:
        pass  # 읽기 전용 입력. 아래 피커 경로로 간다.

    field.click()
    _click_cell(scope, page, channel, cell_templates, substitutions, what)
    if follow_up is not None:
        templates, subs = follow_up
        _click_cell(scope, page, channel, templates, subs, f"{what}(분)")


def _click_cell(
    scope: Scope,
    page: Page,
    channel: str,
    templates: list[str],
    substitutions: dict[str, str],
    what: str,
) -> None:
    candidates = [t.format(**substitutions) for t in templates]
    cell = first_visible(scope, candidates, timeout=6_000)
    if cell is None:
        dump = dump_debug(page, channel, f"schedule-{what}")
        raise UploadFailed(
            f"{what} 을(를) 피커에서 고르지 못했습니다.\n"
            f"  시도한 셀렉터: {candidates}\n"
            f"  selectors.py 의 예약 피커 항목을 고쳐야 합니다. 디버그 덤프: {dump}"
        )
    cell.click()


def _verify_schedule(scope: Scope, page: Page, channel: str, when: datetime) -> None:
    """예약 값이 실제로 반영됐는지 되읽어 확인한다.

    잘못된 시각으로 게시되는 것보다 여기서 멈추는 편이 낫다.
    """
    date_field = first_visible(scope, sel.SCHEDULE_DATE_INPUT, timeout=3_000)
    time_field = first_visible(scope, sel.SCHEDULE_TIME_INPUT, timeout=3_000)
    seen = []
    for field in (date_field, time_field):
        if field is None:
            continue
        try:
            seen.append((field.input_value() or "").strip())
        except PlaywrightError:
            seen.append((field.inner_text() or "").strip())

    blob = " ".join(seen)
    expected_day = f"{when.day}"
    expected_time = f"{when.hour:02d}:{when.minute:02d}"
    if expected_day in blob and expected_time in blob:
        return

    dump = dump_debug(page, channel, "schedule-verify")
    raise UploadFailed(
        f"예약 시각이 제대로 입력되지 않았습니다.\n"
        f"  원한 값: {when:%Y-%m-%d %H:%M}\n"
        f"  화면에서 읽은 값: {blob or '(비어 있음)'}\n"
        f"  잘못된 시각에 게시되는 것을 막기 위해 중단합니다. 디버그 덤프: {dump}"
    )


def _click_post(scope: Scope, page: Page, channel: str) -> None:
    button = require(scope, sel.POST_BUTTON, "게시 버튼", page=page, channel=channel)
    try:
        button.wait_for(state="visible", timeout=10_000)
        if button.is_disabled():
            page.wait_for_timeout(3_000)
    except PlaywrightError:
        pass
    button.click()


def _wait_for_success(scope: Scope, page: Page, channel: str) -> None:
    marker = first_visible(scope, sel.POST_SUCCESS_MARKER, timeout=60_000)
    if marker is None:
        # 성공 토스트를 놓쳤을 수 있다. 콘텐츠 목록으로 넘어갔는지 본다.
        try:
            page.wait_for_url("**/tiktokstudio/content**", timeout=15_000)
            return
        except PlaywrightError:
            pass
        dump = dump_debug(page, channel, "post-result")
        raise UploadFailed(
            f"게시 결과를 확인하지 못했습니다. 실제로 올라갔는지 TikTok 에서 직접 확인하세요.\n"
            f"  디버그 덤프: {dump}"
        )

    confirm = first_visible(scope, sel.POST_CONFIRM_BUTTON, timeout=3_000)
    if confirm is not None:
        confirm.click()


def _describe(request: PostRequest) -> str:
    toggles = request.resolved_toggles()
    lines = [
        f"channel: {request.channel.name}",
        f"video: {request.video}",
        f"caption: {request.caption}",
        f"privacy: {request.resolved_privacy()}",
        f"schedule: {request.schedule_at or '즉시'}",
        f"comment/duet/stitch: {toggles['comment']}/{toggles['duet']}/{toggles['stitch']}",
    ]
    return "\n".join(lines) + "\n"
