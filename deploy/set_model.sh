#!/usr/bin/env bash
# Показывает живые модели провайдера и прописывает рабочую в .env.
#   bash deploy/set_model.sh              — подобрать автоматически
#   bash deploy/set_model.sh <id модели>  — поставить конкретную
# Провайдеры снимают модели с обслуживания, и бот начинает ловить 404 —
# этот скрипт чинит такое без правки кода.

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/pavlik}"
ENV_FILE="$APP_DIR/.env"
ENVTOOL="$APP_DIR/deploy/envtool.py"
WANTED="${1:-}"

[[ -f "$ENV_FILE" ]] || { echo "Нет $ENV_FILE — сначала поставь бота через deploy/install.sh" >&2; exit 1; }

BASE_URL="$(python3 "$ENVTOOL" get LLM_BASE_URL "$ENV_FILE")"
API_KEY="$(python3 "$ENVTOOL" get LLM_API_KEY "$ENV_FILE")"

echo "==> Спрашиваю список моделей у $BASE_URL"
LIST="$(curl -sS --max-time 20 "$BASE_URL/models" -H "Authorization: Bearer $API_KEY")"

CHOICE="$(LIST="$LIST" WANTED="$WANTED" python3 - <<'PY'
import json
import os
import sys

try:
    ids = sorted(m["id"] for m in json.loads(os.environ["LIST"])["data"])
except (KeyError, ValueError):
    print("Провайдер вернул не список моделей:", os.environ["LIST"][:300], file=sys.stderr)
    raise SystemExit(1)

skip = ("whisper", "tts", "guard", "embed", "rerank", "moderation")
chat = [i for i in ids if not any(word in i.lower() for word in skip)]

print("Доступные модели:", file=sys.stderr)
for model_id in chat:
    print("  -", model_id, file=sys.stderr)

wanted = os.environ.get("WANTED", "")
if wanted:
    if wanted not in ids:
        print(f"Модели {wanted} нет в списке", file=sys.stderr)
        raise SystemExit(1)
    print(wanted, end="")
    raise SystemExit(0)

# Порядок предпочтения: сначала те, что живее в разговорном русском.
preferred = (
    "moonshotai/kimi-k2-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-120b",
    "qwen/qwen3-32b",
    "deepseek-r1-distill-llama-70b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
)
for model_id in preferred:
    if model_id in chat:
        print(model_id, end="")
        raise SystemExit(0)

if not chat:
    print("Провайдер не отдал ни одной болталки", file=sys.stderr)
    raise SystemExit(1)

print(chat[0], end="")
PY
)"

echo "==> Ставлю модель: $CHOICE"
python3 "$ENVTOOL" set LLM_MODEL "$CHOICE" "$ENV_FILE"
systemctl restart pavlik
sleep 3
systemctl is-active pavlik
echo "Готово. Проверь в чате: /ping"
