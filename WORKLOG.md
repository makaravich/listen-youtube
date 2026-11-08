# WORKLOG

## 2026-11-08
- Done:
  - Bot written (aiogram 3 + yt-dlp + ffmpeg, long polling) and deployed to oracle-arm `/opt/listen-youtube`,
    systemd `listen-youtube`; daily yt-dlp update timer `listen-youtube-update.timer` (~04:30).
  - deno installed to /usr/local/bin (yt-dlp JS runtime). Without it YouTube refused right away.
  - Fixed: handler crashed on "message is not modified" (status edit to the same text) -> bot hung on "Скачиваю…".
  - Oracle IP got flagged after a few requests ("not a bot" on 2 of 3 videos even with deno) ->
    cookies of a secondary Google account in `var/cookies.txt` (`deploy/deploy.sh --cookies`).
    Cookies replaced once more the same day (`cookies2.txt` -> `cookies.txt`, previous kept as `var/cookies.prev.txt`).
  - Progress in the status message: metadata stage, download bar with MB/speed/ETA, encode bar, part N/M; refresh every 2 s.
  - Daily cookie check at 10:00 Europe/Warsaw (test video, no download), notifies ALLOWED_IDS on failure;
    `/check` command; `/check` + `/start` registered in the bot menu at startup.
  - Verified in Telegram by the user: short video, 28-min video (13 s, no re-encode), 66-min video (re-encoded to 96 kbps, progress shown).
  - Repo github.com/makaravich/listen-youtube; `main` fast-forwarded to `vibecoding` (49c1052). gh logged in as makaravich.
- In progress: —
- Next step: nothing required. Untested yet: very long video (> ~2 h, split into parts), Shorts, music.youtube links.
- Blockers: cookies expire (weeks to months) -> the daily check warns; re-export in incognito, drop the file into
  the project, `deploy/deploy.sh --cookies`.
