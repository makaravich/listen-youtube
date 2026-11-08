#!/usr/bin/env bash
# First-time setup on the server (Ubuntu 24.04 ARM). Run as the deploy user with sudo rights:
#   bash /opt/listen-youtube/deploy/install.sh
set -euo pipefail

APP=/opt/listen-youtube
cd "$APP"

sudo apt-get update -qq
sudo apt-get install -y -qq ffmpeg python3-venv unzip rsync

# yt-dlp needs a JS runtime (deno) to solve YouTube's player challenges.
if ! command -v deno >/dev/null; then
  arch=$(uname -m)   # aarch64 | x86_64
  tmp=$(mktemp -d)
  curl -fsSL -o "$tmp/deno.zip" "https://github.com/denoland/deno/releases/latest/download/deno-${arch}-unknown-linux-gnu.zip"
  unzip -q "$tmp/deno.zip" -d "$tmp"
  sudo install -m 755 "$tmp/deno" /usr/local/bin/deno
  rm -rf "$tmp"
fi
deno --version | head -1

python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

mkdir -p var/work
if [ ! -f .env ]; then
  cp .env.example .env
  echo ">>> edit $APP/.env (BOT_TOKEN, ALLOWED_IDS) and put cookies to $APP/var/cookies.txt"
fi

sudo cp deploy/listen-youtube.service deploy/listen-youtube-update.service deploy/listen-youtube-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable listen-youtube
sudo systemctl enable --now listen-youtube-update.timer
echo "installed. start with: sudo systemctl restart listen-youtube && journalctl -fu listen-youtube"
