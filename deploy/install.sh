#!/usr/bin/env bash
# Ставит Павлика на Ubuntu/Debian как systemd-сервис.
# Запуск из папки с репозиторием:  sudo bash deploy/install.sh
# Повторный запуск = обновление кода и перезапуск бота.

set -euo pipefail

APP_DIR=/opt/pavlik
APP_USER=pavlik
SERVICE=pavlik
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
    echo "Запускай через sudo: sudo bash deploy/install.sh" >&2
    exit 1
fi

if [[ ! -f "$SRC/requirements.txt" ]]; then
    echo "Не вижу requirements.txt рядом со скриптом — запускай из папки репозитория" >&2
    exit 1
fi

set_env() {
    APP_DIR="$APP_DIR" KEY="$1" VALUE="$2" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["APP_DIR"]) / ".env"
key, value = os.environ["KEY"], os.environ["VALUE"]
lines, done = [], False
for line in path.read_text(encoding="utf-8").splitlines():
    if not line.lstrip().startswith("#") and line.split("=", 1)[0].strip() == key:
        lines.append(f"{key}={value}")
        done = True
    else:
        lines.append(line)
if not done:
    lines.append(f"{key}={value}")
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
}

get_env() {
    APP_DIR="$APP_DIR" KEY="$1" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["APP_DIR"]) / ".env"
key = os.environ["KEY"]
for line in path.read_text(encoding="utf-8").splitlines():
    if not line.lstrip().startswith("#") and line.split("=", 1)[0].strip() == key:
        print(line.split("=", 1)[1].strip())
        break
PY
}

echo "==> Ставлю пакеты"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip rsync >/dev/null

echo "==> Готовлю пользователя и папку $APP_DIR"
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR"

echo "==> Копирую код"
rsync -a --delete --exclude .git --exclude .env --exclude .venv --exclude profiles.json \
    "$SRC"/ "$APP_DIR"/

echo "==> Собираю venv"
[[ -d "$APP_DIR/.venv" ]] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"

if [[ ! -f "$APP_DIR/.env" ]]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
fi

# Ключи можно передать переменными окружения:
#   sudo TELEGRAM_BOT_TOKEN=... LLM_API_KEY=... bash deploy/install.sh
# Иначе скрипт спросит их скрытым вводом.
if [[ -z "$(get_env TELEGRAM_BOT_TOKEN)" ]]; then
    token="${TELEGRAM_BOT_TOKEN:-}"
    if [[ -z "$token" ]]; then
        read -rsp "Токен бота от @BotFather: " token
        echo
    fi
    set_env TELEGRAM_BOT_TOKEN "$token"
fi

if [[ -z "$(get_env LLM_API_KEY)" ]]; then
    key="${LLM_API_KEY:-}"
    if [[ -z "$key" ]]; then
        read -rsp "Ключ Groq (console.groq.com/keys): " key
        echo
    fi
    set_env LLM_API_KEY "$key"
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo "==> Ставлю сервис"
install -m 644 "$APP_DIR/deploy/pavlik.service" /etc/systemd/system/$SERVICE.service
systemctl daemon-reload
systemctl enable $SERVICE
systemctl restart $SERVICE
sleep 3

systemctl --no-pager --lines 10 status $SERVICE || true
echo
echo "Готово. Логи:      journalctl -u $SERVICE -f"
echo "Перезапуск:        systemctl restart $SERVICE"
echo "Правка настроек:   nano $APP_DIR/.env  (потом systemctl restart $SERVICE)"
