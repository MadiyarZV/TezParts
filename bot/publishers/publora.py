from bot.publishers.base import PublishResult


class PubloraPublisher:
    """Заглушка под Publora.

    Реализуется, когда решение по каналу публикации будет принято. Точки,
    которые нужно будет закрыть: эндпоинт создания поста, привязка аккаунта
    к platform, обработка ошибки протухшего токена (алерт в Telegram, не в лог).
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise RuntimeError("PUBLORA_API_KEY не задан")
        self.api_key = api_key

    async def publish(self, platform: str, text: str) -> PublishResult:
        raise NotImplementedError("Publora-публикация ещё не подключена")
