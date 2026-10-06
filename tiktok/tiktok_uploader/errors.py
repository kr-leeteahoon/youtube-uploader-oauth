"""이 도구가 던지는 예외. CLI는 이것만 잡아서 메시지를 보여준다."""

from __future__ import annotations


class UploaderError(Exception):
    """사용자에게 그대로 보여줄 수 있는 오류."""


class ConfigError(UploaderError):
    """channels.toml 이 없거나 값이 잘못됨."""


class NotLoggedIn(UploaderError):
    """채널 프로필에 유효한 로그인 세션이 없음."""


class ElementNotFound(UploaderError):
    """셀렉터가 전부 빗나감. 페이지 구조가 바뀌었을 가능성이 높다."""

    def __init__(self, what: str, candidates: list[str], dump: str | None = None):
        self.what = what
        self.candidates = candidates
        self.dump = dump
        tried = "\n".join(f"    - {c}" for c in candidates)
        message = (
            f"'{what}' 요소를 찾지 못했습니다. TikTok 페이지 구조가 바뀐 것 같습니다.\n"
            f"  시도한 셀렉터:\n{tried}\n"
            f"  selectors.py 의 해당 항목에 맞는 셀렉터를 추가하세요."
        )
        if dump:
            message += f"\n  디버그 덤프: {dump}"
        super().__init__(message)


class UploadFailed(UploaderError):
    """업로드 플로우가 중간에 실패함."""
