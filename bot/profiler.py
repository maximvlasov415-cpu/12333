"""Раз в N сообщений просит модель обновить досье на участников чата."""

from __future__ import annotations

import json
import logging
import re

from .llm import LLM
from .memory import ChatHistory
from .persona import PROFILER_SYSTEM, PROFILER_TEMPLATE
from .profiles import ProfileStore

logger = logging.getLogger(__name__)

JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_notes(raw: str) -> dict[str, list[str]]:
    match = JSON_RE.search(raw)
    if match is None:
        return {}
    try:
        data = json.loads(match.group())
    except ValueError:
        logger.info("Модель вернула не-JSON досье: %s", raw[:200])
        return {}
    if not isinstance(data, dict):
        return {}

    notes: dict[str, list[str]] = {}
    for name, value in data.items():
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            notes[str(name)] = [str(item) for item in value if isinstance(item, (str, int, float))]
    return notes


class Profiler:
    def __init__(
        self,
        llm: LLM,
        history: ChatHistory,
        profiles: ProfileStore,
        every: int,
        max_tokens: int,
    ) -> None:
        self._llm = llm
        self._history = history
        self._profiles = profiles
        self._every = every
        self._max_tokens = max_tokens
        self._counters: dict[int, int] = {}
        self._running: set[int] = set()

    def due(self, chat_id: int) -> bool:
        count = self._counters.get(chat_id, 0) + 1
        if count < self._every or chat_id in self._running:
            self._counters[chat_id] = count
            return False
        self._counters[chat_id] = 0
        return True

    async def update(self, chat_id: int) -> None:
        self._running.add(chat_id)
        try:
            known = self._profiles.render(chat_id, author_id=0) or "Пока ничего."
            prompt = PROFILER_TEMPLATE.format(known=known, transcript=self._history.transcript(chat_id))
            raw = await self._llm.ask(PROFILER_SYSTEM, prompt, self._max_tokens, temperature=0.3)
            if raw is None:
                return
            notes = parse_notes(raw)
            if notes:
                self._profiles.update_notes(chat_id, notes)
                logger.info("Досье в чате %s обновлено: %s", chat_id, ", ".join(notes))
        except Exception:  # фоновая задача не должна ронять бота
            logger.exception("Не смог обновить досье в чате %s", chat_id)
        finally:
            self._running.discard(chat_id)
