from __future__ import annotations

import logging
import random
import re
import time

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message

from .config import Config
from .llm import LLM
from .memory import ChatHistory
from .persona import ADDRESSED_TEMPLATE, FALLBACKS, HINT_TEMPLATE, ROAST_TEMPLATE
from .wordplay import pick_joke

logger = logging.getLogger(__name__)

router = Router()


def build_name_pattern(names: list[str]) -> re.Pattern[str]:
    """Ловит имя бота в любом падеже: «бот», «боту», «ботяру»."""
    alternatives = "|".join(re.escape(name.lower()) for name in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})\w*", re.IGNORECASE)


class Throttle:
    """Не даёт боту влезать в чат чаще, чем раз в N секунд."""

    def __init__(self, cooldown: int) -> None:
        self._cooldown = cooldown
        self._last: dict[int, float] = {}

    def allow(self, chat_id: int) -> bool:
        now = time.monotonic()
        if now - self._last.get(chat_id, 0.0) < self._cooldown:
            return False
        self._last[chat_id] = now
        return True


def author_name(message: Message) -> str:
    user = message.from_user
    if user is None:
        return "Аноним"
    return user.first_name or user.username or "Аноним"


def _is_mentioned(message: Message, bot_username: str, bot_id: int) -> bool:
    text = message.text or ""
    for entity in message.entities or []:
        if entity.type == "mention" and text[entity.offset : entity.offset + entity.length].lower() == f"@{bot_username.lower()}":
            return True
        if entity.type == "text_mention" and entity.user and entity.user.id == bot_id:
            return True
    return False


def _is_addressed(message: Message, bot_username: str, bot_id: int, name_pattern: re.Pattern[str]) -> bool:
    if message.chat.type == "private":
        return True
    reply_to = message.reply_to_message
    if reply_to is not None and reply_to.from_user is not None and reply_to.from_user.id == bot_id:
        return True
    if _is_mentioned(message, bot_username, bot_id):
        return True
    return bool(name_pattern.search(message.text or ""))


@router.message(Command("start", "help"))
async def on_start(message: Message, history: ChatHistory) -> None:
    text = "Я тут сижу и слушаю. Позовёшь по имени или тегнешь — отвечу. Не позовёшь — всё равно отвечу."
    history.add(message.chat.id, "Бот", text)
    await message.reply(text)


@router.message(F.text)
async def on_message(
    message: Message,
    bot: Bot,
    config: Config,
    llm: LLM,
    history: ChatHistory,
    throttle: Throttle,
    name_pattern: re.Pattern[str],
) -> None:
    if message.from_user is None or message.from_user.is_bot:
        return
    if config.allowed_chat_ids and message.chat.id not in config.allowed_chat_ids:
        logger.debug("Чужой чат %s, игнорирую", message.chat.id)
        return

    text = message.text or ""
    author = author_name(message)
    history.add(message.chat.id, author, text)

    me = await bot.me()
    addressed = _is_addressed(message, me.username or "", me.id, name_pattern)
    if not addressed:
        if random.random() >= config.random_reply_probability or not throttle.allow(message.chat.id):
            return

    joke = pick_joke(text)
    template = ADDRESSED_TEMPLATE if addressed else ROAST_TEMPLATE
    prompt = template.format(
        transcript=history.transcript(message.chat.id),
        author=author,
        text=text,
        hint=HINT_TEMPLATE.format(joke=joke) if joke else "",
    )

    await bot.send_chat_action(message.chat.id, "typing")
    reply = await llm.reply(prompt)
    if reply is None:
        if not addressed:
            return
        reply = joke.capitalize() + " чтоли" if joke else random.choice(FALLBACKS)

    history.add(message.chat.id, "Бот", reply)
    await message.reply(reply)
