"""Досье на участников чата: что человек мусолит и как его зовут кореша."""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from pathlib import Path

from .wordplay import STOPWORDS, WORD_RE

logger = logging.getLogger(__name__)

MAX_TOPICS = 40
MIN_TOPIC_COUNT = 3
TOPICS_IN_PROMPT = 3
PROFILES_IN_PROMPT = 5


class ProfileStore:
    """Копит темы из сообщений человека и тезисы, которые пишет модель."""

    def __init__(self, path: Path, max_notes: int, ignore: re.Pattern[str] | None = None) -> None:
        self._path = path
        self._max_notes = max_notes
        self._ignore = ignore
        self._chats: dict[str, dict[str, dict]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            self._chats = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            logger.warning("Не смог прочитать досье %s: %s", self._path, error)

    def save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._chats, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self._path)
        except OSError as error:
            logger.warning("Не смог сохранить досье %s: %s", self._path, error)

    def _chat(self, chat_id: int) -> dict[str, dict]:
        return self._chats.setdefault(str(chat_id), {})

    def observe(self, chat_id: int, user_id: int, name: str, text: str) -> None:
        profile = self._chat(chat_id).setdefault(str(user_id), {"name": name, "notes": [], "topics": {}})
        profile["name"] = name

        topics = Counter(profile["topics"])
        topics.update(
            word.lower()
            for word in WORD_RE.findall(text)
            if len(word) >= 4
            and word.lower() not in STOPWORDS
            and not (self._ignore and self._ignore.fullmatch(word.lower()))
        )
        profile["topics"] = dict(topics.most_common(MAX_TOPICS))

    def update_notes(self, chat_id: int, notes_by_name: dict[str, list[str]]) -> None:
        by_name = {profile["name"].lower(): profile for profile in self._chat(chat_id).values()}
        for name, notes in notes_by_name.items():
            profile = by_name.get(name.strip().lower())
            if profile is None:
                continue
            clean = [note.strip() for note in notes if note and note.strip()]
            profile["notes"] = clean[: self._max_notes]
        self.save()

    def _describe(self, profile: dict) -> str | None:
        parts = list(profile.get("notes", []))
        topics = [
            word
            for word, count in sorted(profile.get("topics", {}).items(), key=lambda item: -item[1])
            if count >= MIN_TOPIC_COUNT
        ][:TOPICS_IN_PROMPT]
        if topics:
            parts.append("часто пишет про: " + ", ".join(topics))
        if not parts:
            return None
        return f"{profile['name']}: " + "; ".join(parts)

    def render(self, chat_id: int, author_id: int) -> str:
        chat = self._chat(chat_id)
        author = chat.get(str(author_id))
        lines = []
        if author is not None:
            described = self._describe(author)
            if described:
                lines.append(described)
        for user_id, profile in chat.items():
            if user_id == str(author_id) or len(lines) >= PROFILES_IN_PROMPT:
                continue
            described = self._describe(profile)
            if described:
                lines.append(described)
        if not lines:
            return ""
        return "Что ты знаешь про этих людей:\n" + "\n".join(f"- {line}" for line in lines)

    def transcript_names(self, chat_id: int) -> list[str]:
        return [profile["name"] for profile in self._chat(chat_id).values()]
