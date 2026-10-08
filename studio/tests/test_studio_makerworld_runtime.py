"""Regression tests for the authenticated Studio MakerWorld browser."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


sys.modules.setdefault("homeassistant", types.ModuleType("homeassistant"))
ha_core = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))
sys.modules.setdefault("homeassistant.helpers", types.ModuleType("homeassistant.helpers"))
ha_aiohttp = sys.modules.setdefault(
    "homeassistant.helpers.aiohttp_client",
    types.ModuleType("homeassistant.helpers.aiohttp_client"),
)
ha_core.HomeAssistant = object
ha_aiohttp.async_get_clientsession = lambda _hass: None

package = sys.modules.setdefault(
    "ultimate_3d_studio",
    types.ModuleType("ultimate_3d_studio"),
)
package.__path__ = []
const = sys.modules.setdefault(
    "ultimate_3d_studio.const",
    types.ModuleType("ultimate_3d_studio.const"),
)
for key, value in {
    "CONF_CLOUD_ACCESS_TOKEN": "cloud_access_token",
    "CONF_CLOUD_REGION": "cloud_region",
    "DOMAIN": "ultimate_3d_studio",
    "REGION_CHINA": "china",
    "REGION_GLOBAL": "global",
    "VERSION": "6.0.0-test",
}.items():
    setattr(const, key, value)

PAGER_PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
    / "makerworld_search_pager.py"
)
PAGER_SPEC = importlib.util.spec_from_file_location(
    "ultimate_3d_studio.makerworld_search_pager",
    PAGER_PATH,
)
assert PAGER_SPEC and PAGER_SPEC.loader
pager_module = importlib.util.module_from_spec(PAGER_SPEC)
sys.modules[PAGER_SPEC.name] = pager_module
PAGER_SPEC.loader.exec_module(pager_module)

PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio"
    / "makerworld_runtime.py"
)
SPEC = importlib.util.spec_from_file_location(
    "ultimate_3d_studio.makerworld_runtime",
    PATH,
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def browse_payload():
    return {
        "data": {
            "hits": [
                {
                    "designId": 12345,
                    "title": "Benchy Test",
                    "coverUrl": "https://makerworld.bblmw.com/model.webp",
                    "creator": {"name": "Designer"},
                    "tags": [{"name": "Boat"}, {"name": "Test"}],
                    "likeCount": 42,
                    "downloadCount": 1200,
                    "commentCount": 7,
                },
                {
                    "designId": 12345,
                    "title": "Duplicate",
                    "coverUrl": "https://makerworld.bblmw.com/duplicate.webp",
                    "downloadCount": 1,
                },
            ]
        }
    }


def detail_payload():
    return {
        "data": {
            "id": 12345,
            "title": "Benchy Test",
            "description": "Ausführliche Modellbeschreibung",
            "creator": {"nickname": "Designer"},
            "images": [
                {"url": "https://makerworld.bblmw.com/one.webp"},
                {"url": "https://makerworld.bblmw.com/two.webp"},
            ],
            "downloadCount": 1200,
            "likeCount": 42,
            "instances": [
                {
                    "instanceId": "9988",
                    "title": "0.20 mm Standard",
                    "isDefault": True,
                    "printerModel": "Bambu Lab A1",
                    "nozzleDiameter": "0.4",
                    "coverUrl": "https://makerworld.bblmw.com/profile.webp",
                    "plates": [
                        {
                            "plateId": "plate-1",
                            "plateIndex": 0,
                            "name": "Plate 1",
                            "thumbnailUrl": "https://makerworld.bblmw.com/plate.webp",
                            "printTimeSeconds": 7200,
                            "weightGrams": 48,
                        }
                    ],
                },
                {
                    "id": "8877",
                    "name": "0.16 mm Qualität",
                    "default": False,
                    "plateList": [],
                },
            ],
        }
    }


def test_browse_normalization_deduplicates_designs() -> None:
    designs = module._designs_from_payload(browse_payload())
    assert len(designs) == 1
    assert designs[0]["id"] == "12345"
    assert designs[0]["title"] == "Benchy Test"
    assert designs[0]["creator"] == "Designer"
    assert designs[0]["thumbnail_url"].endswith("model.webp")
    assert designs[0]["stats"]["downloads"] == 1200
    assert designs[0]["tags"] == ["Boat", "Test"]


def test_detail_normalization_includes_instances_and_plates() -> None:
    raw = module._find_design_payload(detail_payload(), "12345")
    design = module._normalize_design(raw)
    assert design is not None
    instances = module._instances_from_design(raw, "12345")

    assert design["description"] == "Ausführliche Modellbeschreibung"
    assert design["images"] == [
        "https://makerworld.bblmw.com/one.webp",
        "https://makerworld.bblmw.com/two.webp",
    ]
    assert [item["id"] for item in instances] == ["9988", "8877"]
    assert instances[0]["is_default"] is True
    assert instances[0]["printer_model"] == "Bambu Lab A1"
    assert instances[0]["plates"][0]["id"] == "plate-1"
    assert instances[0]["plates"][0]["print_time_seconds"] == 7200


def test_account_context_reads_only_studio_entry_options() -> None:
    entry = SimpleNamespace(
        data={},
        options={"cloud_access_token": "placeholder", "cloud_region": "global"},
    )
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_entries=lambda domain: [entry] if domain == "ultimate_3d_studio" else []
        ),
        data={},
    )
    runtime = module.MakerWorldRuntime(hass)
    account = runtime._account()
    assert account.region == "global"
    assert account.api_base == "https://api.bambulab.com/v1"
    assert runtime._headers(account)["User-Agent"].startswith("Ultimate-3D-Studio/")


def test_missing_account_authorization_is_reported() -> None:
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_entries=lambda _domain: []),
        data={},
    )
    runtime = module.MakerWorldRuntime(hass)
    with pytest.raises(module.MakerWorldError, match="Kein Bambu-Kontozugang"):
        runtime._account()


@pytest.mark.asyncio
async def test_browse_uses_fallback_endpoint_until_designs_are_found() -> None:
    runtime = module.MakerWorldRuntime(SimpleNamespace())
    called: list[str] = []

    async def fake_json(path: str, _params):
        called.append(path)
        if path == "search-service/searchlist":
            return {"data": {"hits": []}}
        return browse_payload()

    runtime._json = fake_json
    result = await runtime.async_browse(query="benchy", limit=12)

    assert called == ["search-service/searchlist", "search-service/select/all"]
    assert result["source_endpoint"] == "search-service/select/all"
    assert result["items"][0]["id"] == "12345"


@pytest.mark.asyncio
async def test_detail_returns_complete_normalized_design() -> None:
    runtime = module.MakerWorldRuntime(SimpleNamespace())

    async def fake_json(_path: str, _params):
        return detail_payload()

    runtime._json = fake_json
    detail = await runtime.async_detail("12345")

    assert detail["id"] == "12345"
    assert detail["instance_count"] == 2
    assert detail["instances"][0]["plates"][0]["name"] == "Plate 1"


def test_invalid_design_and_instance_ids_are_rejected() -> None:
    assert module._design_id({"id": "../../../etc"}) == ""
    assert module._instance_id({"id": "with spaces"}) == ""


@pytest.mark.asyncio
async def test_search_pagination_continues_beyond_sixty_results() -> None:
    runtime = module.MakerWorldRuntime(SimpleNamespace())
    calls: list[int] = []

    async def fake_json(_path: str, params):
        offset = int(params.get("offset", 0))
        limit = int(params.get("limit", 60))
        calls.append(offset)
        total = 130
        hits = [
            {
                "designId": index + 1,
                "title": f"Model {index + 1}",
                "downloadCount": index + 10,
            }
            for index in range(offset, min(offset + limit, total))
        ]
        return {"data": {"total": total, "hits": hits}}

    runtime._json = fake_json
    first = await runtime.async_browse(query="holder", offset=0, limit=48)
    second = await runtime.async_browse(query="holder", offset=48, limit=48)
    third = await runtime.async_browse(query="holder", offset=96, limit=48)

    assert [item["id"] for item in first["items"]] == [str(value) for value in range(1, 49)]
    assert [item["id"] for item in second["items"]] == [str(value) for value in range(49, 97)]
    assert [item["id"] for item in third["items"]] == [str(value) for value in range(97, 131)]
    assert first["has_more"] is True
    assert second["has_more"] is True
    assert third["has_more"] is False
    assert third["total_count"] == 130
    assert calls == [0, 60, 120]
