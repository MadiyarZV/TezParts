"""Последовательная очередь задач на каждый чат.

Зачем очередь: агентный запрос идёт от 30 секунд до нескольких минут.
Если пустить два запроса одного чата параллельно, они подерутся за одну
и ту же сессию Claude и за файлы в рабочей папке. Поэтому — строго по одному
на чат, остальные ждут. Разные чаты работают параллельно.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

log = logging.getLogger(__name__)

Job = Callable[[], Awaitable[None]]


class ChatQueue:
    def __init__(self) -> None:
        self._queues: dict[int, asyncio.Queue[Job]] = {}
        self._workers: dict[int, asyncio.Task] = {}
        self._current: dict[int, asyncio.Task] = {}

    def pending(self, chat_id: int) -> int:
        queue = self._queues.get(chat_id)
        return queue.qsize() if queue else 0

    def is_busy(self, chat_id: int) -> bool:
        task = self._current.get(chat_id)
        return task is not None and not task.done()

    async def submit(self, chat_id: int, job: Job) -> None:
        if chat_id not in self._queues:
            self._queues[chat_id] = asyncio.Queue()
            self._workers[chat_id] = asyncio.create_task(self._worker(chat_id))
        await self._queues[chat_id].put(job)

    def cancel_current(self, chat_id: int) -> bool:
        task = self._current.get(chat_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def drain(self, chat_id: int) -> int:
        """Выбрасывает всё, что ждёт в очереди. Возвращает число снятых задач."""
        queue = self._queues.get(chat_id)
        if not queue:
            return 0
        dropped = 0
        while not queue.empty():
            queue.get_nowait()
            queue.task_done()
            dropped += 1
        return dropped

    async def _worker(self, chat_id: int) -> None:
        queue = self._queues[chat_id]
        while True:
            job = await queue.get()
            task = asyncio.create_task(job())
            self._current[chat_id] = task
            try:
                await task
            except asyncio.CancelledError:
                log.info("Задача чата %s отменена", chat_id)
            except Exception:
                log.exception("Задача чата %s упала", chat_id)
            finally:
                self._current.pop(chat_id, None)
                queue.task_done()

    async def shutdown(self) -> None:
        for task in list(self._current.values()) + list(self._workers.values()):
            task.cancel()
        await asyncio.gather(*self._workers.values(), return_exceptions=True)
