"""Data model and telemetry helpers."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .const import (
    AMS_NONE,
    AMS_LITE,
    AMS_ORIGINAL,
    AMS_2_PRO,
    AMS_HT,
    AMS_BMCU_370,
    AMS_4_SLOT_COMPATIBLE,
)

from .bambu_standalone import (
    extract_print_value,
    extract_ams_summary,
    get_model_capabilities,
)


def print_data(data: dict[str, Any]) -> dict[str, Any]:
    candidate = data.get("print")
    return candidate if isinstance(candidate, dict) else data


def deep_merge(target: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge partial MQTT payloads without losing prior telemetry."""
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)
    return target


def safe_state(value: Any, default: str = "unknown", limit: int = 240) -> str:
    """Convert MQTT values to a valid Home Assistant state string."""
    if value is None:
        return default
    if isinstance(value, (dict, list, tuple, set)):
        return default
    text = str(value)
    return text[:limit] if text else default


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if value == "unknown":
        return True
    if value == "unavailable":
        return True
    return False


def _set_if_present(target: dict[str, Any], key: str, value: Any, overwrite_empty_only: bool = True) -> None:
    if _is_empty(value):
        return
    if overwrite_empty_only and not _is_empty(target.get(key)):
        return
    target[key] = value


def _as_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _flatten_text(value: Any) -> str:
    try:
        return repr(value).lower()
    except Exception:
        return ""


def _printer_family_label(model_text: Any) -> str:
    capabilities = get_model_capabilities(str(model_text or ""))
    return capabilities.family.value


def detect_ams_type(data: dict[str, Any]) -> tuple[str, str]:
    """Best-effort AMS type detection using only our own parsed printer payload."""
    p = print_data(data)
    ams = p.get("ams")
    summary = extract_ams_summary({"print": p})

    raw = _flatten_text(ams)
    summary_raw = _flatten_text(summary)
    combined = f"{raw} {summary_raw}"

    if "bmcu" in combined or "bcmu" in combined:
        return AMS_BMCU_370, "high"
    if "ams ht" in combined or "ams_ht" in combined:
        return AMS_HT, "high"
    if "ams 2 pro" in combined or "ams2" in combined or "ams_2_pro" in combined:
        return AMS_2_PRO, "high"
    if "ams lite" in combined or "ams_lite" in combined:
        return AMS_LITE, "high"

    if summary.get("has_ams"):
        unit_count = int(summary.get("unit_count") or 0)
        tray_count = 0
        for unit in summary.get("units") or []:
            if isinstance(unit, dict):
                trays = unit.get("trays") or []
                if isinstance(trays, list):
                    tray_count += len(trays)
        if tray_count == 4:
            return AMS_4_SLOT_COMPATIBLE, "high"
        if unit_count > 0:
            return AMS_ORIGINAL, "medium"

    units: list[Any] = []
    if isinstance(ams, dict):
        maybe_units = ams.get("ams")
        if isinstance(maybe_units, list):
            units = maybe_units
    elif isinstance(ams, list):
        units = ams

    if not units:
        return AMS_NONE, "medium"

    tray_count = 0
    for unit in units:
        if isinstance(unit, dict) and isinstance(unit.get("tray"), list):
            tray_count += len(unit["tray"])

    if tray_count == 4:
        return AMS_4_SLOT_COMPATIBLE, "high"

    return AMS_ORIGINAL, "low"


def normalize_color(value: Any, default: str = "#4a5568") -> str:
    """Normalize AMS tray color values to #RRGGBB."""
    if value is None:
        return default

    if isinstance(value, dict):
        for key in ("hex", "rgb", "rgba", "color", "tray_color"):
            if key in value:
                return normalize_color(value[key], default)
        return default

    if isinstance(value, (list, tuple)):
        if value and isinstance(value[0], str):
            return normalize_color(value[0], default)
        if len(value) >= 3:
            try:
                return "#{:02X}{:02X}{:02X}".format(
                    max(0, min(255, int(value[0]))),
                    max(0, min(255, int(value[1]))),
                    max(0, min(255, int(value[2]))),
                )
            except (TypeError, ValueError):
                return default

    text = str(value).strip().replace("#", "")
    if text.lower().startswith("0x"):
        text = text[2:]

    # Bambu payloads frequently use RRGGBBAA. Alpha is ignored for the UI.
    if len(text) >= 6 and all(char in "0123456789abcdefABCDEF" for char in text[:6]):
        return f"#{text[:6].upper()}"

    return default


