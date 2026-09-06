from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from bot.config import settings
from bot.jobs.daily_post import run_daily_post


def build_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_daily_post,
        trigger=CronTrigger(hour=settings.daily_post_hour, minute=settings.daily_post_minute),
        args=[bot],
        id="daily_post",
        replace_existing=True,
    )
    return scheduler
