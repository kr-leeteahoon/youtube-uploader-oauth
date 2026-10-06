"""로그인 상태 확인과 최초 로그인.

비밀번호는 저장하지 않는다. 최초 1회 브라우저를 띄워 사람이 직접 로그인하고
(2단계 인증·캡차 포함), 그 결과로 생긴 세션이 채널 프로필에 남는다.
"""

from __future__ import annotations

import time

from playwright.sync_api import Error as PlaywrightError, Page

from . import selectors as sel
from .browser import first_visible, open_channel

LOGIN_POLL_SECONDS = 3
LOGIN_TIMEOUT_SECONDS = 300


def is_logged_in(page: Page, *, navigate: bool = True) -> bool:
    """스튜디오에 접근 가능한지로 로그인 여부를 판정한다."""
    if navigate:
        try:
            page.goto(sel.CONTENT_URL, wait_until="domcontentloaded")
        except PlaywrightError:
            return False

    # 로그인 화면으로 튕겼으면 끝.
    if "/login" in page.url:
        return False

    if first_visible(page, sel.LOGGED_IN_MARKER, timeout=8_000) is not None:
        return True
    if first_visible(page, sel.LOGGED_OUT_MARKER, timeout=2_000) is not None:
        return False

    # 마커가 둘 다 안 잡히면 URL 로 판단한다. 스튜디오 경로에 남아 있으면
    # 로그인된 것으로 본다.
    return "tiktokstudio" in page.url


def interactive_login(channel: str, *, timeout: int = LOGIN_TIMEOUT_SECONDS) -> bool:
    """브라우저를 띄워 사람이 로그인할 때까지 기다린다.

    로그인에 성공하면 True. 세션은 채널 프로필에 자동으로 남는다.
    """
    with open_channel(channel, headless=False) as (_context, page):
        if is_logged_in(page):
            print(f"'{channel}' 은(는) 이미 로그인되어 있습니다.")
            return True

        page.goto(sel.LOGIN_URL, wait_until="domcontentloaded")
        print(
            f"브라우저에서 '{channel}' 계정으로 로그인해 주세요.\n"
            f"  로그인이 끝나면 자동으로 감지합니다. (최대 {timeout}초 대기)\n"
            f"  창을 닫지 마세요."
        )

        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(LOGIN_POLL_SECONDS)
            try:
                if "/login" not in page.url and is_logged_in(page, navigate=False):
                    print(f"'{channel}' 로그인 완료. 세션을 저장했습니다.")
                    return True
            except PlaywrightError:
                # 사용자가 페이지를 이동하는 중일 수 있다. 다음 폴링에서 다시 본다.
                continue

        print(f"시간 안에 로그인이 확인되지 않았습니다. 다시 시도해 주세요.")
        return False
