import logging
import random
import time

from aiogram import Bot, F, Router
from aiogram.enums import ChatType
from aiogram.types import Message

from bot.config import COOLDOWN_SECONDS, TRIGGER_CHANCE
from bot.llm import generate_roast

router = Router()

# Время последнего "выпада" бота по каждому чату, чтобы не спамить
_last_roast_at: dict[int, float] = {}


@router.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}), F.text)
async def maybe_roast(message: Message, bot: Bot) -> None:
    if message.from_user and message.from_user.is_bot:
        return
    if message.text.startswith("/"):
        return

    chat_id = message.chat.id
    now = time.monotonic()
    last = _last_roast_at.get(chat_id, 0.0)
    if now - last < COOLDOWN_SECONDS:
        return

    if random.random() >= TRIGGER_CHANCE:
        return

    roast = await generate_roast(message.text)
    if not roast:
        return

    _last_roast_at[chat_id] = now
    try:
        await message.reply(roast)
    except Exception:
        logging.exception("Не удалось отправить сообщение в чат %s", chat_id)
