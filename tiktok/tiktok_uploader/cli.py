"""명령줄 인터페이스."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import doctor
from .config import PRIVACY_VALUES, get_channel, load_channels
from .errors import UploaderError
from .paths import profile_dir
from .session import interactive_login
from .upload import PostRequest, post_video


def _parse_when(text: str) -> datetime:
    """'2026-10-10 19:00' 또는 ISO 형식을 받는다."""
    try:
        return datetime.fromisoformat(text.strip().replace(" ", "T"))
    except ValueError as exc:
        raise UploaderError(
            f"예약 시각을 읽지 못했습니다: {text!r}\n"
            f"  'YYYY-MM-DD HH:MM' 형식으로 적어 주세요. 예: 2026-10-10 19:00"
        ) from exc


def _read_caption(args: argparse.Namespace) -> str:
    if args.caption_file:
        path = Path(args.caption_file).expanduser()
        if not path.exists():
            raise UploaderError(f"캡션 파일이 없습니다: {path}")
        return path.read_text(encoding="utf-8").strip()
    return (args.caption or "").strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tiktok-upload",
        description="채널별 TikTok 업로더 (TikTok Studio 웹 자동화)",
    )
    parser.add_argument("--config", help="channels.toml 경로")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("channels", help="등록된 채널 목록")

    p_login = sub.add_parser("login", help="채널에 로그인 (브라우저가 열립니다)")
    p_login.add_argument("--channel", required=True)

    p_doctor = sub.add_parser("doctor", help="셀렉터가 아직 맞는지 점검")
    p_doctor.add_argument("--channel", required=True)
    p_doctor.add_argument("--video", help="붙여서 점검할 영상 (게시하지 않음)")
    p_doctor.add_argument("--headless", action="store_true")

    p_post = sub.add_parser("post", help="영상 업로드")
    p_post.add_argument("--channel", required=True)
    p_post.add_argument("--video", required=True)
    p_post.add_argument("--caption", help="캡션. 해시태그를 그대로 포함하면 됩니다")
    p_post.add_argument("--caption-file", help="캡션을 파일에서 읽기")
    p_post.add_argument("--schedule", help="예약 시각. 'YYYY-MM-DD HH:MM', 최대 10일 뒤")
    p_post.add_argument("--privacy", choices=PRIVACY_VALUES, help="기본값은 채널 설정")
    p_post.add_argument("--no-comment", action="store_true", help="댓글 비허용")
    p_post.add_argument("--no-duet", action="store_true", help="듀엣 비허용")
    p_post.add_argument("--no-stitch", action="store_true", help="이어찍기 비허용")
    p_post.add_argument("--headless", action="store_true", help="창 없이 실행 (막힐 수 있음)")
    p_post.add_argument("--slow-mo", type=int, default=0, help="동작 사이 지연(ms)")
    p_post.add_argument(
        "--dry-run", action="store_true", help="게시 버튼만 누르지 않고 전부 진행"
    )
    p_post.add_argument(
        "--keep-open", action="store_true", help="dry-run 후 브라우저를 열어 둠"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "channels":
            channels = load_channels(args.config)
            for channel in channels.values():
                print(f"{channel.name}")
                print(f"  기본 공개 범위: {channel.default_privacy}")
                print(f"  프로필: {profile_dir(channel.name)}")
            return 0

        if args.command == "login":
            get_channel(args.channel, args.config)  # 등록된 채널인지 먼저 확인
            return 0 if interactive_login(args.channel) else 1

        if args.command == "doctor":
            get_channel(args.channel, args.config)
            video = Path(args.video).expanduser() if args.video else None
            if video is not None and not video.exists():
                raise UploaderError(f"영상 파일이 없습니다: {video}")
            return doctor.run(args.channel, video=video, headless=args.headless)

        if args.command == "post":
            channel = get_channel(args.channel, args.config)
            caption = _read_caption(args)
            if not caption:
                raise UploaderError("캡션이 비어 있습니다. --caption 또는 --caption-file 을 주세요.")

            request = PostRequest(
                channel=channel,
                video=Path(args.video).expanduser(),
                caption=caption,
                schedule_at=_parse_when(args.schedule) if args.schedule else None,
                privacy=args.privacy,
                allow_comment=False if args.no_comment else None,
                allow_duet=False if args.no_duet else None,
                allow_stitch=False if args.no_stitch else None,
                dry_run=args.dry_run,
            )
            print(
                post_video(
                    request,
                    headless=args.headless,
                    slow_mo=args.slow_mo,
                    keep_open=args.keep_open,
                )
            )
            return 0

    except UploaderError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n중단했습니다.", file=sys.stderr)
        return 130

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
