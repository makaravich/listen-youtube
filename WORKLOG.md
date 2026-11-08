# WORKLOG

## 2026-11-08
- Done: bot written (aiogram 3 + yt-dlp + ffmpeg), deployed to oracle-arm `/opt/listen-youtube`, systemd `listen-youtube` active,
  daily yt-dlp update timer. deno installed to /usr/local/bin. Download from Oracle IP works without cookies (with deno);
  without deno it failed with "Sign in to confirm you're not a bot". Re-encode and split paths tested locally.
- In progress: —
- Fixed: handler crashed on "message is not modified" (status edit to the same text) -> silent "Скачиваю…".
- Oracle IP got flagged after a few requests ("not a bot" on 2 of 3 videos even with deno) -> cookies of a
  secondary Google account in var/cookies.txt (pushed with deploy.sh --cookies), works.
- Repo: github.com/makaravich/listen-youtube (main + vibecoding). gh logged in as makaravich.
- Next step: real-world test in Telegram (long video > 50 min, Shorts, music.youtube).
- Blockers: cookies expire (weeks-months) -> bot says so, re-export and deploy.sh --cookies.
