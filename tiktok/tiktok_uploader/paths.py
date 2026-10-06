"""로컬 저장 경로. 브라우저 프로필과 디버그 덤프가 여기에 들어간다."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

APP_NAME = "tiktok-uploader"


def app_dir() -> Path:
    """앱 전용 디렉터리. 소유자만 읽을 수 있게 만든다."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:  # 개발용 폴백
        xdg = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg) / APP_NAME if xdg else Path.home() / ".local" / "share" / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    return base


def _safe(name: str) -> str:
    """채널명을 디렉터리 이름으로 쓸 수 있게 다듬는다. 한글은 그대로 둔다."""
    cleaned = "".join(c for c in name if c not in '/\\:\0').strip()
    return cleaned or "unnamed"


def profile_dir(channel: str) -> Path:
    """채널별 브라우저 프로필. 로그인 세션이 여기에 남는다."""
    path = app_dir() / "profiles" / _safe(channel)
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def debug_dir(channel: str) -> Path:
    """실패 시 스크린샷과 HTML을 남기는 곳."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = app_dir() / "debug" / f"{_safe(channel)}-{stamp}"
    path.mkdir(parents=True, exist_ok=True)
    return path
