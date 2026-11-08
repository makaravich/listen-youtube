# Listen YouTube (@listen_yt_bot)

Personal Telegram bot: send a YouTube link → get the audio track (m4a/AAC) back.

- Python 3.12, aiogram 3, yt-dlp (+ deno as JS runtime), ffmpeg, long polling.
- Access limited by `ALLOWED_IDS` in `.env`; strangers get their id on /start and nothing else.
- Original m4a stream is sent as is when it fits 48 MB (Bot API limit is 50 MB).
  Otherwise re-encoded to AAC at a bitrate that fits (128 → down to 48 kbps, mono below 64);
  if even 48 kbps is too big (~2 h+), split into parts.
- One job at a time, next links wait in a queue.

## Run locally
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
    cp .env.example .env   # BOT_TOKEN, ALLOWED_IDS
    .venv/bin/python -m listen_youtube

## Production
Server `ssh oracle-arm` (ubuntu-arm-01), `/opt/listen-youtube`, systemd unit `listen-youtube`.

    deploy/deploy.sh             # code
    deploy/deploy.sh --env       # + .env.prod as .env
    deploy/deploy.sh --cookies   # + var/cookies.txt
    deploy/deploy.sh --install   # first-time setup (apt, deno, venv, units)
    ssh oracle-arm journalctl -fu listen-youtube

Timer `listen-youtube-update.timer` updates yt-dlp daily at ~04:30 and restarts the bot.

## If YouTube starts asking "Sign in to confirm you're not a bot"
Datacenter IPs get flagged from time to time. Fix:
1. In a private browser window log in to a **secondary** Google account, open youtube.com.
2. Export cookies in Netscape format (extension "Get cookies.txt LOCALLY") to `var/cookies.txt`, close the window
   without logging out on youtube.com (otherwise cookies get rotated).
3. `deploy/deploy.sh --cookies` — the bot picks it up via `YTDLP_COOKIES=var/cookies.txt`.
Alternative: `YTDLP_PROXY=socks5://...` through a residential IP.
