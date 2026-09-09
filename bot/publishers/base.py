from dataclasses import dataclass
from typing import Protocol


@dataclass
class PublishResult:
    ok: bool
    message: str
    url: str | None = None


class Publisher(Protocol):
    """Граница, за которой прячется способ доставки поста в соцсеть.

    Пока способ не выбран (ручной копипаст или Publora), эта граница
    позволяет всему остальному коду не знать разницы.
    """

    async def publish(self, platform: str, text: str) -> PublishResult: ...
