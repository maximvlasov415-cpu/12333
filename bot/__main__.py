from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from .config import Config
from .handlers import Throttle, build_name_pattern, router
from .llm import LLM
from .memory import ChatHistory
from .profiler import Profiler
from .profiles import ProfileStore


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    config = Config.from_env()
    llm = LLM(config)
    await llm.start()

    name_pattern = build_name_pattern(config.names)
    history = ChatHistory(config.history_limit)
    profiles = ProfileStore(config.profile_path, config.profile_max_notes, ignore=name_pattern)

    bot = Bot(config.telegram_token)
    dispatcher = Dispatcher(
        config=config,
        llm=llm,
        history=history,
        profiles=profiles,
        profiler=Profiler(
            llm,
            history,
            profiles,
            every=config.profile_update_every,
            max_tokens=config.profile_max_tokens,
        ),
        throttle=Throttle(config.random_reply_cooldown),
        name_pattern=name_pattern,
    )
    dispatcher.include_router(router)

    me = await bot.me()
    logging.info("Запустился как @%s, модель %s", me.username, config.llm_model)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await llm.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