def normalize_tray(raw: dict[str, Any]) -> dict[str, Any]:
    """Add stable UI fields while preserving raw MQTT attributes."""
    tray = dict(raw or {})

    material = (
        tray.get("normalized_material")
        or tray.get("tray_type")
        or tray.get("filament_type")
        or tray.get("material")
        or tray.get("type")
        or tray.get("tray_info_idx")
        or ""
    )
    brand = (
        tray.get("normalized_brand")
        or tray.get("tray_sub_brands")
        or tray.get("sub_brand")
        or tray.get("brand")
        or tray.get("name")
        or ""
    )
    remaining = (
        tray.get("remain")
        if tray.get("remain") not in (None, "")
        else tray.get("remaining")
    )
    raw_color = (
        tray.get("tray_color")
        or tray.get("color")
        or tray.get("rgba")
        or tray.get("rgb")
        or tray.get("tray_color_rgb")
        or tray.get("cols")
    )

    meaningful = any(
        tray.get(key) not in (None, "", "0", 0, "empty", "unknown")
        for key in (
            "tray_type",
            "filament_type",
            "material",
            "tray_info_idx",
            "tray_color",
            "color",
            "tag_uid",
            "tray_sub_brands",
            "brand",
        )
    )

    tray["normalized_material"] = safe_state(material, default="loaded")
    tray["normalized_brand"] = safe_state(brand, default="")
    tray["normalized_color"] = normalize_color(raw_color)
    tray["normalized_remaining"] = remaining
    tray["normalized_loaded"] = bool(meaningful)
    return tray


_STANDARD_VALUE_MAP: dict[str, tuple[str, ...]] = {
    "printer_model": ("printer_model",),
    "serial": ("serial",),
    "firmware_version": ("firmware",),
    "wifi_signal": ("wifi_signal",),
    "gcode_state": ("print_status",),
    "stg_cur": ("current_stage",),
    "subtask_name": ("task_name",),
    "gcode_file": ("task_name",),
    "nozzle_temper": ("nozzle_temperature",),
    "nozzle_target_temper": ("nozzle_target_temperature",),
    "nozzle_diameter": ("nozzle_diameter",),
    "nozzle_type": ("nozzle_type",),
    "bed_temper": ("bed_temperature",),
    "bed_target_temper": ("bed_target_temperature",),
    "chamber_temper": ("chamber_temperature",),
    "chamber_target_temper": ("chamber_target_temperature",),
    "mc_percent": ("progress_percent",),
    "mc_remaining_time": ("remaining_time_minutes",),
    "layer_num": ("current_layer",),
    "total_layer_num": ("total_layers",),
    "spd_lvl": ("speed_level",),
    "sdcard": ("sdcard_state",),
    "home_flag": ("home_flag",),
    "fun": ("print_fun",),
}


