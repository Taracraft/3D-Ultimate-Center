"""Telemetry normalization for Ultimate 3D Studio."""
from __future__ import annotations
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from .printer_issues import normalize_hms_item, normalize_print_error

_NORMAL_PRINT_STATES = frozenset({
    "running",
    "finish",
    "finished",
    "idle",
    "ready",
    "completed",
    "complete",
})
_ERROR_KEYS = (
    "print_error",
    "mc_print_error_code",
    "print_error_code",
    "error_code",
    "err_code",
)
_ERROR_MESSAGE_KEYS = (
    "print_error_message",
    "error_message",
    "error_msg",
    "fail_reason",
    "failure_reason",
)
_HMS_KEYS = ("hms", "hms_list", "health_messages")
_CLEAR_ERROR_VALUES = (None, "", 0, "0", "00000000")
_ERROR_STALE_GRACE_SECONDS = 15.0
_ERROR_STALE_CONFIRMATIONS = 3
_HMS_STALE_GRACE_SECONDS = 15.0
_HMS_STALE_CONFIRMATIONS = 3


def merge(target: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def find(payload: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(payload, dict):
        root = payload.get("print") if isinstance(payload.get("print"), dict) else payload
        for key in keys:
            if key in root:
                return root[key]
        for value in root.values():
            found = find(value, keys)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = find(value, keys)
            if found is not None:
                return found
    return None


def contains_key(payload: Any, keys: tuple[str, ...]) -> bool:
    if isinstance(payload, dict):
        root = payload.get("print") if isinstance(payload.get("print"), dict) else payload
        if any(key in root for key in keys):
            return True
        return any(contains_key(value, keys) for value in root.values())
    if isinstance(payload, list):
        return any(contains_key(value, keys) for value in payload)
    return False


def remove_keys(payload: Any, keys: tuple[str, ...]) -> None:
    if isinstance(payload, dict):
        for key in keys:
            payload.pop(key, None)
        for value in payload.values():
            remove_keys(value, keys)
    elif isinstance(payload, list):
        for value in payload:
            remove_keys(value, keys)


def number(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def text(value: Any, default: str = "unknown") -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return default
    result = str(value).strip()
    return result[:500] if result else default


def records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [item for item in value.values() if isinstance(item, dict)]
    return []


def pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def color(value: Any) -> str | None:
    raw = text(value, "").lstrip("#")
    if len(raw) == 8:
        raw = raw[:6]
    if len(raw) != 6 or any(char not in "0123456789abcdefABCDEF" for char in raw):
        return None
    return f"#{raw.upper()}"


def normalize_ams(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize AMS, AMS Lite and compatible third-party slot structures."""
    root = payload.get("print") if isinstance(payload.get("print"), dict) else payload
    ams = root.get("ams") if isinstance(root, dict) else None
    if not isinstance(ams, (dict, list)):
        ams = find(root, ("ams", "ams_list", "ams_data"))

    active_raw = find(root, ("tray_now", "ams_tray_now", "active_tray"))
    active_text = text(active_raw, "")
    active_tray = None if active_text in {"", "255", "-1", "none", "None"} else active_text

    units_source: Any = None
    if isinstance(ams, dict):
        units_source = ams.get("ams") or ams.get("units") or ams.get("data")
        if units_source is None and any(key in ams for key in ("tray", "trays", "slots", "tray_info")):
            units_source = [ams]
    elif isinstance(ams, list):
        units_source = ams

    units = records(units_source)
    if not units:
        standalone = find(root, ("tray", "trays", "slots", "tray_info"))
        if records(standalone):
            units = [{"id": "0", "model": "AMS Lite", "tray": standalone}]

    normalized_units: list[dict[str, Any]] = []
    all_slots: list[dict[str, Any]] = []

    for unit_index, unit in enumerate(units):
        unit_id = text(pick(unit, "id", "ams_id", "unit_id"), str(unit_index))
        unit_model = text(pick(unit, "model", "type", "name"), "AMS")
        unit_serial = text(pick(unit, "serial", "sn"), "")
        trays = records(unit.get("tray") or unit.get("trays") or unit.get("slots") or unit.get("tray_info") or [])
        normalized_slots: list[dict[str, Any]] = []

        for tray_index, tray in enumerate(trays):
            tray_id = text(pick(tray, "id", "tray_id", "slot_id", "tray_info_idx"), str(tray_index))
            global_id = f"{unit_id}:{tray_id}"
            material = text(pick(tray, "tray_type", "type", "filament_type"), "")
            slot_color = color(pick(tray, "tray_color", "color", "filament_color"))
            tag_uid = text(pick(tray, "tag_uid", "tag_id", "rfid"), "")
            present = bool(material or slot_color or (tag_uid and tag_uid != "0000000000000000"))
            remaining_raw = number(pick(tray, "remain", "remaining", "remain_percent", "remaining_percent"))
            remaining_reliable = remaining_raw is not None and not (
                remaining_raw == 0 and tag_uid == "0000000000000000"
            )
            slot = {
                "unit_id": unit_id,
                "slot_index": tray_index,
                "tray_id": tray_id,
                "filament_id": text(pick(tray, "tray_info_idx", "filament_id"), ""),
                "global_id": global_id,
                "active": active_tray is not None and active_tray in {tray_id, global_id, str(tray_index)},
                "material": material,
                "sub_brand": text(pick(tray, "tray_sub_brands", "sub_brand", "filament_sub_brand"), ""),
                "color": slot_color,
                "weight": number(pick(tray, "tray_weight", "weight", "remain_weight")),
                "diameter": number(pick(tray, "tray_diameter", "diameter")),
                "nozzle_temp_min": number(pick(tray, "nozzle_temp_min", "nozzle_temp_min_c")),
                "nozzle_temp_max": number(pick(tray, "nozzle_temp_max", "nozzle_temp_max_c")),
                "bed_temp": number(pick(tray, "bed_temp", "bed_temperature")),
                "remaining_percent": remaining_raw if remaining_reliable else None,
                "remaining_percent_raw": remaining_raw,
                "remaining_reliable": remaining_reliable,
                "tag_uid": tag_uid,
                "present": present,
            }
            normalized_slots.append(slot)
            all_slots.append(slot)

        normalized_units.append({
            "unit_id": unit_id,
            "model": unit_model,
            "serial": unit_serial,
            "humidity": number(pick(unit, "humidity", "ams_humidity")),
            "temperature": number(pick(unit, "temp", "temperature", "ams_temp")),
            "slots": normalized_slots,
            "slot_count": len(normalized_slots),
            "occupied_slot_count": sum(1 for slot in normalized_slots if slot["present"]),
        })

    occupied = sum(1 for slot in all_slots if slot["present"])
    is_lite_named = any("lite" in unit["model"].lower() for unit in normalized_units)
    is_unidentified_four_slot = (
        len(normalized_units) == 1
        and len(all_slots) == 4
        and not normalized_units[0]["serial"]
        and active_text in {"255", "-1", "", "none", "None"}
    )
    kind = "ams_lite" if is_lite_named else "ams_lite_compatible" if is_unidentified_four_slot else "ams"

    return {
        "available": bool(normalized_units or all_slots),
        "kind": kind,
        "unit_count": len(normalized_units),
        "slot_count": len(all_slots),
        "occupied_slot_count": occupied,
        "active_tray": active_tray,
        "active_tray_raw": active_text or None,
        "units": normalized_units,
        "slots": all_slots,
    }


class BambuTelemetryState:
    def __init__(self) -> None:
        self.raw: dict[str, Any] = {}
        self.updated_at: datetime | None = None
        self._last_error_at: datetime | None = None
        self._error_clear_candidate_at: datetime | None = None
        self._error_clear_confirmations = 0
        self._last_hms_at: datetime | None = None
        self._hms_clear_candidate_at: datetime | None = None
        self._hms_clear_confirmations = 0

    def update(
        self,
        payload: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> None:
        timestamp = now or datetime.now(UTC)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        timestamp = timestamp.astimezone(UTC)

        incoming_error_is_explicit = contains_key(payload, _ERROR_KEYS)
        incoming_error = find(payload, _ERROR_KEYS) if incoming_error_is_explicit else None
        error_was_explicitly_cleared = (
            incoming_error_is_explicit
            and incoming_error in _CLEAR_ERROR_VALUES
        )
        incoming_error_is_active = (
            incoming_error_is_explicit
            and not error_was_explicitly_cleared
        )
        incoming_hms_is_explicit = contains_key(payload, _HMS_KEYS)
        incoming_hms = records(find(payload, _HMS_KEYS)) if incoming_hms_is_explicit else []

        if incoming_error_is_active:
            # Different Bambu packets can use different error-key aliases. Drop
            # every retained alias first so the newly reported code is authoritative.
            remove_keys(self.raw, _ERROR_KEYS)
            remove_keys(self.raw, _ERROR_MESSAGE_KEYS)
            self._last_error_at = timestamp
            self._error_clear_candidate_at = None
            self._error_clear_confirmations = 0
        elif error_was_explicitly_cleared:
            remove_keys(self.raw, _ERROR_KEYS)
            remove_keys(self.raw, _ERROR_MESSAGE_KEYS)
            self._last_error_at = None
            self._error_clear_candidate_at = None
            self._error_clear_confirmations = 0

        if incoming_hms:
            self._last_hms_at = timestamp
            self._hms_clear_candidate_at = None
            self._hms_clear_confirmations = 0
        elif incoming_hms_is_explicit:
            remove_keys(self.raw, _HMS_KEYS)
            self._last_hms_at = None
            self._hms_clear_candidate_at = None
            self._hms_clear_confirmations = 0
        elif error_was_explicitly_cleared:
            remove_keys(self.raw, _HMS_KEYS)
            self._last_hms_at = None
            self._hms_clear_candidate_at = None
            self._hms_clear_confirmations = 0

        merge(self.raw, payload)

        has_retained_error = self.error_code is not None
        printer_is_normal = self.printer_state in _NORMAL_PRINT_STATES
        if (
            has_retained_error
            and not incoming_error_is_explicit
            and not incoming_hms
            and printer_is_normal
        ):
            if self._error_clear_candidate_at is None:
                self._error_clear_candidate_at = timestamp
                self._error_clear_confirmations = 1
            else:
                self._error_clear_confirmations += 1
            reference = self._last_error_at or self._error_clear_candidate_at
            age_seconds = (timestamp - reference).total_seconds()
            if (
                self._error_clear_confirmations >= _ERROR_STALE_CONFIRMATIONS
                and age_seconds >= _ERROR_STALE_GRACE_SECONDS
            ):
                remove_keys(self.raw, _ERROR_KEYS)
                remove_keys(self.raw, _ERROR_MESSAGE_KEYS)
                remove_keys(self.raw, _HMS_KEYS)
                self._last_error_at = None
                self._error_clear_candidate_at = None
                self._error_clear_confirmations = 0
                self._last_hms_at = None
                self._hms_clear_candidate_at = None
                self._hms_clear_confirmations = 0
        elif (
            not has_retained_error
            or incoming_error_is_explicit
            or bool(incoming_hms)
            or not printer_is_normal
        ):
            self._error_clear_candidate_at = None
            self._error_clear_confirmations = 0

        has_retained_hms = bool(records(find(self.raw, _HMS_KEYS)))
        if (
            has_retained_hms
            and not incoming_hms_is_explicit
            and self.error_code is None
        ):
            if self._hms_clear_candidate_at is None:
                self._hms_clear_candidate_at = timestamp
                self._hms_clear_confirmations = 1
            else:
                self._hms_clear_confirmations += 1
            reference = self._last_hms_at or self._hms_clear_candidate_at
            age_seconds = (timestamp - reference).total_seconds()
            if (
                self._hms_clear_confirmations >= _HMS_STALE_CONFIRMATIONS
                and age_seconds >= _HMS_STALE_GRACE_SECONDS
            ):
                remove_keys(self.raw, _HMS_KEYS)
                self._last_hms_at = None
                self._hms_clear_candidate_at = None
                self._hms_clear_confirmations = 0
        elif (
            not has_retained_hms
            or incoming_hms_is_explicit
            or self.error_code is not None
        ):
            self._hms_clear_candidate_at = None
            self._hms_clear_confirmations = 0

        self.updated_at = timestamp

    @property
    def model(self) -> str | None:
        value = text(find(self.raw, ("printer_type", "printer_model", "model", "dev_model_name")), "")
        return value or None

    @property
    def printer_state(self) -> str:
        return text(find(self.raw, ("gcode_state", "print_status", "state"))).lower()

    @property
    def progress(self) -> float | None:
        return number(find(self.raw, ("mc_percent", "print_percent", "progress", "percent")))

    @property
    def current_file(self) -> str | None:
        value = text(find(self.raw, ("subtask_name", "gcode_file", "task_name", "file")), "")
        return value or None

    @property
    def error_code(self) -> int | str | None:
        value = find(self.raw, _ERROR_KEYS)
        if value in _CLEAR_ERROR_VALUES:
            return None
        numeric = number(value)
        if numeric is not None and numeric.is_integer():
            return int(numeric)
        normalized = text(value, "")
        return normalized or None

    @property
    def hms(self) -> list[dict[str, Any]]:
        value = find(self.raw, _HMS_KEYS)
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        suppress_resolved_blocking = (
            self.printer_state in _NORMAL_PRINT_STATES
            and self.error_code is None
        )
        for item in records(value):
            normalized = normalize_hms_item(item)
            if normalized is None:
                continue
            if (
                suppress_resolved_blocking
                and bool(normalized.get("blocking", True))
                and normalized.get("severity") == "error"
            ):
                continue
            key = str(normalized.get("code") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            result.append(normalized)
        return result

    @property
    def error_message(self) -> str | None:
        direct = text(find(self.raw, (
            "print_error_message",
            "error_message",
            "error_msg",
            "fail_reason",
            "failure_reason",
        )), "")
        if direct and direct.casefold() not in {"ok", "success", "none", "0"}:
            return direct
        for item in self.hms:
            message = text(item.get("message"), "")
            if message:
                return message
        code = self.error_code
        return f"Druckerfehler {code}" if code is not None else None

    @property
    def issues(self) -> list[dict[str, Any]]:
        issues = [dict(item) for item in self.hms]
        existing_codes = {str(item.get("code_compact") or item.get("code") or "") for item in issues}
        code = self.error_code
        direct_error_message = text(find(self.raw, _ERROR_MESSAGE_KEYS), "")
        if direct_error_message.casefold() in {"ok", "success", "none", "0"}:
            direct_error_message = ""
        print_issue = normalize_print_error(code, direct_error_message) if code is not None else None
        if print_issue is not None:
            print_key = str(print_issue.get("code_compact") or print_issue.get("code") or "")
            if print_key not in existing_codes:
                issues.insert(0, print_issue)
        paused = self.printer_state in {"pause", "paused"}
        for issue in issues:
            issue["printer_state"] = self.printer_state
            issue["resume_supported"] = paused and bool(issue.get("blocking", True))
            issue["updated_at"] = self.updated_at_iso
        return issues

    @property
    def nozzle_temperature(self) -> float | None:
        return number(find(self.raw, ("nozzle_temper", "nozzle_temp")))

    @property
    def bed_temperature(self) -> float | None:
        return number(find(self.raw, ("bed_temper", "bed_temp")))

    @property
    def nozzle_target_temperature(self) -> float | None:
        return number(find(self.raw, ("nozzle_target_temper", "nozzle_target_temperature", "target_nozzle_temperature")))

    @property
    def bed_target_temperature(self) -> float | None:
        return number(find(self.raw, ("bed_target_temper", "bed_target_temperature", "target_bed_temperature")))

    @property
    def current_layer(self) -> int | None:
        value = number(find(self.raw, ("layer_num", "current_layer", "current_layer_num")))
        return None if value is None or value < 0 else int(value)

    @property
    def total_layers(self) -> int | None:
        value = number(find(self.raw, ("total_layer_num", "total_layers", "layer_count")))
        return None if value is None or value < 0 else int(value)

    @property
    def speed_level(self) -> int | None:
        value = number(find(self.raw, ("spd_lvl", "speed_level", "print_speed_level")))
        if value is None:
            return None
        level = int(value)
        return level if level in {1, 2, 3, 4} else None

    @property
    def wifi_signal(self) -> int | None:
        value = number(find(self.raw, ("wifi_signal", "wifi_signal_strength", "rssi")))
        return None if value is None else int(value)

    @property
    def ams(self) -> dict[str, Any]:
        return normalize_ams(self.raw)

    @property
    def updated_at_iso(self) -> str | None:
        return self.updated_at.isoformat() if self.updated_at else None
