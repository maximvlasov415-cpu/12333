from __future__ import annotations

import asyncio
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
from .mood import JOKE_CHANCE, classify
from .persona import (
    ADDRESSED_TEMPLATE,
    BOT_DISPLAY_NAME,
    FALLBACKS,
    FOLLOWUP_TEMPLATE,
    HINT_TEMPLATE,
    MOOD_DIRECTIVES,
    NO_JOKE_HINT,
    NO_JOKE_LINE,
    ROAST_TEMPLATE,
    TECHNIQUE_LINE,
)
from .profiler import Profiler
from .profiles import ProfileStore
from .wordplay import pick_joke

logger = logging.getLogger(__name__)

router = Router()


def build_name_pattern(names: list[str]) -> re.Pattern[str]:
    """Ловит имя бота в любом падеже: «бот», «боту», «ботяру»."""
    alternatives = "|".join(re.escape(name.lower()) for name in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternatives})\w*", re.IGNORECASE)


class Rotator:
    """Чередует приёмы шутки, чтобы Павлик не долбил одним и тем же."""

    def __init__(self, items: tuple[str, ...]) -> None:
        self._items = items
        self._last: dict[int, str] = {}

    def next(self, chat_id: int) -> str:
        options = [item for item in self._items if item != self._last.get(chat_id)]
        choice = random.choice(options)
        self._last[chat_id] = choice
        return choice


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
    text = "Я Павлик. Позовёшь по имени или тегнешь — отвечу. Не позовёшь — всё равно отвечу."
    history.add(message.chat.id, BOT_DISPLAY_NAME, text)
    await message.reply(text)


@router.message(Command("ping"))
async def on_ping(message: Message, config: Config, llm: LLM) -> None:
    """Проверка мозгов: жив ли доступ к модели и что именно ломается."""
    answer = await llm.ask("Отвечай одним словом.", "Скажи: живой", config.max_tokens, 0.0)
    if answer is not None:
        await message.reply(f"Модель {config.llm_model} отвечает: {answer}")
    else:
        await message.reply(f"Модель {config.llm_model} молчит.\nПричина: {llm.last_error}")


@router.message(F.text)
async def on_message(
    message: Message,
    bot: Bot,
    config: Config,
    llm: LLM,
    history: ChatHistory,
    profiles: ProfileStore,
    profiler: Profiler,
    throttle: Throttle,
    techniques: Rotator,
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
    profiles.observe(message.chat.id, message.from_user.id, author, text)
    if profiler.due(message.chat.id):
        asyncio.create_task(profiler.update(message.chat.id))

    me = await bot.me()
    addressed = _is_addressed(message, me.username or "", me.id, name_pattern)
    # Разговор с Павликом ещё идёт — влезать можно чаще и без кулдауна.
    in_dialogue = history.spoke_recently(message.chat.id, BOT_DISPLAY_NAME)
    if not addressed:
        chance = config.followup_probability if in_dialogue else config.random_reply_probability
        if random.random() >= chance:
            return
        if not in_dialogue and not throttle.allow(message.chat.id):
            return

    mood = classify(text)
    joke_allowed = random.random() < JOKE_CHANCE[mood]
    joke = pick_joke(text) if joke_allowed and random.random() < config.joke_probability else None
    if addressed:
        template = ADDRESSED_TEMPLATE
    elif in_dialogue:
        template = FOLLOWUP_TEMPLATE
    else:
        template = ROAST_TEMPLATE
    context = "\n\n".join(
        part
        for part in (
            profiles.render(message.chat.id, message.from_user.id),
            history.transcript(message.chat.id),
        )
        if part
    )
    directive = MOOD_DIRECTIVES[mood]
    if joke_allowed:
        technique = techniques.next(message.chat.id)
        directive = f"{directive}\n{TECHNIQUE_LINE.format(technique=technique)}"
    else:
        technique = "без шутки"
        directive = f"{directive}\n{NO_JOKE_LINE}"
    prompt = template.format(
        context=context,
        author=author,
        text=text,
        directive=directive,
        hint=HINT_TEMPLATE.format(joke=joke) if joke else NO_JOKE_HINT,
    )
    logger.info("Режим %s, приём: %s", mood, technique)

    await bot.send_chat_action(message.chat.id, "typing")
    reply = await llm.reply(prompt)
    if reply is None:
        if not addressed:
            return
        reply = joke.capitalize() + " чтоли" if joke else random.choice(FALLBACKS)

    history.add(message.chat.id, BOT_DISPLAY_NAME, reply)
    await message.reply(reply)
