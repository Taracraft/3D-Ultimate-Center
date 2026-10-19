"""Bambu AMS addressing, independent of printer names and slot counts.

Protocol reference: BambuStudio DeviceCore/DevDefs.h and DevFilaSystem.cpp,
commit da8b44ee34dd349f2ae0df3f1cbae366df482354. No device I/O.
"""
from __future__ import annotations
from typing import Any

_KINDS = {
    1: ("ams", "AMS (Original / Gen 1)"),
    2: ("ams_lite", "AMS Lite"),
    3: ("ams_2_pro", "AMS 2 Pro"),
    4: ("ams_ht", "AMS HT"),
    5: ("ams_lite_mixed", "AMS Lite (Mixed)"),
}
_NAMES = {
    "ams": 1, "ams1": 1, "amsoriginal": 1, "amsgen1": 1,
    "amslite": 2, "ams2pro": 3, "n3f": 3, "amsht": 4, "n3s": 4,
}

def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None

def ams_identity(unit: dict[str, Any]) -> dict[str, Any]:
    """Only explicit protocol type bits or named telemetry establish generation."""
    code = None
    info = unit.get("info")
    if isinstance(info, str) and info.strip():
        try:
            code = int(info.strip(), 16) & 15
        except ValueError:
            pass
    if code not in _KINDS:
        code = None
        for field in ("model", "type", "name"):
            name = "".join(c for c in str(unit.get(field) or "").lower() if c.isalnum())
            if name in _NAMES:
                code = _NAMES[name]
                break
    kind, model = _KINDS.get(code, ("ams_unknown", "AMS (Generation unbekannt)"))
    return {"kind": kind, "model": model, "type_code": code, "generation_known": code is not None}

def global_slot_index(unit_id: Any, tray_id: Any, type_code: int | None) -> int | None:
    """Return firmware tray index; never use list order as a device address."""
    unit, tray = _integer(unit_id), _integer(tray_id)
    if unit is None or tray is None:
        return None
    if type_code == 4:
        return 16 + unit - 128 if 128 <= unit <= 135 and tray == 0 else None
    if type_code == 5:
        return 24 + tray if 0 <= tray <= 3 else None
    # Legacy reports may lack type bits; their regular addresses remain usable.
    return unit * 4 + tray if 0 <= unit <= 3 and 0 <= tray <= 3 else None

def active_slot(active_tray: Any, unit_id: Any, tray_id: Any, index: int | None) -> bool:
    if index is None:
        return False
    active = str(active_tray or "").strip() if active_tray != 0 else "0"
    return active in {str(index), f"{unit_id}:{tray_id}"}
