"""Exercise the actual repository using an in-memory HA Store boundary only."""
from __future__ import annotations

import asyncio
from copy import deepcopy
import importlib.util
from pathlib import Path
import os
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get("CAD_SOURCE_ROOT") or Path(__file__).resolve().parents[1])
COMPONENT = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"


class StoreDouble:
    def __class_getitem__(cls, _item):
        return cls

    def __init__(self, *_args):
        self.saved = None
        self.fail = False
        self.load_count = 0
        self.write_count = 0
        self.entered = None
        self.release = None

    async def async_load(self):
        self.load_count += 1
        await asyncio.sleep(0)
        return deepcopy(self.saved)

    async def async_save(self, value):
        self.write_count += 1
        if self.entered is not None:
            self.entered.set()
            await self.release.wait()
        if self.fail:
            raise OSError("storage unavailable")
        self.saved = deepcopy(value)


def load_repository():
    core = ModuleType("homeassistant.core")
    core.HomeAssistant = object
    storage = ModuleType("homeassistant.helpers.storage")
    storage.Store = StoreDouble
    package = ModuleType("_cad_project_repository_test")
    package.__path__ = [str(COMPONENT)]
    const = ModuleType("_cad_project_repository_test.const")
    const.DOMAIN = "test_studio"
    modules = {"homeassistant.core": core, "homeassistant.helpers.storage": storage,
               "_cad_project_repository_test": package, "_cad_project_repository_test.const": const}
    with patch.dict(sys.modules, modules):
        spec = importlib.util.spec_from_file_location("_cad_project_repository_test.studio_project_repository", COMPONENT / "studio_project_repository.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


REPOSITORY = load_repository()


def snapshot(mark="original"):
    return {"version": 1, "plates": [{"id": 0, "instances": [{"id": "mesh", "positions": [0, 0, 0, 1, 0, 0, 0, 1, 0]}]}],
            "paintCompositionVersion": 1, "paintLegacyAmbiguousObjectIds": ["mesh"],
            "paintRegions": [{"objectId": "mesh", "triangleIndices": [0], "label": mark}],
            "paintLayers": [[0, [{"id": "layer", "objectId": "mesh", "points": [{"x": 1}], "mask": {"kind": "text", "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], "left": 0, "top": 0, "right": 1, "bottom": 1, "width": 2, "height": 2, "runs": [0, 1, 3, 4]}}]]]}


class StudioProjectAtomicityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = REPOSITORY.StudioProjectRepository(object())
        self.store = self.repository._store

    async def test_failed_create_does_not_publish_a_phantom_project(self):
        self.store.fail = True
        with self.assertRaises(OSError):
            await self.repository.async_create("Project", snapshot())
        self.assertEqual(await self.repository.async_list(), [])

    async def test_failed_save_keeps_revision_and_data_retryable(self):
        created = await self.repository.async_create("Project", snapshot())
        self.store.fail = True
        with self.assertRaises(OSError):
            await self.repository.async_save_project(created["id"], name="Changed", snapshot=snapshot("new"), expected_revision=1)
        current = await self.repository.async_get(created["id"])
        self.assertEqual(current["revision"], 1)
        self.assertEqual(current["snapshot"], snapshot())
        self.store.fail = False
        saved = await self.repository.async_save_project(created["id"], name="Changed", snapshot=snapshot("new"), expected_revision=1)
        self.assertEqual(saved["revision"], 2)

    async def test_failed_delete_keeps_project_and_revision(self):
        created = await self.repository.async_create("Project", snapshot())
        self.store.fail = True
        with self.assertRaises(OSError):
            await self.repository.async_delete(created["id"], expected_revision=1)
        self.assertEqual((await self.repository.async_get(created["id"]))["revision"], 1)

    async def test_concurrent_writers_publish_one_revision_after_storage_succeeds(self):
        created = await self.repository.async_create("Project", snapshot())
        self.store.entered = asyncio.Event()
        self.store.release = asyncio.Event()
        first = asyncio.create_task(self.repository.async_save_project(created["id"], name="First", snapshot=snapshot("first"), expected_revision=1))
        await self.store.entered.wait()
        current = await self.repository.async_get(created["id"])
        second = asyncio.create_task(self.repository.async_save_project(created["id"], name="Second", snapshot=snapshot("second"), expected_revision=1))
        self.store.release.set()
        results = await asyncio.gather(first, second, return_exceptions=True)
        self.assertEqual(current["revision"], 1, "in-flight revision must not be exposed as durable")
        self.assertEqual(results[0]["revision"], 2)
        self.assertIsInstance(results[1], REPOSITORY.ProjectConflictError)
        self.assertEqual((await self.repository.async_get(created["id"]))["snapshot"], snapshot("first"))

    async def test_initial_load_is_shared_by_concurrent_creates(self):
        created = await asyncio.gather(self.repository.async_create("One", snapshot()), self.repository.async_create("Two", snapshot()))
        self.assertEqual(self.store.load_count, 1)
        self.assertEqual(len(await self.repository.async_list()), 2)
        self.assertNotEqual(created[0]["id"], created[1]["id"])

    async def test_revision_restore_keeps_complete_paint_sources_and_creates_new_revision(self):
        original = snapshot()
        created = await self.repository.async_create("Project", original)
        original["paintLayers"][0][1][0]["mask"]["matrix"][0] = 999
        await self.repository.async_save_project(created["id"], name="Project", snapshot=snapshot("new"), expected_revision=1)
        restored = await self.repository.async_restore(created["id"], source_revision=1, expected_revision=2)
        self.assertEqual(restored["revision"], 3)
        self.assertEqual(restored["snapshot"], snapshot())
        restored["snapshot"]["paintRegions"][0]["triangleIndices"].clear()
        self.assertEqual((await self.repository.async_get(created["id"]))["snapshot"], snapshot())

    async def test_invalid_masks_are_rejected_before_saving_without_discarding_the_prior_revision(self):
        created = await self.repository.async_create("Project", snapshot())
        for change in ({"matrix": [1, 2]}, {"width": 1_000_001}, {"runs": [0, 2, 1, 4]}, {"runs": [0, 5]}, {"right": 0}, {"kind": "rectangle", "runs": [0, 1_000_001]}, {"kind": "circle", "runs": [0]}, {"kind": "rectangle", "runs": None}):
            invalid = snapshot()
            invalid["paintLayers"][0][1][0]["mask"].update(change)
            with self.assertRaises(REPOSITORY.ProjectValidationError):
                await self.repository.async_save_project(created["id"], name="Project", snapshot=invalid, expected_revision=1)
        self.assertEqual((await self.repository.async_get(created["id"]))["revision"], 1)

    async def test_invalid_snapshot_does_not_change_revision(self):
        created = await self.repository.async_create("Project", snapshot())
        invalid = snapshot(); invalid["nonfinite"] = float("nan")
        with self.assertRaises(REPOSITORY.ProjectValidationError):
            await self.repository.async_save_project(created["id"], name="Project", snapshot=invalid, expected_revision=1)
        self.assertEqual((await self.repository.async_get(created["id"]))["revision"], 1)


if __name__ == "__main__":
    unittest.main()
