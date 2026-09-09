import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.agent import ContentAgent
from bot.config import Config
from bot.db import Storage
from bot.handlers import WhitelistMiddleware, router
from bot.publishers import build_publisher
from bot.worker import JobQueue

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger(__name__)


async def main() -> None:
    config = Config.from_env()
    config.workspace.mkdir(parents=True, exist_ok=True)

    storage = Storage(config.db_path)
    agent = ContentAgent(config.workspace, config.model)
    publisher = build_publisher(config.publisher, config.publora_api_key)
    queue = JobQueue()

    guard = WhitelistMiddleware(config.allowed_user_ids)
    router.message.middleware(guard)
    router.callback_query.middleware(guard)

    # aiogram прокидывает workflow_data в хендлеры по имени параметра.
    dispatcher = Dispatcher()
    dispatcher["storage"] = storage
    dispatcher["agent"] = agent
    dispatcher["publisher"] = publisher
    dispatcher["queue"] = queue
    dispatcher.include_router(router)

    bot = Bot(token=config.bot_token)
    queue.start()
    log.info("бот запущен, whitelist: %s, публикатор: %s",
             config.allowed_user_ids, config.publisher)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await queue.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
