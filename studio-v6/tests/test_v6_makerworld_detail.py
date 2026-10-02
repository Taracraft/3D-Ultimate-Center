"""Regression tests for the V6 MakerWorld detail endpoint."""
from __future__ import annotations

import importlib.util
import asyncio
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


def test_recommendation_preserves_normalized_search_media_and_statistics() -> None:
    item = {
        "id": "456",
        "title": "Related model",
        "creator": "Designer",
        "thumbnail_url": "https://makerworld.bblmw.com/related.jpg",
        "stats": {"likes": 7, "downloads": 42, "comments": 3, "collects": 8, "prints": 11},
    }
    assert detail_module._recommendations({"items": [item]}) == [item]


def test_recommendation_uses_public_id_and_does_not_turn_metadata_into_models() -> None:
    payload = {"data": [{
        "id": 456, "modelId": "opaque-download-id", "title": "Related model",
        "designCreator": {"id": 99, "name": "Designer"},
        "instances": [{"id": 88, "title": "Print profile"}],
    }, {"id": "opaque-id", "title": "Invalid card"}]}
    cards = detail_module._recommendations(payload)
    assert [card["id"] for card in cards] == ["456"]
    assert cards[0]["creator"] == "Designer"


def test_embedded_recommendations_survive_and_exclude_current_model_and_duplicates() -> None:
    payload = current_detail_payload()
    payload["data"]["recommendations"] = [
        {"id": 2887138, "title": "Self"},
        {"id": 456, "title": "Related model"},
        {"id": 456, "title": "Duplicate"},
    ]
    result = detail_module._normalize(payload, "2887138")
    assert [item["id"] for item in result["recommendations"]] == ["456"]


@pytest.mark.asyncio
async def test_recommendations_merge_embedded_direct_and_search_results() -> None:
    payload = current_detail_payload()
    payload["data"]["recommendations"] = [{"id": 456, "title": "Embedded"}]

    class Runtime:
        async def _json(self, path, _params):
            if path == "design-service/design/2887138":
                return payload
            if "comment-service" in path:
                return {}
            return {"items": [{"id": 456, "title": "Duplicate"}, {"id": 789, "title": "Direct"}]}

        async def async_browse(self, **_kwargs):
            return {"items": [{"id": "111", "title": "Fallback", "thumbnail_url": "https://example.com/model.jpg", "stats": {"downloads": 12}}]}

    result = await detail_module.async_load_detail(Runtime(), "2887138")
    assert [item["id"] for item in result["recommendations"]] == ["456", "789", "111"]
    assert result["recommendations"][-1]["stats"]["downloads"] == 12


@pytest.mark.asyncio
async def test_optional_enrichment_is_bounded_keeps_partial_results_and_never_retries_detail(monkeypatch) -> None:
    for name in ("_COMMENTS_TIMEOUT", "_RECOMMENDATIONS_TIMEOUT", "_FALLBACK_TIMEOUT"):
        monkeypatch.setattr(detail_module, name, 0.02)
    payload = current_detail_payload()
    payload["data"]["comments"] = [{"commentId": "embedded", "content": "Already supplied"}]
    payload["data"]["recommendations"] = [{"id": 456, "title": "Embedded"}]
    detail_calls = 0
    recommendation_calls = 0
    comment_calls = 0

    class Runtime:
        async def _json(self, path, _params):
            nonlocal detail_calls, recommendation_calls, comment_calls
            if path == "design-service/design/2887138":
                detail_calls += 1
                return payload
            if "comment-service" in path:
                comment_calls += 1
                if comment_calls == 1:
                    return {"comments": [{"commentId": "extra", "content": "Extra comment"}]}
            else:
                recommendation_calls += 1
                if recommendation_calls == 1:
                    return {"items": [{"id": 789, "title": "Partial direct result"}]}
            await asyncio.sleep(10)
            raise AssertionError("Slow request must be cancelled")

        async def async_browse(self, **_kwargs):
            await asyncio.sleep(10)
            raise AssertionError("Slow fallback must be cancelled")

    result = await asyncio.wait_for(detail_module.async_load_detail(Runtime(), "2887138"), timeout=1)
    assert detail_calls == 1
    assert [item["id"] for item in result["recommendations"]] == ["456", "789"]
    assert [item["id"] for item in result["comments"]] == ["embedded", "extra"]
    assert result["instances"][0]["id"] == "US123456789"


