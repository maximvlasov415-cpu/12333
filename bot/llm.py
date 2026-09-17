from __future__ import annotations

import json
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
        self.last_error: str | None = None

    async def start(self) -> None:
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._config.llm_api_key}"},
            timeout=aiohttp.ClientTimeout(total=self._config.request_timeout),
        )

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def ask(self, system: str, prompt: str, max_tokens: int, temperature: float) -> str | None:
        if self._session is None:
            raise RuntimeError("LLM.start() не вызван")

        payload = {
            "model": self._config.llm_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }

        try:
            async with self._session.post(
                f"{self._config.llm_base_url}/chat/completions", json=payload
            ) as response:
                body = await response.text()
                if response.status != 200:
                    self.last_error = f"HTTP {response.status}: {body[:300]}"
                    logger.warning("LLM ответил %s: %s", response.status, body[:500])
                    return None
                data = json.loads(body)
        except aiohttp.ClientError as error:
            self.last_error = f"сеть: {error}"
            logger.warning("LLM недоступен: %s", error)
            return None
        except TimeoutError:
            self.last_error = f"таймаут {self._config.request_timeout} c"
            logger.warning("LLM не ответил за %s секунд", self._config.request_timeout)
            return None
        except ValueError as error:
            self.last_error = f"нечитаемый ответ: {error}"
            logger.warning("LLM вернул не-JSON: %s", error)
            return None

        choices = data.get("choices") or []
        if not choices:
            self.last_error = f"пустой ответ: {str(data)[:300]}"
            logger.warning("LLM вернул пустой ответ: %s", data)
            return None

        text = _clean(choices[0].get("message", {}).get("content") or "")
        if not text:
            self.last_error = "модель вернула пустой текст"
            logger.warning("LLM вернул пустой текст: %s", str(choices[0])[:300])
            return None

        self.last_error = None
        return text

    async def reply(self, prompt: str) -> str | None:
        """Реплика в чат от лица Павлика."""
        text = await self.ask(
            SYSTEM_PROMPT, prompt, self._config.max_tokens, self._config.temperature
        )
        if text is None:
            return None

        lowered = text.lower()
        if any(marker in lowered for marker in REFUSAL_MARKERS):
            self.last_error = f"модель включила цензуру: {text[:200]}"
            logger.warning("Модель отказалась отвечать: %s", text[:300])
            return None

        return text
