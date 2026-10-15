"""Detailed read-only AMS and RFID status for the Studio user interface."""
from __future__ import annotations

from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .a1_filament_catalog import CATALOG_SOURCE, CATALOG_VERSION, catalog_payload
from .const import DATA_RUNTIMES, DOMAIN
from .runtime import Ultimate3DStudioRuntime

API_PREFIX = "/api/ultimate_3d_studio/v1/slicer"
_SAFE_START_STATES = {"idle", "finish", "finished", "complete", "completed", "success", "ready", "standby", "failed"}
_EMPTY_TAGS = {"", "0000000000000000", "unknown", "none"}


def _runtimes(hass: HomeAssistant) -> list[Ultimate3DStudioRuntime]:
    domain_data = hass.data.get(DOMAIN, {})
    values = domain_data.get(DATA_RUNTIMES, {}) if isinstance(domain_data, dict) else {}
    return [
        item
        for item in values.values()
        if isinstance(item, Ultimate3DStudioRuntime)
    ] if isinstance(values, dict) else []


def _printer_ready(printer: Any) -> tuple[bool, str]:
    if str(printer.connection_state).casefold() != "connected":
        return False, "Drucker ist nicht verbunden."
    state = str(printer.printer_state or "unknown").casefold()
    if state not in _SAFE_START_STATES:
        return False, f"Druckerzustand '{state}' erlaubt derzeit keinen neuen Druckauftrag."
    return True, ""


def _number(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def _normalized_color(value: Any) -> str | None:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) >= 6 and all(character in "0123456789abcdefABCDEF" for character in raw[:6]):
        return f"#{raw[:6].lower()}"
    return None


def _external_spool(hass: HomeAssistant, printer: Any) -> dict[str, Any]:
    printer_key = "".join(character.lower() if character.isalnum() else "_" for character in str(printer.printer_id))
    entity_id = f"sensor.{printer_key}_external_spool_external_spool"
    state = hass.states.get(entity_id)
    if state is None:
        candidates = [
            hass.states.get(candidate)
            for candidate in hass.states.async_entity_ids("sensor")
            if candidate.endswith("_external_spool_external_spool") and printer_key in candidate
        ]
        state = next((candidate for candidate in candidates if candidate is not None), None)
    if state is None:
        return {
            "available": False,
            "loaded": False,
            "entity_id": None,
            "tray_id": "",
            "filament_id": "",
            "material": "",
            "sub_brand": "",
            "color": None,
            "remaining_percent": None,
            "remaining_reliable": False,
            "weight": None,
            "diameter": None,
            "nozzle_temp_min": None,
            "nozzle_temp_max": None,
            "bed_temp": None,
            "tag_uid": "",
            "rfid_detected": False,
            "rfid_status": "not_detected",
        }

    attributes = state.attributes
    raw_state = str(state.state or "").strip()
    material = str(attributes.get("normalized_material") or raw_state).strip()
    if material.casefold() in {"", "unknown", "unavailable", "none", "null"}:
        material = ""
    tag_uid = str(attributes.get("tag_uid") or attributes.get("tray_uuid") or "").strip()
    tag_key = tag_uid.casefold()
    loaded = attributes.get("normalized_loaded") is True
    return {
        "available": raw_state.casefold() not in {"unknown", "unavailable"},
        "loaded": loaded,
        "entity_id": state.entity_id,
        "tray_id": str(attributes.get("id") or attributes.get("tray_id") or "254").strip(),
        "filament_id": str(attributes.get("filament_id") or attributes.get("tray_info_idx") or "").strip(),
        "material": material,
        "sub_brand": str(attributes.get("normalized_brand") or attributes.get("tray_sub_brands") or "").strip(),
        "color": _normalized_color(attributes.get("normalized_color") or attributes.get("tray_color")),
        "remaining_percent": _number(attributes.get("normalized_remaining")),
        "remaining_reliable": False,
        "weight": _number(attributes.get("normalized_weight") or attributes.get("weight")),
        "diameter": _number(attributes.get("tray_diameter") or attributes.get("diameter")),
        "nozzle_temp_min": _number(attributes.get("nozzle_temp_min") or attributes.get("nozzle_temperature_min")),
        "nozzle_temp_max": _number(attributes.get("nozzle_temp_max") or attributes.get("nozzle_temperature_max")),
        "bed_temp": _number(attributes.get("bed_temp") or attributes.get("bed_temperature")),
        "tag_uid": tag_uid,
        "rfid_detected": tag_key not in _EMPTY_TAGS,
        "rfid_status": "detected" if tag_key not in _EMPTY_TAGS else "not_detected",
    }


