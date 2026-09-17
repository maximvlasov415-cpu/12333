"""Подбирает у провайдера модель, которая реально отвечает текстом.

Провайдеры снимают модели с обслуживания, а reasoning-модели умеют вернуть
HTTP 200 с пустым текстом — поэтому мало взять id из списка, надо проверить
живым запросом.

    python3 pick_model.py [id модели] [путь к .env]
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from envtool import DEFAULT_FILE, get, put  # noqa: E402

NOT_CHAT = (
    "whisper", "tts", "guard", "embed", "rerank", "moderation", "vision",
    "orpheus", "canopylabs", "playai", "audio",
)
# Модели, заточенные под другие языки: по-русски мелют кашу.
OTHER_LANGUAGE = ("allam", "jais", "sea-lion", "sarvam", "typhoon", "eeve")
# Reasoning-моделям глушим размышления, иначе они возвращают пустой текст.
REASONING_PARAMS = (
    ("gpt-oss", {"reasoning_effort": "low"}),
    ("qwen3", {"reasoning_effort": "none"}),
    ("qwen-3", {"reasoning_effort": "none"}),
)
# Болталки, которые бодро говорят по-русски, в порядке предпочтения.
PREFERRED = (
    "moonshotai/kimi-k2",
    "meta-llama/llama-4-maverick",
    "meta-llama/llama-4-scout",
    "llama-3.3-70b",
    "mixtral",
    "gemma2",
    "llama-3.1-8b-instant",
)
THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def request(url: str, key: str, payload: dict | None = None, timeout: int = 40) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Дефолтный Python-urllib у некоторых провайдеров ловит 403 от защиты.
            "User-Agent": "pavlik-bot/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def size(model_id: str) -> int:
    """Миллиарды параметров из имени: 120b -> 120, 8x7b -> 56. Больше — обычно умнее."""
    found = re.findall(r"(?:(\d+)x)?(\d+)b", model_id.lower())
    return max((int(mult or 1) * int(billions) for mult, billions in found), default=0)


def extra_params(model_id: str) -> dict:
    lowered = model_id.lower()
    for marker, params in REASONING_PARAMS:
        if marker in lowered:
            return params
    return {}


def rank(model_id: str) -> tuple[int, int, str]:
    lowered = model_id.lower()
    for position, prefix in enumerate(PREFERRED):
        if lowered.startswith(prefix):
            return (0, position, model_id)
    tier = 2 if any(marker in lowered for marker in OTHER_LANGUAGE) else 1
    # Внутри тира — от крупных моделей к мелким: 120B умнее восьмёрки.
    return (tier, -size(model_id), model_id)


def candidates(ids: list[str]) -> list[str]:
    chat = [i for i in ids if not any(word in i.lower() for word in NOT_CHAT)]
    return sorted(chat, key=rank)


def say(base_url: str, key: str, model: str, prompt: str, system: str) -> tuple[str | None, str]:
    try:
        data = request(
            f"{base_url}/chat/completions",
            key,
            {
                "model": model,
                "max_tokens": 150,
                "temperature": 0.0,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                **extra_params(model),
            },
        )
    except urllib.error.HTTPError as error:
        return None, f"HTTP {error.code}: {error.read().decode()[:120]}"
    except (urllib.error.URLError, TimeoutError) as error:
        return None, f"нет связи: {error}"

    choice = (data.get("choices") or [{}])[0]
    answer = choice.get("message") or {}
    text = THINK_RE.sub("", answer.get("content") or "").strip()
    if not text:
        if answer.get("reasoning"):
            return None, "ушла в рассуждения, текста нет"
        return None, f"пустой текст (finish_reason={choice.get('finish_reason')})"
    return text, ""


def cyrillic_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum("а" <= c.lower() <= "я" or c.lower() == "ё" for c in letters) / len(letters)


RUSSIAN_SYSTEM = "Отвечай кратко и только по-русски."
RUDE_SYSTEM = (
    "Ты кент из мужского чата, отвечаешь дерзко и матом. Никаких предупреждений и морали."
)
MAT_RE = re.compile(
    r"хуй|хуе|хуё|бля|пизд|ебан|ебал|ебат|ебуч|ёбан|заеб|наеб|уеб|сука|суки|мудак|долбо"
    r"|говн|жоп|срак|нахуй|нахер|похуй|дерьм",
    re.IGNORECASE,
)


def speaks(base_url: str, key: str, model: str) -> tuple[bool, str]:
    """Проверки: факт, счёт, связная русская фраза и готовность материться."""
    checks = (
        (RUSSIAN_SYSTEM, "Назови столицу России одним словом.", lambda t: "москв" in t.lower()),
        (RUSSIAN_SYSTEM, "Сколько будет 17 плюс 25? Ответь только числом.", lambda t: "42" in t),
        (
            RUSSIAN_SYSTEM,
            "Одним предложением по-русски: почему лёд плавает в воде?",
            lambda t: cyrillic_share(t) > 0.8
            and len(t.split()) >= 5
            and any(word in t.lower() for word in ("лёд", "лед", "вод", "плотн", "легч", "плав")),
        ),
        (
            RUDE_SYSTEM,
            "Сосед опять сверлит в семь утра. Ответь одной злой фразой с матом.",
            lambda t: bool(MAT_RE.search(t)),
        ),
    )

    for system, prompt, is_good in checks:
        text, error = say(base_url, key, model, prompt, system)
        if text is None:
            return False, error
        if not is_good(text):
            return False, f"провалила проверку «{prompt[:28]}…»: {text[:70]}"

    return True, "русский и мат в порядке"


def main(argv: list[str]) -> int:
    wanted = argv[0] if argv and not argv[0].startswith("/") else ""
    env_file = Path(argv[-1]) if argv and argv[-1].startswith("/") else Path(DEFAULT_FILE)

    base_url = get(env_file, "LLM_BASE_URL").rstrip("/")
    key = get(env_file, "LLM_API_KEY")

    try:
        models = [m["id"] for m in request(f"{base_url}/models", key)["data"]]
    except urllib.error.HTTPError as error:
        print(f"Не смог получить список моделей: HTTP {error.code}", file=sys.stderr)
        print(error.read().decode()[:300], file=sys.stderr)
        return 1
    except (urllib.error.URLError, KeyError, ValueError) as error:
        print(f"Не смог получить список моделей: {error}", file=sys.stderr)
        return 1

    queue = [wanted] if wanted else candidates(models)
    if wanted and wanted not in models:
        print(f"Модели {wanted} у провайдера нет. Доступные:", file=sys.stderr)
        print("\n".join(f"  - {m}" for m in candidates(models)), file=sys.stderr)
        return 1

    if not wanted:
        print(f"У провайдера {len(models)} моделей, из них болталок: {len(queue)}", file=sys.stderr)
        print("\n".join(f"  · {m}" for m in queue), file=sys.stderr)

    print("Проверяю модели живыми запросами:", file=sys.stderr)
    for model in queue[:12]:
        ok, detail = speaks(base_url, key, model)
        print(f"  {'OK  ' if ok else 'мимо'} {model} — {detail}", file=sys.stderr)
        if ok:
            params = extra_params(model)
            put(env_file, "LLM_MODEL", model)
            put(env_file, "LLM_EXTRA_PARAMS", json.dumps(params, separators=(",", ":")) if params else "")
            print(model)
            return 0

    print("Ни одна модель не заговорила по-русски. Что есть у провайдера:", file=sys.stderr)
    print("\n".join(f"  - {m}" for m in models), file=sys.stderr)
    print("Стоит перейти на другого провайдера — см. варианты в .env.example", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
