"""Settings loaded from environment (.env is read by systemd or by python-dotenv locally)."""
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # dotenv is optional on the server, systemd passes the env
    pass

BASE_DIR = Path(__file__).resolve().parent.parent


def _ids(raw: str) -> frozenset[int]:
    return frozenset(int(x) for x in raw.replace(" ", "").split(",") if x)


@dataclass(frozen=True)
class Config:
    bot_token: str
    allowed_ids: frozenset[int]
    cookies_file: Path | None
    proxy: str | None
    work_dir: Path
    # Bot API upload limit is 50 MB; keep a margin for multipart overhead.
    max_upload_bytes: int = 48 * 1024 * 1024
    bitrate_kbps: int = 128
    min_bitrate_kbps: int = 48


def load() -> Config:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is not set")

    cookies = os.environ.get("YTDLP_COOKIES", "").strip()
    cookies_path = Path(cookies) if cookies else None
    if cookies_path and not cookies_path.is_absolute():
        cookies_path = BASE_DIR / cookies_path

    work_dir = BASE_DIR / "var" / "work"
    work_dir.mkdir(parents=True, exist_ok=True)

    return Config(
        bot_token=token,
        allowed_ids=_ids(os.environ.get("ALLOWED_IDS", "")),
        cookies_file=cookies_path if cookies_path and cookies_path.exists() else None,
        proxy=os.environ.get("YTDLP_PROXY", "").strip() or None,
        work_dir=work_dir,
        bitrate_kbps=int(os.environ.get("AUDIO_BITRATE_KBPS", "128")),
    )
