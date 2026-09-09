from bot.publishers.base import PublishResult


class ManualPublisher:
    """Этап 1: публикуете вы сами, бот только подтверждает готовность текста."""

    async def publish(self, platform: str, text: str) -> PublishResult:
        return PublishResult(
            ok=True,
            message=f"Готово к публикации в {platform}. Текст выше — копируйте и постите.",
        )
