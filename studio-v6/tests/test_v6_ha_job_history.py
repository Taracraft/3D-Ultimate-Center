"""Regression tests for the V6 Home Assistant print-job journal."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


class FakeStore:
    def __init__(self, *_args, **_kwargs) -> None:
        self.data = None
        self.saved = []

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.data = data
        self.saved.append(data)


homeassistant = types.ModuleType("homeassistant")
ha_core = types.ModuleType("homeassistant.core")
ha_helpers = types.ModuleType("homeassistant.helpers")
ha_storage = types.ModuleType("homeassistant.helpers.storage")
ha_core.HomeAssistant = object
ha_storage.Store = FakeStore
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.core", ha_core)
sys.modules.setdefault("homeassistant.helpers", ha_helpers)
sys.modules.setdefault("homeassistant.helpers.storage", ha_storage)

package = types.ModuleType("ultimate_3d_studio_v6")
package.__path__ = []
models = types.ModuleType("ultimate_3d_studio_v6.models")
models.PrinterSnapshot = object
sys.modules.setdefault("ultimate_3d_studio_v6", package)
sys.modules.setdefault("ultimate_3d_studio_v6.models", models)

PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
    / "job_history.py"
)
SPEC = importlib.util.spec_from_file_location("ultimate_3d_studio_v6.job_history", PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def snapshot(state: str, progress: float, file_name: str = "cube.3mf"):
    return SimpleNamespace(
        printer_id="SERIAL",
        name="Bambu A1",
        printer_state=state,
        current_file=file_name,
        progress=progress,
        updated_at="2026-07-03T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_running_job_is_created_and_updated() -> None:
    journal = module.JobHistory(object(), "entry")
    await journal.async_load()
    await journal.async_observe((snapshot("running", 12),))
    await journal.async_observe((snapshot("running", 34),))
    data = journal.as_dict()
    assert data["current_count"] == 1
    assert data["current"][0]["progress"] == 34
    assert data["history_count"] == 0


@pytest.mark.asyncio
async def test_completed_job_moves_to_persistent_history() -> None:
    journal = module.JobHistory(object(), "entry")
    await journal.async_load()
    await journal.async_observe((snapshot("running", 95),))
    await journal.async_observe((snapshot("finished", 100),))
    data = journal.as_dict()
    assert data["current_count"] == 0
    assert data["history_count"] == 1
    assert data["history"][0]["status"] == "completed"
    assert data["history"][0]["progress"] == 100
    assert journal._store.saved[-1]["history"][0]["file"] == "cube.3mf"


@pytest.mark.asyncio
async def test_file_change_archives_previous_job() -> None:
    journal = module.JobHistory(object(), "entry")
    await journal.async_load()
    await journal.async_observe((snapshot("running", 20, "first.3mf"),))
    await journal.async_observe((snapshot("running", 1, "second.3mf"),))
    data = journal.as_dict()
    assert data["current"][0]["file"] == "second.3mf"
    assert data["history"][0]["file"] == "first.3mf"
    assert data["history"][0]["status"] == "replaced"


@pytest.mark.asyncio
async def test_load_restores_queue_and_history() -> None:
    journal = module.JobHistory(object(), "entry")
    journal._store.data = {
        "queue": [{"job_id": "queued"}],
        "history": [{"job_id": "done"}],
    }
    await journal.async_load()
    data = journal.as_dict()
    assert data["queue_count"] == 1
    assert data["history_count"] == 1
    assert data["read_only"] is False
    assert data["persistent"] is True
    assert data["repeat_supported"] is True
    assert data["queue_remove_supported"] is True
    assert data["queue_execution_enabled"] is False


@pytest.mark.asyncio
async def test_history_job_can_be_queued_for_repeat_without_starting_print() -> None:
    journal = module.JobHistory(object(), "entry")
    journal._store.data = {
        "history": [
            {
                "job_id": "done-1",
                "printer_id": "SERIAL",
                "printer_name": "Bambu A1",
                "file": "cube.3mf",
                "status": "completed",
                "progress": 100,
            }
        ]
    }
    await journal.async_load()

    queued = await journal.async_repeat("done-1")

    assert queued is not None
    assert queued["job_id"].startswith("queue:")
    assert queued["source_job_id"] == "done-1"
    assert queued["status"] == "queued"
    assert queued["progress"] == 0
    assert queued["started_at"] is None
    assert journal.as_dict()["queue_count"] == 1


@pytest.mark.asyncio
async def test_unknown_history_job_is_not_queued() -> None:
    journal = module.JobHistory(object(), "entry")
    await journal.async_load()
    assert await journal.async_repeat("missing") is None
    assert journal.as_dict()["queue_count"] == 0


@pytest.mark.asyncio
async def test_queued_repeat_can_be_removed() -> None:
    journal = module.JobHistory(object(), "entry")
    journal._store.data = {
        "history": [{"job_id": "done-1", "file": "cube.3mf"}]
    }
    await journal.async_load()
    queued = await journal.async_repeat("done-1")
    assert queued is not None

    removed = await journal.async_remove_queued(queued["job_id"])

    assert removed is not None
    assert removed["job_id"] == queued["job_id"]
    assert journal.as_dict()["queue_count"] == 0


@pytest.mark.asyncio
async def test_matching_running_job_consumes_repeat_queue_item() -> None:
    journal = module.JobHistory(object(), "entry")
    journal._store.data = {
        "queue": [
            {
                "job_id": "queue:one",
                "source_job_id": "done-1",
                "printer_id": "SERIAL",
                "file": "cube.3mf",
                "status": "queued",
            }
        ]
    }
    await journal.async_load()

    await journal.async_observe((snapshot("running", 2, "cube.3mf"),))

    data = journal.as_dict()
    assert data["queue_count"] == 0
    assert data["current"][0]["queue_job_id"] == "queue:one"
    assert data["current"][0]["source_job_id"] == "done-1"
