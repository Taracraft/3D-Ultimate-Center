"""Generic bounded background job runner."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class JobRequest:
    id: str
    handler: Callable[[], Awaitable[Any]]


class BackgroundJobRunner:
    def __init__(self, max_parallel_jobs: int = 1) -> None:
        if max_parallel_jobs < 1:
            raise ValueError("max_parallel_jobs must be at least 1")
        self._queue: asyncio.Queue[JobRequest] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._max_parallel_jobs = max_parallel_jobs
        self._closed = False

    async def start(self) -> None:
        if self._workers:
            return
        self._closed = False
        self._workers = [
            asyncio.create_task(self._worker(index))
            for index in range(self._max_parallel_jobs)
        ]

    async def submit(self, request: JobRequest) -> None:
        if self._closed:
            raise RuntimeError("job runner is closed")
        if not self._workers:
            await self.start()
        await self._queue.put(request)

    async def join(self) -> None:
        await self._queue.join()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._queue.join()
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    async def _worker(self, worker_index: int) -> None:
        while True:
            request = await self._queue.get()
            try:
                await request.handler()
            finally:
                self._queue.task_done()