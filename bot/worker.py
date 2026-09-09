"""Очередь задач к агенту.

Генерация поста идёт десятки секунд и дольше. Если запускать её прямо в
хендлере, Telegram будет копить апдейты, а параллельные запуски — жечь токены.
Один воркер, одна задача за раз, явная обратная связь пользователю.
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable

log = logging.getLogger(__name__)

Job = Callable[[], Awaitable[None]]


class JobQueue:
    def __init__(self, maxsize: int = 20):
        self._queue: asyncio.Queue[Job] = asyncio.Queue(maxsize=maxsize)
        self._task: asyncio.Task | None = None

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    async def put(self, job: Job) -> bool:
        try:
            self._queue.put_nowait(job)
            return True
        except asyncio.QueueFull:
            return False

    def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            job = await self._queue.get()
            try:
                await job()
            except Exception:
                # Воркер не должен умирать из-за одной неудачной задачи.
                log.exception("задача упала")
            finally:
                self._queue.task_done()
