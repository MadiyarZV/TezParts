"""Точка входа. Long polling — без домена, TLS и вебхуков.

Для одного пользователя polling проще и надёжнее вебхука: не нужен
белый IP, сертификат и открытый порт. Если однажды понадобится вебхук —
меняется только этот файл.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import config
from bot.handlers import queue, router


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    log = logging.getLogger("bot")
    log.info("Рабочая папка: %s", config.workspace)
    log.info("Разрешённые пользователи: %s", sorted(config.allowed_user_ids))

    bot = Bot(token=config.telegram_token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        await queue.shutdown()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
