"""셀렉터 점검. 페이지가 바뀌어 업로드가 깨졌을 때 어디가 빗나갔는지 알려준다.

업로드는 하지 않는다. 업로드 페이지를 열어 각 셀렉터 그룹이 잡히는지만 본다.
영상을 붙이기 전에는 안 보이는 요소(캡션, 공개 범위, 예약)가 있으므로,
--video 를 주면 실제로 파일을 붙인 뒤 점검한다. 게시 버튼은 누르지 않는다.
"""

from __future__ import annotations

from pathlib import Path

from . import selectors as sel
from .browser import dump_debug, first_present, first_visible, open_channel, resolve_scope, write_note
from .session import is_logged_in

# (표시 이름, 후보 리스트, 영상이 붙은 뒤에만 보이는지)
PROBES: list[tuple[str, list[str], bool]] = [
    ("파일 입력", sel.FILE_INPUT, False),
    ("캡션 편집기", sel.CAPTION_EDITOR, True),
    ("공개 범위 드롭다운", sel.PRIVACY_DROPDOWN, True),
    ("댓글 허용", sel.INTERACTION_TOGGLES["comment"], True),
    ("듀엣 허용", sel.INTERACTION_TOGGLES["duet"], True),
    ("이어찍기 허용", sel.INTERACTION_TOGGLES["stitch"], True),
    ("예약 스위치", sel.SCHEDULE_SWITCH, True),
    ("예약 날짜 입력", sel.SCHEDULE_DATE_INPUT, True),
    ("예약 시간 입력", sel.SCHEDULE_TIME_INPUT, True),
    ("게시 버튼", sel.POST_BUTTON, True),
]


def run(channel: str, *, video: Path | None = None, headless: bool = False) -> int:
    """0 이면 전부 통과, 1 이면 빗나간 항목이 있음."""
    with open_channel(channel, headless=headless) as (_context, page):
        print(f"채널: {channel}")

        if not is_logged_in(page):
            print("  로그인: 안 됨 — 'tiktok-upload login' 을 먼저 실행하세요.")
            return 1
        print("  로그인: OK")

        page.goto(sel.UPLOAD_URL, wait_until="domcontentloaded")
        scope = resolve_scope(page, sel.UPLOAD_IFRAME)
        in_iframe = scope is not page
        print(f"  업로드 UI: {'iframe 안' if in_iframe else '메인 프레임'}")

        if video is not None:
            file_input = first_present(scope, sel.FILE_INPUT)
            if file_input is None:
                print("  파일 입력을 찾지 못해 더 진행할 수 없습니다.")
                print(f"  디버그 덤프: {dump_debug(page, channel, 'doctor-no-file-input')}")
                return 1
            file_input.set_input_files(str(video))
            print(f"  영상 첨부: {video.name}")
            first_visible(scope, sel.CAPTION_EDITOR, timeout=60_000)

        failures: list[str] = []
        report: list[str] = []
        for label, candidates, needs_video in PROBES:
            if needs_video and video is None:
                report.append(f"  {label}: 건너뜀 (--video 를 주면 점검합니다)")
                continue
            hit = first_visible(scope, candidates, timeout=5_000) or first_present(scope, candidates)
            if hit is None:
                failures.append(label)
                report.append(f"  {label}: 실패 — 후보 {len(candidates)}개 모두 빗나감")
            else:
                report.append(f"  {label}: OK")

        for line in report:
            print(line)

        dump = dump_debug(page, channel, "doctor")
        write_note(dump, "report.txt", "\n".join(report) + "\n")
        print(f"  덤프: {dump}")

        if failures:
            print(
                f"\n빗나간 항목: {', '.join(failures)}\n"
                f"위 덤프의 HTML 을 열어 실제 속성을 확인하고 selectors.py 에 후보를 추가하세요."
            )
            return 1

        print("\n전부 통과했습니다.")
        return 0
