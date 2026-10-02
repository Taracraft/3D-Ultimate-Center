"""Debounced asynchronous project autosave."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from .project_service import ProjectSession


class AutosaveController:
    def __init__(
        self,
        session: ProjectSession,
        delay_seconds: float = 1.5,
        on_saved: Callable[[int], None] | None = None,
    ) -> None:
        if delay_seconds <= 0:
            raise ValueError("delay_seconds must be greater than zero")
        self._session = session
        self._delay_seconds = delay_seconds
        self._on_saved = on_saved
        self._task: asyncio.Task[None] | None = None
        self._closed = False

    def schedule(self) -> None:
        if self._closed:
            raise RuntimeError("autosave controller is closed")
        if self._task is not None:
            self._task.cancel()
        self._task = asyncio.create_task(self._save_after_delay())

    async def flush(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None
        self._save_if_dirty()

    async def close(self) -> None:
        if self._closed:
            return
        await self.flush()
        self._closed = True

    async def _save_after_delay(self) -> None:
        try:
            await asyncio.sleep(self._delay_seconds)
            self._save_if_dirty()
        except asyncio.CancelledError:
            return
        finally:
            self._task = None

    def _save_if_dirty(self) -> None:
        if not self._session.dirty:
            return
        project = self._session.save()
        if self._on_saved is not None:
            self._on_saved(project.revision)