@pytest.mark.asyncio
async def test_full_embedded_recommendations_do_not_trigger_redundant_search() -> None:
    payload = current_detail_payload()
    payload["data"]["recommendations"] = [{"id": str(i), "title": f"Model {i}"} for i in range(100, 112)]

    class Runtime:
        async def _json(self, path, _params):
            if path == "design-service/design/2887138":
                return payload
            assert path.startswith("comment-service/")
            return {}

        async def async_browse(self, **_kwargs):
            raise AssertionError("Complete embedded recommendations need no browse request")

    result = await detail_module.async_load_detail(Runtime(), "2887138")
    assert len(result["recommendations"]) == 12


@pytest.mark.asyncio
async def test_cancelling_detail_request_propagates_to_optional_operations() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class Runtime:
        async def _json(self, path, _params):
            if path == "design-service/design/2887138":
                return current_detail_payload()
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                cancelled.set()
                raise

    task = asyncio.create_task(detail_module.async_load_detail(Runtime(), "2887138"))
    await asyncio.wait_for(started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


def test_nested_profile_metadata_and_printer_variants_keep_distinct_plate_data() -> None:
    raw = {"id": 42, "title": "Fixture", "instances": [{
        "id": 12, "profileId": 100, "title": "Process", "isDefault": True,
        "extention": {"modelInfo": {
            "compatibility": {"devProductName": "X1 Carbon", "nozzleDiameter": 0.4},
            "plates": [{"index": 1, "prediction": 3600, "weight": 25}]},
            "otherCompatibilityModelInfo": [{"profileId": 101, "devProductName": "A1",
                "modelInfo": {"compatibility": {"devProductName": "A1", "nozzleDiameter": 0.6},
                              "plates": [{"index": 1, "prediction": 4200, "weight": 26}]}}]}}]}
    profiles = detail_module._instances(raw, raw, "42")
    assert len(profiles) == 2
    primary = next(p for p in profiles if p["id"] == "100")
    variant = next(p for p in profiles if p["id"] == "101")
    assert primary["printer_model"] == "X1 Carbon"
    assert primary["nozzle_diameter"] == "0.4"
    assert primary["is_default"]
    assert variant["printer_model"] == "A1"
    assert variant["nozzle_diameter"] == "0.6"
    assert not variant["is_default"]
    assert variant["plates"][0]["print_time_seconds"] == 4200
    assert primary["plates"][0]["weight_grams"] == 25


def test_profile_scope_excludes_recommendations_and_foreign_designs() -> None:
    raw = {"id": 42, "title": "Fixture", "instances": [
        {"profileId": 100, "title": "Own"},
        {"profileId": 200, "title": "Foreign", "designId": 99}],
        "recommendations": [{"id": 99, "title": "Other", "instances": [{"profileId": 300}]}]}
    assert [p["id"] for p in detail_module._instances(raw, raw, "42")] == ["100"]


def test_json_extension_and_plain_description_paragraphs_are_preserved() -> None:
    raw = {"id": 42, "title": "Fixture", "summary": "First\n\nSecond", "instances": [
        {"profileId": 100, "extention": '{"modelInfo":{"compatibility":{"devProductName":"P1S"},"plates":[{"prediction":60}]}}'}]}
    detail = detail_module._normalize(raw, "42")
    assert detail["description"] == "First\n\nSecond"
    assert detail["instances"][0]["printer_model"] == "P1S"
    assert detail["instances"][0]["plate_count"] == 1
