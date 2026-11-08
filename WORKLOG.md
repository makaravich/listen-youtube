# WORKLOG

## 2026-11-08
- Done: bot written (aiogram 3 + yt-dlp + ffmpeg), deployed to oracle-arm `/opt/listen-youtube`, systemd `listen-youtube` active,
  daily yt-dlp update timer. deno installed to /usr/local/bin. Download from Oracle IP works without cookies (with deno);
  without deno it failed with "Sign in to confirm you're not a bot". Re-encode and split paths tested locally.
- In progress: —
- Next step: real-world test in Telegram (long video > 50 min, Shorts, music.youtube).
- Blockers: none. If YouTube blocks the IP — cookies from a secondary account (README).
