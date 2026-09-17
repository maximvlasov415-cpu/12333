#!/usr/bin/env bash
# Подбирает живую модель и прописывает её в .env.
#   bash deploy/set_model.sh              — проверить список и выбрать рабочую
#   bash deploy/set_model.sh <id модели>  — поставить конкретную (тоже с проверкой)
# Каждая модель проверяется настоящим запросом: провайдеры снимают модели
# с обслуживания, а reasoning-модели возвращают пустой текст.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pavlik}"
ENV_FILE="$APP_DIR/.env"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[[ -f "$ENV_FILE" ]] || { echo "Нет $ENV_FILE — сначала поставь бота через deploy/install.sh" >&2; exit 1; }

CHOSEN="$(python3 "$SRC/pick_model.py" "${1:-}" "$ENV_FILE")"

echo "==> Модель: $CHOSEN"
systemctl restart pavlik
sleep 3
systemctl is-active pavlik
echo "Готово. Проверь в чате: /ping"
