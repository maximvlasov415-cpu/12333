from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _split(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    telegram_token: str
    llm_base_url: str
    llm_api_key: str
    llm_model: str
    llm_extra_params: dict
    names: list[str]
    random_reply_probability: float
    random_reply_cooldown: int
    followup_probability: float
    joke_probability: float
    history_limit: int
    max_tokens: int
    temperature: float
    request_timeout: float
    allowed_chat_ids: set[int]
    profile_path: Path
    profile_update_every: int
    profile_max_notes: int
    profile_max_tokens: int

    @classmethod
    def from_env(cls) -> Config:
        load_dotenv()

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise SystemExit("TELEGRAM_BOT_TOKEN не задан — возьми токен у @BotFather и положи в .env")

        base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/")
        model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        if not api_key and "localhost" not in base_url and "127.0.0.1" not in base_url:
            raise SystemExit(f"LLM_API_KEY не задан — нужен ключ для {base_url}")

        try:
            extra_params = json.loads(os.getenv("LLM_EXTRA_PARAMS", "") or "{}")
        except ValueError as error:
            raise SystemExit(f"LLM_EXTRA_PARAMS — не JSON: {error}") from error

        names = _split(os.getenv("BOT_NAMES", "павлик,павлуш,павел,павл,паш"))
        if not names:
            raise SystemExit("BOT_NAMES пустой — боту не на что откликаться")

        return cls(
            telegram_token=token,
            llm_base_url=base_url,
            llm_api_key=api_key or "local",
            llm_model=model,
            llm_extra_params=extra_params,
            names=names,
            random_reply_probability=float(os.getenv("RANDOM_REPLY_PROBABILITY", "0.08")),
            random_reply_cooldown=int(os.getenv("RANDOM_REPLY_COOLDOWN", "180")),
            followup_probability=float(os.getenv("FOLLOWUP_PROBABILITY", "0.5")),
            joke_probability=float(os.getenv("JOKE_PROBABILITY", "0.15")),
            history_limit=int(os.getenv("HISTORY_LIMIT", "30")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "400")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.9")),
            request_timeout=float(os.getenv("LLM_TIMEOUT", "30")),
            allowed_chat_ids={int(chat_id) for chat_id in _split(os.getenv("ALLOWED_CHAT_IDS", ""))},
            profile_path=Path(os.getenv("PROFILE_PATH", "profiles.json")),
            profile_update_every=int(os.getenv("PROFILE_UPDATE_EVERY", "25")),
            profile_max_notes=int(os.getenv("PROFILE_MAX_NOTES", "3")),
            profile_max_tokens=int(os.getenv("PROFILE_MAX_TOKENS", "600")),
        )