def _slots(printer: Any) -> list[dict[str, Any]]:
    ams = printer.ams if isinstance(getattr(printer, "ams", None), dict) else {}
    result: list[dict[str, Any]] = []
    for slot in ams.get("slots", []):
        if not isinstance(slot, dict):
            continue
        slot_index = int(slot.get("slot_index", 0) or 0)
        tag_uid = str(slot.get("tag_uid", "") or "").strip()
        tag_key = tag_uid.casefold()
        result.append({
            "global_id": str(slot.get("global_id", "")),
            "slot_index": slot_index,
            "display_slot": slot_index + 1,
            "tray_id": str(slot.get("tray_id", "")),
            "filament_id": str(slot.get("filament_id", "")),
            "unit_id": str(slot.get("unit_id", "")),
            "material": str(slot.get("material", "")),
            "sub_brand": str(slot.get("sub_brand", "")),
            "color": slot.get("color"),
            "present": bool(slot.get("present")),
            "active": bool(slot.get("active")),
            "remaining_percent": _number(slot.get("remaining_percent")),
            "remaining_reliable": bool(slot.get("remaining_reliable")),
            "weight": _number(slot.get("weight")),
            "diameter": _number(slot.get("diameter")),
            "nozzle_temp_min": _number(slot.get("nozzle_temp_min")),
            "nozzle_temp_max": _number(slot.get("nozzle_temp_max")),
            "bed_temp": _number(slot.get("bed_temp")),
            "tag_uid": tag_uid,
            "rfid_detected": tag_key not in _EMPTY_TAGS,
            "rfid_status": "detected" if tag_key not in _EMPTY_TAGS else "not_detected",
        })
    return result


class DirectPrintDetailedStatusView(HomeAssistantView):
    url = f"{API_PREFIX}/direct-print/status-detailed"
    name = "api:ultimate_3d_studio:direct_print_status_detailed"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        items = []
        for runtime in _runtimes(hass):
            for printer in await runtime.async_printers():
                ready, reason = _printer_ready(printer)
                ams = printer.ams if isinstance(printer.ams, dict) else {}
                items.append({
                    "printer_id": printer.printer_id,
                    "name": printer.name,
                    "provider": printer.provider,
                    "connection_state": printer.connection_state,
                    "printer_state": printer.printer_state,
                    "ready": ready,
                    "reason": reason or None,
                    "external_spool": _external_spool(hass, printer),
                    "ams": {
                        "available": bool(ams.get("available")),
                        "kind": ams.get("kind"),
                        "unit_count": int(ams.get("unit_count", 0) or 0),
                        "slot_count": int(ams.get("slot_count", 0) or 0),
                        "occupied_slot_count": int(ams.get("occupied_slot_count", 0) or 0),
                        "slots": _slots(printer),
                    },
                })
        return web.json_response({
            "data": {
                "items": items,
                "filament_catalog": {
                    "source": CATALOG_SOURCE,
                    "version": CATALOG_VERSION,
                    "items": catalog_payload(),
                },
                "two_step_confirmation": True,
                "slot_numbering": "display_one_based_worker_zero_based",
                "rfid_refresh_mode": "telemetry_sync",
            }
        })


def async_register_direct_print_slot_views(hass: HomeAssistant) -> None:
    hass.http.register_view(DirectPrintDetailedStatusView())
