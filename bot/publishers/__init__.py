from bot.publishers.base import PublishResult, Publisher
from bot.publishers.manual import ManualPublisher
from bot.publishers.publora import PubloraPublisher


def build_publisher(kind: str, api_key: str = "") -> Publisher:
    if kind == "manual":
        return ManualPublisher()
    if kind == "publora":
        return PubloraPublisher(api_key)
    raise RuntimeError(f"неизвестный публикатор: {kind}")


__all__ = ["Publisher", "PublishResult", "ManualPublisher", "PubloraPublisher", "build_publisher"]