@dataclass
class PrinterSnapshot:
    online: bool = False
    transport: str = "disconnected"
    telemetry: dict[str, Any] = field(default_factory=dict)
    detected_ams_type: str = AMS_NONE
    detection_confidence: str = "unknown"

    def update(self, telemetry: dict[str, Any], transport: str) -> None:
        deep_merge(self.telemetry, telemetry)
        self.transport = transport
        self.online = True
        self._normalize_standalone_payload()
        self.detected_ams_type, self.detection_confidence = detect_ams_type(self.telemetry)

    @property
    def print(self) -> dict[str, Any]:
        return print_data(self.telemetry)

    @property
    def printer_model(self) -> str:
        return safe_state(
            self.value("printer_model", "dev_model_name", "machine_model", default=""),
            default="",
        )

    @property
    def printer_family(self) -> str:
        return _printer_family_label(self.printer_model)

    def _normalize_standalone_payload(self) -> None:
        """Normalize A1/P1/X1/H2 payload differences into stable PCC keys."""
        p = self.print
        if not isinstance(p, dict):
            return

        for target_key, source_keys in _STANDARD_VALUE_MAP.items():
            for source_key in source_keys:
                value = extract_print_value({"print": p}, source_key)
                if _is_empty(value):
                    value = extract_print_value(self.telemetry, source_key)
                if not _is_empty(value):
                    _set_if_present(p, target_key, value)
                    break

        # Make get_version/module payloads useful for the firmware sensor.
        firmware = p.get("firmware_version") or extract_print_value(self.telemetry, "firmware")
        _set_if_present(p, "firmware_version", firmware)
        _set_if_present(p, "upgrade_display_state", firmware)

        model = p.get("printer_model") or extract_print_value(self.telemetry, "printer_model")
        _set_if_present(p, "printer_model", model)

        # Store our normalized AMS summary without destroying the raw Bambu AMS tree.
        try:
            summary = extract_ams_summary({"print": p})
        except Exception:
            summary = {"has_ams": False, "unit_count": 0, "units": []}
        self.telemetry["_pcc_ams_summary"] = summary

    def value(self, *keys: str, default: Any = None) -> Any:
        for key in keys:
            if key in self.print:
                return self.print.get(key)
            if key in self.telemetry:
                return self.telemetry.get(key)
        return default

    def firmware_state(self) -> str:
        direct = self.value("firmware_version", "sw_ver", "ota_version", default=None)
        if direct not in (None, ""):
            return safe_state(direct)

        display = self.value("upgrade_display_state", default=None)
        if display not in (None, ""):
            return safe_state(display)

        raw = self.value("upgrade_state", default=None)
        if isinstance(raw, dict):
            return safe_state(
                raw.get("status")
                or raw.get("message")
                or raw.get("module")
                or raw.get("version")
                or "unknown"
            )
        return safe_state(raw)

    def firmware_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        for key in ("firmware_version", "sw_ver", "ota_version", "hardware", "hw_ver"):
            value = self.value(key, default=None)
            if value not in (None, ""):
                attrs[key] = value

        raw = self.value("upgrade_state", default={})
        if isinstance(raw, dict):
            attrs.update(raw)

        version_payload = self.value("get_version", default={})
        if isinstance(version_payload, dict):
            attrs["get_version"] = version_payload

        return attrs

    def _raw_ams_units(self) -> list[Any]:
        root = self.print.get("ams")
        if isinstance(root, dict) and isinstance(root.get("ams"), list):
            return root["ams"]
        if isinstance(root, list):
            return root
        return []

    def ams_slots(self) -> list[dict[str, Any]]:
        """Return four deterministic AMS/BMCU tray records ordered by slot id."""
        by_slot: dict[int, dict[str, Any]] = {}

        for unit in self._raw_ams_units():
            if not isinstance(unit, dict):
                continue
            trays = unit.get("tray")
            if not isinstance(trays, list):
                continue
            for tray in trays:
                if not isinstance(tray, dict):
                    continue
                raw_id = tray.get("id", tray.get("tray_id", tray.get("tray_info_idx")))
                slot = _as_int(raw_id)
                if slot is not None and 0 <= slot <= 3:
                    by_slot[slot] = tray

        # Fallback for non-standard BMCU/AMS 2 Pro/H2 payloads.
        if not by_slot:
            summary = self.telemetry.get("_pcc_ams_summary")
            if not isinstance(summary, dict):
                summary = extract_ams_summary({"print": self.print})
            for unit in summary.get("units") or []:
                if not isinstance(unit, dict):
                    continue
                for tray_index, tray in enumerate(unit.get("trays") or []):
                    if not isinstance(tray, dict):
                        continue
                    raw_id = tray.get("id")
                    slot = _as_int(raw_id)
                    if slot is None:
                        slot = tray_index
                    if 0 <= slot <= 3:
                        by_slot.setdefault(slot, tray)

        # Deep fallback for odd third-party controllers.
        if not by_slot and self.print.get("ams") is not None:
            def visit(value: Any) -> None:
                if isinstance(value, list):
                    for item in value:
                        visit(item)
                    return
                if not isinstance(value, dict):
                    return
                raw_id = value.get("id", value.get("tray_id", value.get("tray_info_idx")))
                if raw_id is not None and any(
                    key in value
                    for key in (
                        "tray_type",
                        "filament_type",
                        "tray_info_idx",
                        "tray_color",
                        "cols",
                        "remain",
                        "tag_uid",
                    )
                ):
                    slot = _as_int(raw_id)
                    if slot is not None and 0 <= slot <= 3:
                        by_slot.setdefault(slot, value)
                for item in value.values():
                    visit(item)

            visit(self.print.get("ams"))

        return [by_slot.get(slot, {"id": str(slot)}) for slot in range(4)]

    def external_spool(self) -> dict[str, Any]:
        for key in ("vt_tray", "virtual_tray", "external_spool"):
            value = self.print.get(key)
            if isinstance(value, dict):
                return value
        return {}