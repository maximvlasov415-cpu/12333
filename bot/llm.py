from __future__ import annotations

import logging
import re

import aiohttp

from .config import Config
from .persona import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
NAME_PREFIX_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_ ]{1,20}:\s*")
REFUSAL_MARKERS = (
    "как языковая модель",
    "как ии",
    "я — ии",
    "не могу помочь",
    "не могу выполнить",
    "не могу поддержать",
    "не могу участвовать",
    "as an ai",
    "i can't",
    "i cannot",
    "i'm sorry",
)


def _clean(raw: str) -> str:
    text = THINK_RE.sub("", raw).strip()
    text = NAME_PREFIX_RE.sub("", text)
    if len(text) > 1 and text[0] in "«\"'" and text[-1] in "»\"'":
        text = text[1:-1].strip()
    return text


class LLM:
    """Клиент к любому OpenAI-совместимому API: Groq, Gemini, OpenRouter, Ollama."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._config.llm_api_key}"},
            timeout=aiohttp.ClientTimeout(total=self._config.request_timeout),
        )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def reply(self, prompt: str) -> str | None:
        if self._session is None:
            raise RuntimeError("LLM.start() не вызван")

        payload = {
            "model": self._config.llm_model,
            "max_tokens": self._config.max_tokens,
            "temperature": self._config.temperature,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }

        try:
            async with self._session.post(
                f"{self._config.llm_base_url}/chat/completions", json=payload
            ) as response:
                if response.status != 200:
                    logger.warning("LLM ответил %s: %s", response.status, await response.text())
                    return None
                data = await response.json()
        except aiohttp.ClientError as error:
            logger.warning("LLM недоступен: %s", error)
            return None
        except TimeoutError:
            logger.warning("LLM не ответил за %s секунд", self._config.request_timeout)
            return None

        choices = data.get("choices") or []
        if not choices:
            logger.warning("LLM вернул пустой ответ: %s", data)
            return None

        text = _clean(choices[0].get("message", {}).get("content") or "")
        if not text:
            return None

        lowered = text.lower()
        if any(marker in lowered for marker in REFUSAL_MARKERS):
            logger.info("Модель отказалась отвечать, включаю заглушку")
            return None

        return text
