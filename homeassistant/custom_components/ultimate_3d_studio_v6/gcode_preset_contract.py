"""Six A1 sections: four machine presets and two filament parameters."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_DATA = json.loads(Path(__file__).with_name("a1_gcode_defaults.json").read_text(encoding="utf-8"))
SLOT_KEYS = {
    "start_sound": "start_sound_gcode",
    "end_sound": "end_sound_gcode",
    "gcode_1": "custom_gcode_1",
    "gcode_2": "custom_gcode_2",
}
_NAMES = {"start_sound": "A1 Startsound", "end_sound": "A1 Endsound",
          "gcode_1": "A1 Maschinen-Start", "gcode_2": "A1 Maschinen-Ende"}
GCODE_DEFAULT_PROFILES = tuple({
    "id": "builtin.a1." + slot, "name": _NAMES[slot], "kind": "process",
    "source": "builtin", "builtin": True, "base_id": None, "version": "20260513",
    "created_at": None, "updated_at": None,
    "payload": {"gcode_slot": slot, "printer_model": "A1", key: _DATA["parts"][slot]},
} for slot, key in SLOT_KEYS.items())
FILAMENT_GCODE_DEFAULTS = {key: _DATA[key] for key in ("filament_start_gcode", "filament_end_gcode")}


def resolve_gcode_presets(catalog: dict, model: str) -> dict | None:
    selection = catalog.get("selection", {})
    ids = selection.get("gcode_preset_ids", {})
    if not isinstance(ids, dict) or set(ids) - set(SLOT_KEYS):
        raise ValueError("Ungültige G-Code-Profilauswahl.")
    if str(model).strip().casefold() not in {"a1", "bambu lab a1"}:
        if any(ids.values()):
            raise ValueError("Die Maschinen-G-Code-Vorlagen sind ausschließlich für den A1.")
        return None
    by_id = {p["id"]: p for p in catalog.get("profiles", [])}
    parts, selected = {}, {}
    for slot, key in SLOT_KEYS.items():
        profile_id = ids.get(slot, "builtin.a1." + slot)
        if not profile_id:
            if slot in {"gcode_1", "gcode_2"}:
                raise ValueError("Maschinen-Start und Maschinen-Ende müssen gewählt sein.")
            parts[slot] = ""
            selected[slot] = ""
            continue
        profile = by_id.get(profile_id)
        if not profile or profile.get("kind") != "process":
            raise ValueError("Das gewählte Maschinen-G-Code-Profil ist nicht verfügbar.")
        payload = profile.get("payload", {})
        if payload.get("gcode_slot") != slot or payload.get("printer_model") != "A1":
            raise ValueError("Das G-Code-Profil passt nicht zum Abschnitt oder Drucker.")
        value = payload.get(key)
        if not isinstance(value, str) or len(value.encode()) > 200000:
            raise ValueError("Der G-Code-Abschnitt ist ungültig oder zu groß.")
        parts[slot], selected[slot] = value, profile_id
    settings = {}
    for slot, sound, marker, native in (
        ("gcode_1", "start_sound", ";@U3D_START_SOUND@", "machine_start_gcode"),
        ("gcode_2", "end_sound", ";@U3D_END_SOUND@", "machine_end_gcode"),
    ):
        if parts[slot].count(marker) != 1:
            raise ValueError("Der Maschinenablauf muss genau eine Sound-Einfügestelle enthalten.")
        code = parts[slot].replace(marker, parts[sound])
        if ";@U3D_" in code or not code.strip():
            raise ValueError("Die Maschinen-G-Code-Vorlage ist unvollständig.")
        settings[native] = code
    body = {"schema": 1, "printer_model": "A1", "selected_profiles": selected, "settings": settings}
    body["sha256"] = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return body
