"""Regression tests for the safe V6 MakerWorld link catalog."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

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


homeassistant = sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
ha_core = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))
ha_helpers = sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
ha_aiohttp = sys.modules.setdefault(
    "homeassistant.helpers.aiohttp_client",
    types.ModuleType("homeassistant.helpers.aiohttp_client"),
)
ha_storage = sys.modules.setdefault(
    "homeassistant.helpers.storage",
    types.ModuleType("homeassistant.helpers.storage"),
)
ha_core.HomeAssistant = object
ha_aiohttp.async_get_clientsession = lambda _hass: None
ha_storage.Store = FakeStore

package = sys.modules.setdefault(
    "ultimate_3d_studio_v6",
    types.ModuleType("ultimate_3d_studio_v6"),
)
package.__path__ = []

PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
    / "makerworld_catalog.py"
)
SPEC = importlib.util.spec_from_file_location(
    "ultimate_3d_studio_v6.makerworld_catalog",
    PATH,
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_normalize_accepts_official_model_url_and_removes_tracking() -> None:
    url, model_id = module._normalize_model_url(
        "https://www.makerworld.com/de/models/123456-test-model?from=search#profileId-9"
    )
    assert url == "https://makerworld.com/de/models/123456-test-model"
    assert model_id == "123456"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/models/123-test",
        "http://makerworld.com/de/models/123-test",
        "https://makerworld.com/de/search/models",
        "https://user:pass@makerworld.com/de/models/123-test",
        "https://makerworld.com:8443/de/models/123-test",
    ],
)
def test_normalize_rejects_nonofficial_or_nonmodel_urls(url: str) -> None:
    with pytest.raises(ValueError):
        module._normalize_model_url(url)


def test_metadata_parser_handles_multiple_json_ld_blocks() -> None:
    parser = module._MetadataParser()
    parser.feed(
        """
        <html><head>
          <meta property="og:title" content="Demo Model">
          <meta property="og:image" content="https://cdn.example/model.webp">
          <link rel="canonical alternate" href="https://makerworld.com/de/models/99-demo">
          <script type="application/ld+json">{"@type":"BreadcrumbList","name":"Navigation"}</script>
          <script type="application/ld+json">{"@type":"Product","name":"Demo Model","author":{"name":"Maker"}}</script>
        </head><body></body></html>
        """
    )
    objects = module._json_ld_objects(parser.json_ld_blocks)
    assert parser.meta["og:title"] == "Demo Model"
    assert parser.canonical == "https://makerworld.com/de/models/99-demo"
    assert len(objects) == 2
    assert objects[1]["author"]["name"] == "Maker"


@pytest.mark.asyncio
async def test_add_loads_existing_catalog_before_persisting() -> None:
    catalog = module.MakerWorldCatalog(object())
    catalog._store.data = {
        "items": [
            {
                "id": "1",
                "title": "Existing",
                "model_url": "https://makerworld.com/de/models/1-existing",
            }
        ]
    }

    async def fake_metadata(_url: str, model_id: str):
        return {
            "id": model_id,
            "title": "New",
            "model_url": f"https://makerworld.com/de/models/{model_id}-new",
        }

    catalog._async_fetch_metadata = fake_metadata
    added = await catalog.async_add("https://makerworld.com/de/models/2-new")
    items = await catalog.async_list()

    assert added["id"] == "2"
    assert [item["id"] for item in items] == ["2", "1"]
    assert [item["id"] for item in catalog._store.saved[-1]["items"]] == ["2", "1"]


@pytest.mark.asyncio
async def test_refresh_replaces_item_without_duplicate() -> None:
    catalog = module.MakerWorldCatalog(object())
    catalog._store.data = {
        "items": [
            {
                "id": "5",
                "title": "Old",
                "model_url": "https://makerworld.com/de/models/5-demo",
            }
        ]
    }

    async def fake_metadata(_url: str, model_id: str):
        return {
            "id": model_id,
            "title": "Refreshed",
            "model_url": f"https://makerworld.com/de/models/{model_id}-demo",
        }

    catalog._async_fetch_metadata = fake_metadata
    refreshed = await catalog.async_refresh("5")
    items = await catalog.async_list()

    assert refreshed is not None
    assert refreshed["title"] == "Refreshed"
    assert len(items) == 1
    assert items[0]["title"] == "Refreshed"


@pytest.mark.asyncio
async def test_remove_is_persistent_and_unknown_id_is_safe() -> None:
    catalog = module.MakerWorldCatalog(object())
    catalog._store.data = {
        "items": [
            {
                "id": "7",
                "title": "Stored",
                "model_url": "https://makerworld.com/de/models/7-stored",
            }
        ]
    }

    assert await catalog.async_remove("missing") is None
    removed = await catalog.async_remove("7")

    assert removed is not None
    assert removed["id"] == "7"
    assert await catalog.async_list() == []
    assert catalog._store.saved[-1]["items"] == []