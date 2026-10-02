"""Extended persistent print-job journal for V6."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .job_history import JobHistory


class JobHistoryV2(JobHistory):
    """Add explicit history maintenance without changing observation semantics."""

    def history_item(self, job_id: str) -> dict[str, Any] | None:
        requested = str(job_id or "")
        item = next(
            (
                entry
                for entry in self._history
                if str(entry.get("job_id", "")) == requested
            ),
            None,
        )
        return deepcopy(item) if item is not None else None

    async def async_remove_history(self, job_id: str) -> dict[str, Any] | None:
        requested = str(job_id or "")
        for index, item in enumerate(self._history):
            if str(item.get("job_id", "")) == requested:
                removed = self._history.pop(index)
                await self._save()
                return deepcopy(removed)
        return None

    async def async_clear_history(self) -> int:
        count = len(self._history)
        if count:
            self._history.clear()
            await self._save()
        return count