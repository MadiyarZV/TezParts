import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.db.session import init_db
from bot.handlers import callbacks, commands
from bot.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await init_db()

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(commands.router)
    dp.include_router(callbacks.router)

    scheduler = build_scheduler(bot)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
