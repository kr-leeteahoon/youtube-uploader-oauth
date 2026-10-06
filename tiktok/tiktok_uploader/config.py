"""채널 레지스트리. 계정마다 분리된 설정을 담는다."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError
from .paths import app_dir

PRIVACY_VALUES = ("public", "friends", "private")


@dataclass(frozen=True)
class Channel:
    """채널 하나. 로그인 세션은 설정이 아니라 브라우저 프로필에 들어간다."""

    name: str
    default_privacy: str = "public"
    allow_comment: bool = True
    allow_duet: bool = True
    allow_stitch: bool = True


def config_path(explicit: str | None = None) -> Path:
    """설정 파일 위치. 명시값 > 현재 디렉터리 > 앱 디렉터리 순."""
    if explicit:
        return Path(explicit).expanduser()
    local = Path.cwd() / "channels.toml"
    if local.exists():
        return local
    return app_dir() / "channels.toml"


def load_channels(explicit: str | None = None) -> dict[str, Channel]:
    path = config_path(explicit)
    if not path.exists():
        raise ConfigError(
            f"설정 파일이 없습니다: {path}\n"
            f"  channels.toml.example 을 복사해서 채널을 적어 주세요."
        )

    try:
        with path.open("rb") as fp:
            raw = tomllib.load(fp)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} 를 읽지 못했습니다: {exc}") from exc

    section = raw.get("channels")
    if not isinstance(section, dict) or not section:
        raise ConfigError(f"{path} 에 [channels.<이름>] 항목이 하나도 없습니다.")

    channels: dict[str, Channel] = {}
    for name, body in section.items():
        if not isinstance(body, dict):
            raise ConfigError(f"[channels.{name}] 은 테이블이어야 합니다.")

        privacy = body.get("default_privacy", "public")
        if privacy not in PRIVACY_VALUES:
            raise ConfigError(
                f"[channels.{name}] default_privacy 가 '{privacy}' 입니다. "
                f"{', '.join(PRIVACY_VALUES)} 중 하나여야 합니다."
            )

        channels[name] = Channel(
            name=name,
            default_privacy=privacy,
            allow_comment=bool(body.get("allow_comment", True)),
            allow_duet=bool(body.get("allow_duet", True)),
            allow_stitch=bool(body.get("allow_stitch", True)),
        )
    return channels


def get_channel(name: str, explicit: str | None = None) -> Channel:
    channels = load_channels(explicit)
    if name not in channels:
        known = ", ".join(channels) or "(없음)"
        raise ConfigError(f"'{name}' 채널을 모릅니다. 등록된 채널: {known}")
    return channels[name]
