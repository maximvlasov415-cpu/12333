from __future__ import annotations

from collections import defaultdict, deque


class ChatHistory:
    """Последние сообщения по каждому чату — контекст для модели."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._chats: dict[int, deque[tuple[str, str]]] = defaultdict(lambda: deque(maxlen=limit))

    def add(self, chat_id: int, author: str, text: str) -> None:
        self._chats[chat_id].append((author, text))

    def spoke_recently(self, chat_id: int, author: str, window: int = 3) -> bool:
        """Павлик встревал в последние сообщения — значит разговор с ним ещё идёт."""
        recent = list(self._chats[chat_id])[-window:]
        return any(name == author for name, _ in recent)

    def transcript(self, chat_id: int) -> str:
        lines = [f"{author}: {text}" for author, text in self._chats[chat_id]]
        if not lines:
            return "Переписка только началась."
        return "Последние сообщения в чате:\n" + "\n".join(lines)
