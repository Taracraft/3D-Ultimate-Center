"""Two-step, telemetry-bound filament color writes for Studio."""
from __future__ import annotations

import asyncio
from secrets import token_urlsafe
from time import monotonic
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .a1_filament_catalog import filament_profile, generic_filament_profile
from .audit_log import get_audit_log
from .direct_print_slot_views import (
    API_PREFIX,
    _external_spool,
    _printer_ready,
    _runtimes,
    _slots,
)

_PREVIEW_TTL_SECONDS = 120.0
_PREVIEWS: dict[str, dict[str, Any]] = {}


def _error(status: int, code: str, message: str, **details: Any) -> web.Response:
    error: dict[str, Any] = {"code": code, "message": message}
    if details:
        error["details"] = details
    return web.json_response({"data": None, "error": error}, status=status)


def _admin_error(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return _error(403, "admin_required", "Administratorzugriff ist erforderlich.")
    return None


async def _json_object(request: web.Request) -> tuple[dict[str, Any] | None, web.Response | None]:
    try:
        payload = await request.json()
    except Exception:
        return None, _error(400, "invalid_json", "Der Request muss gültiges JSON enthalten.")
    if not isinstance(payload, dict):
        return None, _error(400, "invalid_json", "Der Request muss ein JSON-Objekt enthalten.")
    return payload, None


async def _find_runtime_and_printer(hass: HomeAssistant, printer_id: str):
    for runtime in _runtimes(hass):
        printer = await runtime.async_printer(printer_id)
        if printer is not None:
            return runtime, printer
    return None, None


def _hex_color(value: Any) -> str | None:
    raw = str(value or "").strip().lstrip("#")
    if len(raw) != 6 or any(character not in "0123456789abcdefABCDEF" for character in raw):
        return None
    return f"#{raw.lower()}"


def _temperature(value: Any) -> int | None:
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return result if 1 <= result <= 400 else None


def _snapshot(hass: HomeAssistant, printer: Any, kind: str, target_id: str) -> dict[str, Any]:
    if kind == "external_spool":
        item = _external_spool(hass, printer)
        if not item.get("available") or not item.get("loaded"):
            raise ValueError("Die externe Spule wird vom Drucker aktuell nicht als geladen gemeldet.")
        ams_id = 255
        tray_id = 0
        label = "Externe Spule"
    elif kind == "ams_slot":
        item = next((slot for slot in _slots(printer) if slot.get("global_id") == target_id), None)
        if item is None or not item.get("present"):
            raise ValueError("Das gewählte Materialfach ist nicht mehr belegt.")
        try:
            ams_id = int(str(item.get("unit_id", "")).strip())
            tray_id = int(item.get("slot_index"))
        except (TypeError, ValueError) as exc:
            raise ValueError("AMS- und Slotnummer konnten nicht sicher bestimmt werden.") from exc
        if not 0 <= ams_id <= 254 or not 0 <= tray_id <= 3:
            raise ValueError("AMS- oder Slotnummer liegt außerhalb des sicheren Bereichs.")
        label = f"AMS {ams_id + 1}, Fach {tray_id + 1}"
    else:
        raise ValueError("Unbekanntes Farbziel.")

    if item.get("rfid_detected"):
        raise ValueError("RFID-Filamente sind schreibgeschützt; deren Farbe kommt ausschließlich vom RFID-Tag.")
    material = str(item.get("material") or "").strip()
    minimum = _temperature(item.get("nozzle_temp_min"))
    maximum = _temperature(item.get("nozzle_temp_max"))
    if not material:
        raise ValueError("Das Material wird nicht eindeutig gemeldet; die Farbe wird nicht geschrieben.")
    if minimum is None or maximum is None or minimum > maximum:
        raise ValueError("Die Düsentemperaturen werden nicht vollständig gemeldet; die Farbe wird nicht geschrieben.")
    return {
        "kind": kind,
        "target_id": "external" if kind == "external_spool" else target_id,
        "label": label,
        "ams_id": ams_id,
        "tray_id": tray_id,
        "tray_info_idx": str(item.get("filament_id") or "").strip(),
        "tray_type": material,
        "nozzle_temp_min": minimum,
        "nozzle_temp_max": maximum,
        "current_color": _hex_color(item.get("color")),
    }


def _purge_previews() -> None:
    now = monotonic()
    for token, preview in tuple(_PREVIEWS.items()):
        if float(preview.get("expires_at", 0)) <= now:
            _PREVIEWS.pop(token, None)


class FilamentColorView(HomeAssistantView):
    url = f"{API_PREFIX}/filament-color"
    name = "api:ultimate_3d_studio:filament_color"
    requires_auth = True

    async def post(self, request: web.Request) -> web.Response:
        admin_error = _admin_error(request)
        if admin_error is not None:
            return admin_error
        payload, payload_error = await _json_object(request)
        if payload_error is not None:
            return payload_error
        assert payload is not None
        _purge_previews()
        if payload.get("confirmed") is True:
            return await self._apply(request.app["hass"], payload)
        return await self._preview(request.app["hass"], payload)

    async def _preview(self, hass: HomeAssistant, payload: dict[str, Any]) -> web.Response:
        printer_id = str(payload.get("printer_id") or "").strip()
        kind = str(payload.get("target_kind") or "").strip()
        target_id = str(payload.get("target_id") or "").strip()
        color = _hex_color(payload.get("color"))
        requested_id = str(payload.get("filament_id") or "").strip()
        profile = filament_profile(requested_id)
        if profile is None and not requested_id:
            profile = generic_filament_profile(payload.get("material_type"))
        if not printer_id or not kind or color is None or profile is None:
            return _error(
                400,
                "invalid_request",
                "Drucker, Farbziel, Farbe #RRGGBB und ein freigegebenes A1-Filamentprofil sind erforderlich.",
            )
        if kind not in profile["targets"]:
            return _error(
                409,
                "material_not_supported_by_target",
                "Dieses Filamentprofil ist für das gewählte Materialsystem nicht freigegeben.",
                filament_id=profile["id"],
                allowed_targets=profile["targets"],
            )
        material_type = str(profile["material_type"])
        runtime, printer = await _find_runtime_and_printer(hass, printer_id)
        if runtime is None or printer is None:
            return _error(404, "printer_not_found", "Der Drucker wurde nicht gefunden.")
        ready, reason = _printer_ready(printer)
        if not ready:
            return _error(409, "printer_not_ready", reason.replace("keinen neuen Druckauftrag", "keine Materialänderung"))
        try:
            target = _snapshot(hass, printer, kind, target_id)
        except ValueError as exc:
            return _error(409, "unsafe_color_target", str(exc))
        if (
            target["current_color"] == color
            and target["tray_info_idx"] == profile["id"]
            and target["tray_type"].upper() == material_type.upper()
        ):
            return _error(409, "filament_unchanged", "Hersteller, Filament und Farbe sind bereits am Drucker eingestellt.")
        settings = {
            **target,
            "tray_info_idx": profile["id"],
            "tray_type": material_type,
            "nozzle_temp_min": profile["nozzle_temp_min"],
            "nozzle_temp_max": profile["nozzle_temp_max"],
            "filament_name": profile["name"],
            "filament_vendor": profile["vendor"],
            "setting_id": profile["setting_id"],
        }
        token = token_urlsafe(24)
        _PREVIEWS[token] = {
            "expires_at": monotonic() + _PREVIEW_TTL_SECONDS,
            "printer_id": printer_id,
            "color": color,
            "material_type": material_type,
            "target": target,
            "settings": settings,
        }
        return web.json_response({"data": {
            "token": token,
            "expires_in_seconds": int(_PREVIEW_TTL_SECONDS),
            "printer_id": printer_id,
            "target_kind": kind,
            "target_id": target["target_id"],
            "target_label": target["label"],
            "current_color": target["current_color"],
            "new_color": color,
            "current_material": target["tray_type"],
            "new_material": material_type,
            "new_filament_id": profile["id"],
            "new_filament_name": profile["name"],
            "new_filament_vendor": profile["vendor"],
            "confirmation_text": "FARBE SETZEN",
            "confirmation_message": (
                f"{target['label']}: {target['tray_type']} / {target['current_color'] or 'unbekannt'} "
                f"auf {profile['vendor']} · {profile['name']} ({material_type}) / {color} am Drucker setzen? "
                "Es werden ausschließlich Werte aus dem offiziellen A1-Systemkatalog verwendet."
            ),
        }})

    async def _apply(self, hass: HomeAssistant, payload: dict[str, Any]) -> web.Response:
        token = str(payload.get("token") or "").strip()
        if str(payload.get("confirmation_text") or "").strip() != "FARBE SETZEN" or not token:
            return _error(409, "confirmation_required", "Vorschau-Token und Bestätigung FARBE SETZEN sind erforderlich.")
        preview = _PREVIEWS.pop(token, None)
        if preview is None or float(preview.get("expires_at", 0)) <= monotonic():
            return _error(409, "preview_expired", "Die Farbvorschau ist abgelaufen. Bitte erneut prüfen.")
        printer_id = str(preview["printer_id"])
        runtime, printer = await _find_runtime_and_printer(hass, printer_id)
        if runtime is None or printer is None:
            return _error(404, "printer_not_found", "Der Drucker wurde nicht gefunden.")
        ready, reason = _printer_ready(printer)
        if not ready:
            return _error(409, "printer_not_ready", reason.replace("keinen neuen Druckauftrag", "keine Materialänderung"))
        expected = preview["target"]
        settings = preview["settings"]
        try:
            current = _snapshot(hass, printer, expected["kind"], expected["target_id"])
        except ValueError as exc:
            return _error(409, "unsafe_color_target", str(exc))
        protected = ("ams_id", "tray_id", "tray_info_idx", "tray_type", "nozzle_temp_min", "nozzle_temp_max", "current_color")
        if any(current.get(field) != expected.get(field) for field in protected):
            return _error(409, "telemetry_changed", "Die Filamentdaten haben sich seit der Vorschau geändert. Bitte erneut prüfen.")
        await get_audit_log(hass).async_append(
            category="Material",
            component="filament_color",
            event="printer_color_write_requested",
            status="info",
            source="frontend_confirmed",
            printer_id=printer_id,
            details={
                "target": current["label"],
                "old_color": current["current_color"],
                "new_color": preview["color"],
                "old_material": current["tray_type"],
                "new_material": settings["tray_type"],
            },
        )
        try:
            result = await runtime.async_set_filament_color(
                printer_id,
                ams_id=current["ams_id"],
                tray_id=current["tray_id"],
                tray_info_idx=settings["tray_info_idx"],
                tray_color=preview["color"],
                nozzle_temp_min=settings["nozzle_temp_min"],
                nozzle_temp_max=settings["nozzle_temp_max"],
                tray_type=settings["tray_type"],
            )
        except (RuntimeError, ValueError) as exc:
            await get_audit_log(hass).async_append(
                category="Material",
                component="filament_color",
                event="printer_color_write_failed",
                status="error",
                source="bambu_lan",
                printer_id=printer_id,
                details={"target": current["label"], "error": str(exc)},
            )
            return _error(409, "printer_color_rejected", str(exc))
        if result is None:
            return _error(409, "printer_color_unsupported", "Der Druckerprovider unterstützt das Setzen der Farbe nicht.")

        telemetry_confirmed = False
        for _attempt in range(32):
            await asyncio.sleep(0.25)
            _runtime, refreshed = await _find_runtime_and_printer(hass, printer_id)
            if refreshed is None:
                break
            try:
                observed = _snapshot(hass, refreshed, current["kind"], current["target_id"])
            except ValueError:
                continue
            if (
                observed.get("current_color") == preview["color"]
                and observed.get("tray_info_idx") == settings["tray_info_idx"]
                and str(observed.get("tray_type") or "").upper() == settings["tray_type"].upper()
            ):
                telemetry_confirmed = True
                break
        await get_audit_log(hass).async_append(
            category="Material",
            component="filament_color",
            event="printer_color_write_completed",
            status="success" if telemetry_confirmed else "warning",
            source="bambu_lan",
            printer_id=printer_id,
            details={
                "target": current["label"],
                "old_color": current["current_color"],
                "new_color": preview["color"],
                "old_material": current["tray_type"],
                "new_material": settings["tray_type"],
                "printer_accepted": bool(result.get("accepted")),
                "telemetry_confirmed": telemetry_confirmed,
            },
        )
        return web.json_response({"data": result | {
            "target_label": current["label"],
            "old_color": current["current_color"],
            "new_color": preview["color"],
            "old_material": current["tray_type"],
            "new_material": settings["tray_type"],
            "new_filament_id": settings["tray_info_idx"],
            "new_filament_name": settings["filament_name"],
            "new_filament_vendor": settings["filament_vendor"],
            "telemetry_confirmed": telemetry_confirmed,
        }}, status=200 if telemetry_confirmed else 202)


def async_register_filament_color_views(hass: HomeAssistant) -> None:
    hass.http.register_view(FilamentColorView())
