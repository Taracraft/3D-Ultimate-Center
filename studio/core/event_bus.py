"""In-process event bus used by workers and WebSocket adapters."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator

from .events import StudioEvent


class EventSubscription(AsyncIterator[StudioEvent]):
    def __init__(
        self,
        bus: "EventBus",
        topic: str,
        queue: asyncio.Queue[StudioEvent],
    ) -> None:
        self._bus = bus
        self._topic = topic
        self._queue = queue
        self._closed = False

    def __aiter__(self) -> "EventSubscription":
        return self

    async def __anext__(self) -> StudioEvent:
        if self._closed:
            raise StopAsyncIteration
        return await self._queue.get()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._bus._unsubscribe(self._topic, self._queue)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[StudioEvent]]] = defaultdict(set)

    async def publish(self, event: StudioEvent) -> None:
        queues = set(self._subscribers.get(event.topic, ()))
        queues.update(self._subscribers.get("*", ()))
        for queue in queues:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(event)

    def subscribe(self, topic: str = "*") -> EventSubscription:
        queue: asyncio.Queue[StudioEvent] = asyncio.Queue(maxsize=1000)
        self._subscribers[topic].add(queue)
        return EventSubscription(self, topic, queue)

    def _unsubscribe(
        self,
        topic: str,
        queue: asyncio.Queue[StudioEvent],
    ) -> None:
        subscribers = self._subscribers.get(topic)
        if subscribers is None:
            return
        subscribers.discard(queue)
        if not subscribers:
            self._subscribers.pop(topic, None)
