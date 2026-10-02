"""Regression tests for the V6 MakerWorld detail endpoint."""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)

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
    "ultimate_3d_studio_v6",
    types.ModuleType("ultimate_3d_studio_v6"),
)
package.__path__ = [str(COMPONENT)]
const = sys.modules.setdefault(
    "ultimate_3d_studio_v6.const",
    types.ModuleType("ultimate_3d_studio_v6.const"),
)
for key, value in {
    "CONF_CLOUD_ACCESS_TOKEN": "cloud_access_token",
    "CONF_CLOUD_REGION": "cloud_region",
    "DOMAIN": "ultimate_3d_studio_v6",
    "REGION_CHINA": "china",
    "REGION_GLOBAL": "global",
    "VERSION": "6.0.0-test",
}.items():
    setattr(const, key, value)

runtime_name = "ultimate_3d_studio_v6.makerworld_runtime"
if runtime_name not in sys.modules:
    runtime_spec = importlib.util.spec_from_file_location(
        runtime_name,
        COMPONENT / "makerworld_runtime.py",
    )
    assert runtime_spec and runtime_spec.loader
    runtime_module = importlib.util.module_from_spec(runtime_spec)
    sys.modules[runtime_name] = runtime_module
    runtime_spec.loader.exec_module(runtime_module)
else:
    runtime_module = sys.modules[runtime_name]

detail_name = "ultimate_3d_studio_v6.makerworld_detail"
detail_spec = importlib.util.spec_from_file_location(
    detail_name,
    COMPONENT / "makerworld_detail.py",
)
assert detail_spec and detail_spec.loader
detail_module = importlib.util.module_from_spec(detail_spec)
sys.modules[detail_name] = detail_module
detail_spec.loader.exec_module(detail_module)


def current_detail_payload() -> dict:
    return {
        "data": {
            "id": 2887138,
            "modelId": "model-2887138-current",
            "title": "Current MakerWorld Test Model",
            "description": "Full MakerWorld detail text",
            "designCreator": {
                "name": "Current API Designer",
                "avatar": "https://makerworld.bblmw.com/avatar.png",
            },
            "images": [
                {"url": "https://makerworld.bblmw.com/design-1.jpg"},
                {"url": "https://makerworld.bblmw.com/design-2.jpg"},
            ],
            "tags": [{"name": "Mechanical"}, {"name": "Print in place"}],
            "likeCount": 2851,
            "downloadCount": 1654,
            "commentCount": 41,
            "printCount": 357,
            "instances": [
                {
                    "id": "US123456789",
                    "name": "0.20 mm Standard",
                    "isDefault": True,
                    "printerModel": "Bambu Lab A1",
                    "nozzleDiameter": "0.4",
                    "images": [
                        {"url": "https://makerworld.bblmw.com/profile.jpg"}
                    ],
                    "plates": [
                        {
                            "id": "plate-1",
                            "index": 0,
                            "name": "Druckplatte 1",
                            "thumbnailUrl": "https://makerworld.bblmw.com/plate.jpg",
                            "prediction": 3600,
                            "filamentWeight": 22,
                        }
                    ],
                }
            ],
        }
    }


def test_current_detail_shape_normalizes_creator_instances_and_plates() -> None:
    detail = detail_module._normalize(current_detail_payload(), "2887138")

    assert detail["id"] == "2887138"
    assert detail["creator"] == "Current API Designer"
    assert detail["instance_count"] == 1
    assert detail["instances"][0]["id"] == "US123456789"
    assert detail["instances"][0]["printer_model"] == "Bambu Lab A1"
    assert detail["instances"][0]["plates"][0]["print_time_seconds"] == 3600
    assert detail["instances"][0]["plates"][0]["weight_grams"] == 22


def test_detail_wrapper_without_repeated_id_is_enriched() -> None:
    payload = {
        "result": {
            "title": "Wrapped model",
            "designCreator": {"nickname": "Wrapped Creator"},
            "instances": [],
        }
    }
    detail = detail_module._normalize(payload, "987654")
    assert detail["id"] == "987654"
    assert detail["title"] == "Wrapped model"
    assert detail["creator"] == "Wrapped Creator"


@pytest.mark.asyncio
async def test_detail_retries_with_browse_variants_before_failing() -> None:
    calls: list[dict[str, str]] = []

    class Runtime:
        async def _json(self, _path: str, params: dict[str, str]):
            calls.append(dict(params))
            if len(calls) == 1:
                raise runtime_module.MakerWorldError("temporary variant rejection")
            return current_detail_payload()

    result = await detail_module.async_load_detail(Runtime(), "2887138")

    assert result["title"] == "Current MakerWorld Test Model"
    assert calls[:2] == [
        {"trafficSource": "browse", "visitHistory": "true"},
        {"trafficSource": "browse", "visitHistory": "false"},
    ]


@pytest.mark.asyncio
async def test_detail_accepts_parameterless_fallback() -> None:
    calls: list[dict[str, str]] = []

    class Runtime:
        async def _json(self, _path: str, params: dict[str, str]):
            calls.append(dict(params))
            if params:
                raise runtime_module.MakerWorldError("variant rejected")
            return current_detail_payload()

    result = await detail_module.async_load_detail(Runtime(), "2887138")
    assert result["instance_count"] == 1
    assert {} in calls
    assert calls[:5] == [
        {"trafficSource": "browse", "visitHistory": "true"},
        {"trafficSource": "browse", "visitHistory": "false"},
        {"trafficSource": "recommend", "visitHistory": "false"},
        {"trafficSource": "search", "visitHistory": "false"},
        {},
    ]


@pytest.mark.asyncio
async def test_invalid_detail_id_is_rejected_before_request() -> None:
    class Runtime:
        async def _json(self, _path: str, _params: dict[str, str]):
            raise AssertionError("request must not be sent")

    with pytest.raises(ValueError, match="Ungültige MakerWorld-Modell-ID"):
        await detail_module.async_load_detail(Runtime(), "invalid")
