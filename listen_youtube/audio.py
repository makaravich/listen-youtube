"""Download the audio track of a YouTube video and fit it into Telegram's upload limit."""
from __future__ import annotations

import logging
import math
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yt_dlp

from .config import Config

log = logging.getLogger(__name__)

YOUTUBE_URL_RE = re.compile(
    r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be|youtube-nocookie\.com)/\S+",
    re.IGNORECASE,
)


class DownloadError(Exception):
    """User-facing failure; the message is shown in the chat."""


@dataclass
class AudioResult:
    title: str
    uploader: str
    duration: int
    url: str
    parts: list[Path] = field(default_factory=list)
    thumbnail: Path | None = None
    bitrate_kbps: int = 0


def find_url(text: str) -> str | None:
    m = YOUTUBE_URL_RE.search(text or "")
    return m.group(0) if m else None


def _ffmpeg(*args: str) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise DownloadError(f"ffmpeg error: {res.stderr.strip()[-300:]}")


def _ydl_opts(cfg: Config, out_dir: Path) -> dict:
    opts = {
        # m4a (itag 140, AAC) plays in Telegram's audio player without re-encoding.
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": str(out_dir / "source.%(ext)s"),
        "noplaylist": True,
        "writethumbnail": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 3,
        "socket_timeout": 30,
    }
    if cfg.cookies_file:
        opts["cookiefile"] = str(cfg.cookies_file)
    if cfg.proxy:
        opts["proxy"] = cfg.proxy
    return opts


def _make_thumbnail(out_dir: Path) -> Path | None:
    """Telegram wants JPEG, <=320px, <200 KB."""
    src = next((p for p in out_dir.glob("source.*") if p.suffix.lower() in {".jpg", ".jpeg", ".webp", ".png"}), None)
    if not src:
        return None
    dst = out_dir / "thumb.jpg"
    try:
        _ffmpeg("-i", str(src), "-vf", "scale=320:320:force_original_aspect_ratio=decrease", "-q:v", "5", str(dst))
    except DownloadError:
        return None
    return dst if dst.exists() and dst.stat().st_size < 200_000 else None


def download(cfg: Config, url: str, out_dir: Path) -> AudioResult:
    """Blocking: run it in a thread."""
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        with yt_dlp.YoutubeDL(_ydl_opts(cfg, out_dir)) as ydl:
            info = ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e)
        if "Sign in to confirm" in msg:
            raise DownloadError("YouTube требует подтвердить, что я не бот: нужны свежие cookies (см. README).") from e
        if "Private video" in msg or "members-only" in msg:
            raise DownloadError("Видео приватное или только для спонсоров.") from e
        if "live event" in msg or "is_live" in msg:
            raise DownloadError("Прямую трансляцию скачать нельзя, дождись записи.") from e
        raise DownloadError(f"yt-dlp: {msg.removeprefix('ERROR: ')[:400]}") from e

    if info.get("is_live"):
        raise DownloadError("Прямую трансляцию скачать нельзя, дождись записи.")

    audio = info.get("requested_downloads", [{}])[0].get("filepath")
    if not audio or not Path(audio).exists():
        raise DownloadError("yt-dlp ничего не скачал.")
    audio = Path(audio)

    result = AudioResult(
        title=info.get("title") or "audio",
        uploader=info.get("uploader") or info.get("channel") or "",
        duration=int(info.get("duration") or 0),
        url=info.get("webpage_url") or url,
        thumbnail=_make_thumbnail(out_dir),
    )
    result.parts, result.bitrate_kbps = _fit(cfg, audio, result.duration, out_dir)
    return result


def _fit(cfg: Config, audio: Path, duration: int, out_dir: Path) -> tuple[list[Path], int]:
    """Return a list of .m4a files, each under the upload limit."""
    limit = cfg.max_upload_bytes
    if audio.suffix.lower() == ".m4a" and audio.stat().st_size <= limit:
        return [audio], 0  # 0 = original stream, not re-encoded

    if duration <= 0:
        raise DownloadError("Не удалось узнать длительность видео.")

    # Bitrate that fits the whole track into one file (5% margin for the container).
    fit_kbps = int(limit * 8 * 0.95 / duration / 1000)
    kbps = min(cfg.bitrate_kbps, fit_kbps)
    if kbps >= cfg.min_bitrate_kbps:
        dst = out_dir / "audio.m4a"
        _encode(audio, dst, kbps)
        return [dst], kbps

    # Too long even at the minimum bitrate: encode once, then cut into parts by time.
    kbps = cfg.min_bitrate_kbps
    full = out_dir / "full.m4a"
    _encode(audio, full, kbps)
    part_sec = int(limit * 8 * 0.9 / (kbps * 1000))
    n = math.ceil(duration / part_sec)
    parts = []
    for i in range(n):
        dst = out_dir / f"part{i + 1:02d}.m4a"
        _ffmpeg("-ss", str(i * part_sec), "-t", str(part_sec), "-i", str(full), "-c", "copy", "-movflags", "+faststart", str(dst))
        parts.append(dst)
    return parts, kbps


def _encode(src: Path, dst: Path, kbps: int) -> None:
    # Low bitrates are almost always speech (lectures, podcasts): mono sounds better there.
    channels = "2" if kbps >= 64 else "1"
    log.info("encoding %s -> %s at %dk, %s ch", src.name, dst.name, kbps, channels)
    _ffmpeg("-i", str(src), "-vn", "-c:a", "aac", "-b:a", f"{kbps}k", "-ac", channels, "-movflags", "+faststart", str(dst))
