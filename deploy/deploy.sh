#!/usr/bin/env bash
# Push code to the server and restart the bot.
#   deploy/deploy.sh             # code only
#   deploy/deploy.sh --env       # also push .env.prod (falls back to .env)
#   deploy/deploy.sh --cookies   # also push var/cookies.txt
#   deploy/deploy.sh --install   # first run: code + run deploy/install.sh on the server
set -euo pipefail

HOST=${LISTEN_YT_HOST:-oracle-arm}
APP=/opt/listen-youtube
HERE=$(cd "$(dirname "$0")/.." && pwd)

WITH_ENV=0; WITH_COOKIES=0; INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --env) WITH_ENV=1 ;;
    --cookies) WITH_COOKIES=1 ;;
    --install) INSTALL=1 ;;
    *) echo "unknown option $arg"; exit 2 ;;
  esac
done

ssh "$HOST" "sudo mkdir -p $APP && sudo chown \$(id -un):\$(id -gn) $APP"

rsync -az --delete \
  --exclude .venv --exclude var --exclude '.env*' --exclude .git --exclude __pycache__ \
  --include .env.example \
  "$HERE/" "$HOST:$APP/"
rsync -az "$HERE/.env.example" "$HOST:$APP/.env.example"

if [ "$WITH_ENV" = 1 ]; then
  ENV_FILE="$HERE/.env.prod"; [ -f "$ENV_FILE" ] || ENV_FILE="$HERE/.env"
  echo "pushing $(basename "$ENV_FILE") as .env"
  rsync -az "$ENV_FILE" "$HOST:$APP/.env"
fi
if [ "$WITH_COOKIES" = 1 ]; then
  ssh "$HOST" "mkdir -p $APP/var"
  rsync -az --chmod=F600 "$HERE/var/cookies.txt" "$HOST:$APP/var/cookies.txt"
fi

if [ "$INSTALL" = 1 ]; then
  ssh -t "$HOST" "bash $APP/deploy/install.sh"
fi

ssh "$HOST" "cd $APP && .venv/bin/pip install -q -r requirements.txt \
  && for u in listen-youtube.service listen-youtube-update.service listen-youtube-update.timer; do \
       cmp -s deploy/\$u /etc/systemd/system/\$u || { sudo cp deploy/\$u /etc/systemd/system/\$u && echo \"\$u updated\"; CHANGED=1; }; done; \
     sudo systemctl daemon-reload \
  && sudo systemctl restart listen-youtube && sleep 2 && systemctl is-active listen-youtube && journalctl -u listen-youtube -n 5 --no-pager"
