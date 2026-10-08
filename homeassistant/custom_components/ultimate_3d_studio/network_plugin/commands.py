from __future__ import annotations

from typing import Any

from ..commands import create_sequence_id
from .models import NetworkCommand


def build_command(
    section: str,
    command: str,
    *,
    qos: int = 1,
    sequence_id: str | None = None,
    **fields: Any,
) -> NetworkCommand:
    seq = sequence_id or create_sequence_id()
    body: dict[str, Any] = {
        "sequence_id": seq,
        "command": command,
        **fields,
    }
    return NetworkCommand(
        section=section,
        command=command,
        sequence_id=seq,
        payload={section: body},
        qos=qos,
    )


def build_get_version() -> NetworkCommand:
    return build_command("info", "get_version", qos=0)


def build_push_all() -> NetworkCommand:
    return build_command(
        "pushing",
        "pushall",
        qos=0,
        version=1,
        push_target=1,
    )


def build_print_control(command: str) -> NetworkCommand:
    if command not in {"pause", "resume", "stop"}:
        raise ValueError(f"Unsupported print control command: {command}")
    qos = 0 if command == "resume" else 1
    return build_command("print", command, qos=qos, param="")


def build_print_speed(level: int) -> NetworkCommand:
    if level not in {1, 2, 3, 4}:
        raise ValueError(f"Unsupported Bambu speed level: {level}")
    return build_command("print", "print_speed", qos=1, param=str(level))


def build_gcode_line(gcode: str) -> NetworkCommand:
    normalized = gcode.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise ValueError("G-code payload must not be empty")
    return build_command("print", "gcode_line", qos=1, param=normalized)


def build_project_file(**fields: Any) -> NetworkCommand:
    return build_command("print", "project_file", qos=0, **fields)


def build_ams_filament_setting(
    *,
    ams_id: int,
    tray_id: int,
    tray_info_idx: str,
    tray_color: str,
    nozzle_temp_min: int,
    nozzle_temp_max: int,
    tray_type: str,
) -> NetworkCommand:
    if not isinstance(ams_id, int) or not 0 <= ams_id <= 255:
        raise ValueError("ams_id must be an integer between 0 and 255")
    if not isinstance(tray_id, int) or not 0 <= tray_id <= 3:
        raise ValueError("tray_id must be an integer between 0 and 3")
    normalized_color = str(tray_color or "").strip().lstrip("#").upper()
    if len(normalized_color) == 6:
        normalized_color += "FF"
    if len(normalized_color) != 8 or any(
        character not in "0123456789ABCDEF"
        for character in normalized_color
    ):
        raise ValueError("tray_color must be RRGGBB or RRGGBBAA")
    material = str(tray_type or "").strip()
    if not material or len(material) > 32:
        raise ValueError("tray_type must contain 1 to 32 characters")
    minimum = int(nozzle_temp_min)
    maximum = int(nozzle_temp_max)
    if not 1 <= minimum <= maximum <= 400:
        raise ValueError("nozzle temperatures must satisfy 1 <= min <= max <= 400")
    return build_command(
        "print",
        "ams_filament_setting",
        qos=1,
        ams_id=ams_id,
        tray_id=tray_id,
        tray_info_idx=str(tray_info_idx or "").strip(),
        tray_color=normalized_color,
        nozzle_temp_min=minimum,
        nozzle_temp_max=maximum,
        tray_type=material,
    )
