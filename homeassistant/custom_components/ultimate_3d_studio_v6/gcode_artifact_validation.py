"""Streaming validation for rendered Bambu G-code artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import BinaryIO


class GCodeValidationError(ValueError):
    """Raised when rendered plate G-code is incomplete or unsafe."""


@dataclass(frozen=True, slots=True)
class GCodeValidationReport:
    line_count: int
    extrusion_moves: int
    positive_extrusion_mm: float
    markers: dict[str, bool]

    def as_dict(self) -> dict[str, object]:
        return {
            "line_count": self.line_count,
            "extrusion_moves": self.extrusion_moves,
            "positive_extrusion_mm": round(self.positive_extrusion_mm, 3),
            "markers": dict(self.markers),
        }


_EXTRUSION = re.compile(
    r"(?:^|\s)E(-?(?:\d+(?:\.\d*)?|\.\d+))",
    re.IGNORECASE,
)
_UNRESOLVED = re.compile(
    r"(?:\[(?:initial_|bed_temperature|nozzle_temperature|filament_|first_layer_|flush_)"
    r"|\{(?:initial_|bed_temperature|nozzle_temperature|filament_|first_layer_|flush_|curr_bed_type|max_layer_z))",
    re.IGNORECASE,
)
_M620_WITH_A = re.compile(r"^M620\s+[^;]*A(?:\s|;|$)", re.IGNORECASE)
_M621_WITH_A = re.compile(r"^M621\s+[^;]*A(?:\s|;|$)", re.IGNORECASE)


def validate_rendered_bambu_gcode(handle: BinaryIO) -> GCodeValidationReport:
    """Verify that a selected Bambu machine template was fully rendered.

    Template placeholders are checked only in the executable command section.
    Comment-only configuration metadata such as ``filename_format`` may retain
    slicer placeholders by design and must not block a safe print artifact.
    """
    markers = {
        "bambu_action_protocol": False,
        "machine_initialization": False,
        "hotend_heat": False,
        "bed_heat": False,
        "hotend_wait": False,
        "bed_wait": False,
        "material_select": False,
        "material_complete": False,
        "bed_level_flag": False,
        "bed_level_command": False,
        "flow_calibration_flag": False,
        "flow_calibration_command": False,
        "nozzle_wipe": False,
        "prime_or_calibration_line": False,
        "machine_shutdown_hotend": False,
        "machine_shutdown_bed": False,
    }
    line_count = 0
    extrusion_moves = 0
    positive_extrusion_mm = 0.0
    unresolved_examples: list[str] = []

    for raw in handle:
        line_count += 1
        if line_count > 12_000_000:
            raise GCodeValidationError("Die G-Code-Datei enthält unerwartet viele Zeilen.")
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        upper = text.upper()
        command = upper.split(";", 1)[0].strip()

        if command and _UNRESOLVED.search(command) and len(unresolved_examples) < 5:
            unresolved_examples.append(text[:240])
        if "M1002 GCODE_CLAIM_ACTION" in upper:
            markers["bambu_action_protocol"] = True
        if command.startswith("G392 ") or command.startswith("M9833"):
            markers["machine_initialization"] = True
        if command.startswith("M104 "):
            markers["hotend_heat"] = True
            if re.search(r"(?:^|\s)S0(?:\s|$)", command):
                markers["machine_shutdown_hotend"] = True
        if command.startswith("M140 "):
            markers["bed_heat"] = True
            if re.search(r"(?:^|\s)S0(?:\s|$)", command):
                markers["machine_shutdown_bed"] = True
        if command.startswith("M109 "):
            markers["hotend_wait"] = True
        if command.startswith("M190 "):
            markers["bed_wait"] = True
        if _M620_WITH_A.match(command):
            markers["material_select"] = True
        if _M621_WITH_A.match(command):
            markers["material_complete"] = True
        if "JUDGE_FLAG G29_BEFORE_PRINT_FLAG" in upper:
            markers["bed_level_flag"] = True
        if command.startswith("G29 A1"):
            markers["bed_level_command"] = True
        if "JUDGE_FLAG EXTRUDE_CALI_FLAG" in upper:
            markers["flow_calibration_flag"] = True
        if command.startswith("M983 ") or command.startswith("M984 "):
            markers["flow_calibration_command"] = True
        if "WIPE NOZZLE" in upper or "BRUSH MATERIAL WIPE" in upper:
            markers["nozzle_wipe"] = True
        if "EXTRUDE CALI TEST" in upper or command.startswith("M900 C"):
            markers["prime_or_calibration_line"] = True

        if command.startswith(("G0 ", "G1 ")):
            match = _EXTRUSION.search(command)
            if match:
                try:
                    amount = float(match.group(1))
                except ValueError:
                    amount = 0.0
                if amount > 0:
                    extrusion_moves += 1
                    positive_extrusion_mm += amount

    if unresolved_examples:
        raise GCodeValidationError(
            "Der Slicer hat Profil-Template-Platzhalter nicht aufgelöst: "
            + " | ".join(unresolved_examples)
        )
    if line_count < 100:
        raise GCodeValidationError("Die eingebettete G-Code-Datei ist unvollständig.")
    if extrusion_moves < 5 or positive_extrusion_mm <= 0:
        raise GCodeValidationError("Der G-Code enthält keine ausreichenden positiven Extrusionsbewegungen.")

    labels = {
        "bambu_action_protocol": "Bambu-Aktionsprotokoll",
        "machine_initialization": "Maschineninitialisierung",
        "hotend_heat": "Düsenheizung",
        "bed_heat": "Bettheizung",
        "hotend_wait": "Warten auf Düsentemperatur",
        "bed_wait": "Warten auf Betttemperatur",
        "material_select": "AMS/BMCU-Materialauswahl",
        "material_complete": "AMS/BMCU-Materialabschluss",
        "bed_level_flag": "Bettvermessungs-Flag",
        "bed_level_command": "Bettvermessungsbefehl",
        "flow_calibration_flag": "Flow-Kalibrierungs-Flag",
        "flow_calibration_command": "Flow-Kalibrierungsbefehl",
        "nozzle_wipe": "Düsenreinigung",
        "prime_or_calibration_line": "Prime-/Kalibrierstreifen",
        "machine_shutdown_hotend": "Düsen-Abschaltcode",
        "machine_shutdown_bed": "Bett-Abschaltcode",
    }
    missing = [labels[name] for name, present in markers.items() if not present]
    if missing:
        raise GCodeValidationError(
            "Der gerenderte Maschinenablauf ist unvollständig. Es fehlen: " + ", ".join(missing)
        )

    return GCodeValidationReport(
        line_count=line_count,
        extrusion_moves=extrusion_moves,
        positive_extrusion_mm=positive_extrusion_mm,
        markers=markers,
    )
