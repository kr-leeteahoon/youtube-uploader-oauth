"""브라우저 기동과 셀렉터 탐색 헬퍼.

채널마다 별도의 영속 프로필을 쓴다. 쿠키를 주입하는 대신 실제 브라우저
프로필을 그대로 재사용하므로, 한 번 로그인해 두면 계속 로그인 상태가 유지되고
계정끼리 세션이 섞일 일이 없다.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Sequence
from pathlib import Path

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    FrameLocator,
    Locator,
    Page,
    sync_playwright,
)

from .errors import ElementNotFound
from .paths import debug_dir, profile_dir

# 자동화 티를 덜 내기 위한 최소한의 플래그. 우회 목적이 아니라,
# 기본값 그대로 두면 정상 동작조차 막히는 경우가 있어서 넣는다.
LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]

Scope = Page | FrameLocator


@contextlib.contextmanager
def open_channel(
    channel: str,
    *,
    headless: bool = False,
    slow_mo: int = 0,
) -> Iterator[tuple[BrowserContext, Page]]:
    """채널 프로필로 브라우저를 열고 (컨텍스트, 첫 페이지) 를 돌려준다."""
    user_data = profile_dir(channel)
    with sync_playwright() as pw:
        options = dict(
            user_data_dir=str(user_data),
            headless=headless,
            slow_mo=slow_mo,
            args=LAUNCH_ARGS,
            viewport={"width": 1440, "height": 960},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        # 설치된 실제 Chrome 이 번들 Chromium 보다 덜 막힌다.
        try:
            context = pw.chromium.launch_persistent_context(channel="chrome", **options)
        except PlaywrightError:
            context = pw.chromium.launch_persistent_context(**options)

        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(30_000)
            yield context, page
        finally:
            context.close()


def first_visible(
    scope: Scope,
    candidates: Sequence[str],
    *,
    timeout: int = 10_000,
) -> Locator | None:
    """후보 셀렉터를 순서대로 시도해서 처음 보이는 것을 돌려준다.

    전체 대기 시간이 timeout 을 넘지 않도록 후보 수로 나눠 쓴다.
    """
    per_try = max(timeout // max(len(candidates), 1), 500)
    for selector in candidates:
        locator = scope.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=per_try)
            return locator
        except PlaywrightError:
            continue
    return None


def first_present(scope: Scope, candidates: Sequence[str]) -> Locator | None:
    """보이지 않아도 되는 요소를 찾는다. 숨겨진 file input 용."""
    for selector in candidates:
        locator = scope.locator(selector).first
        try:
            if locator.count() > 0:
                return locator
        except PlaywrightError:
            continue
    return None


def require(
    scope: Scope,
    candidates: Sequence[str],
    what: str,
    *,
    page: Page | None = None,
    channel: str = "unknown",
    timeout: int = 10_000,
) -> Locator:
    """찾지 못하면 디버그 덤프를 남기고 ElementNotFound 를 던진다."""
    found = first_visible(scope, candidates, timeout=timeout)
    if found is not None:
        return found
    dump = dump_debug(page, channel, what) if page is not None else None
    raise ElementNotFound(what, list(candidates), dump)


def resolve_scope(page: Page, iframe_candidates: Sequence[str]) -> Scope:
    """업로드 UI가 iframe 안에 있으면 그 프레임을, 아니면 페이지를 돌려준다."""
    for selector in iframe_candidates:
        try:
            if page.locator(selector).count() > 0:
                return page.frame_locator(selector)
        except PlaywrightError:
            continue
    return page


def dump_debug(page: Page, channel: str, label: str) -> str:
    """스크린샷과 HTML을 남기고 디렉터리 경로를 돌려준다."""
    target = debug_dir(channel)
    safe_label = label.replace("/", "_").replace(" ", "_")
    try:
        page.screenshot(path=str(target / f"{safe_label}.png"), full_page=True)
    except PlaywrightError:
        pass
    try:
        (target / f"{safe_label}.html").write_text(page.content(), encoding="utf-8")
    except PlaywrightError:
        pass
    try:
        (target / "url.txt").write_text(page.url, encoding="utf-8")
    except PlaywrightError:
        pass
    return str(target)


def write_note(directory: str | Path, name: str, body: str) -> None:
    """덤프 디렉터리에 메모를 남긴다."""
    Path(directory).joinpath(name).write_text(body, encoding="utf-8")
