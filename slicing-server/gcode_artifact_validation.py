"""Streaming validation for rendered Bambu G-code artifacts."""
from __future__ import annotations

from dataclasses import dataclass
import math
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
    temperature_limits_verified: bool = False
    max_commanded_nozzle_temperature_c: float = 0.0
    max_commanded_bed_temperature_c: float = 0.0
    checked_print_extrusion_moves: int = 0
    filament_parameter_contract_verified: bool = False
    declared_printer_model: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "line_count": self.line_count,
            "extrusion_moves": self.extrusion_moves,
            "positive_extrusion_mm": round(self.positive_extrusion_mm, 3),
            "markers": dict(self.markers),
            "temperature_limits_verified": self.temperature_limits_verified,
            "max_commanded_nozzle_temperature_c": self.max_commanded_nozzle_temperature_c,
            "max_commanded_bed_temperature_c": self.max_commanded_bed_temperature_c,
            "checked_print_extrusion_moves": self.checked_print_extrusion_moves,
            "filament_parameter_contract_verified": self.filament_parameter_contract_verified,
            "declared_printer_model": self.declared_printer_model,
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


def _arc_bounds(command: str, start: dict[str, float], end: dict[str, float], clockwise: bool) -> dict[str, tuple[float, float]]:
    """Bound an XY arc with relative I/J centre offsets, including its extrema."""
    args = {key: float(value) for key, value in re.findall(r"(?:^|\s)([IJRP])([+-]?(?:\d+(?:\.\d*)?|\.\d+))", command)}
    if "R" in args or not ({"I", "J"} & args.keys()) or args.get("P", 1) != 1:
        raise GCodeValidationError("Der Kreisbogen benötigt relative I/J-Mittelpunkte und höchstens eine Umdrehung.")
    cx, cy = start["X"] + args.get("I", 0), start["Y"] + args.get("J", 0)
    radius = math.hypot(start["X"] - cx, start["Y"] - cy)
    end_radius = math.hypot(end["X"] - cx, end["Y"] - cy)
    # Native endpoints/offsets are rounded to 0.001 mm independently.
    if radius <= 0 or abs(radius - end_radius) > 0.01:
        raise GCodeValidationError("Der Kreisbogen hat keinen konsistenten Mittelpunkt.")
    first = math.atan2(start["Y"] - cy, start["X"] - cx)
    last = math.atan2(end["Y"] - cy, end["X"] - cx)
    direction = -1 if clockwise else 1
    sweep = ((last - first) * direction) % math.tau
    if math.hypot(end["X"] - start["X"], end["Y"] - start["Y"]) < 1e-9:
        sweep = math.tau
    points = [(start["X"], start["Y"]), (end["X"], end["Y"])]
    for angle in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        if ((angle - first) * direction) % math.tau <= sweep + 1e-9:
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return {"X": (min(x for x, _ in points), max(x for x, _ in points)),
            "Y": (min(y for _, y in points), max(y for _, y in points)),
            "Z": (min(start["Z"], end["Z"]), max(start["Z"], end["Z"]))}


def validate_rendered_bambu_gcode(
    handle: BinaryIO,
    *,
    hardware_limits: dict[str, float] | None = None,
    runtime_parameters: list[dict[str, object]] | None = None,
    expected_printer_model: str | None = None,
    expected_bed_temperature_key: str | None = None,
) -> GCodeValidationReport:
    """Verify that a selected Bambu machine template was fully rendered.

    Template placeholders are checked only in the executable command section.
    Comment-only configuration metadata such as ``filename_format`` may retain
    slicer placeholders by design and must not block a safe print artifact.
    """
    # H2S firmware uses dedicated calibration and cleaning opcodes. A file
    # declaration alone must never grant that machine's hardware authority.
    model_key = re.sub(r"[^a-z0-9]+", " ", str(expected_printer_model or "").casefold()).strip()
    h2s = model_key in {"h2s", "bambu h2s", "bambu lab h2s"}
    if h2s and (hardware_limits is None or "max_chamber_temperature_c" not in hardware_limits):
        raise GCodeValidationError("Für den H2S fehlt die explizite Hardware-/Kammertemperaturprüfung.")
    if h2s:
        maxima = {"max_nozzle_temperature_c": 350., "max_bed_temperature_c": 120.,
                  "max_chamber_temperature_c": 65., "width_mm": 340.,
                  "depth_mm": 320., "height_mm": 340.}
        for key, maximum in maxima.items():
            raw = hardware_limits.get(key)
            try:
                value = float(raw)
            except (ValueError, TypeError) as exc:
                raise GCodeValidationError("Ungültige H2S-Hardwaregrenze.") from exc
            if isinstance(raw, bool) or not math.isfinite(value) or value <= 0 or value > maximum:
                raise GCodeValidationError("Ungültige H2S-Hardwaregrenze.")
    h2s_load_line = False
    h2s_prime_move = False
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
    limits = dict(hardware_limits) if hardware_limits is not None else None
    temperatures = {"nozzle": 0.0, "bed": 0.0}
    print_started = False
    material_change = False
    relative_axes = False
    relative_extrusion = False
    position = {"X": 0.0, "Y": 0.0, "Z": 0.0, "E": 0.0}
    checked_print_moves = 0
    arc_plane = "G17"
    relative_arc_centres = True
    print_bounds = {"X": [float("inf"), float("-inf")], "Y": [float("inf"), float("-inf")], "Z": [float("inf"), float("-inf")]}
    wanted_settings = {key for profile in runtime_parameters or [] for key in profile}
    observed_settings: dict[str, list[str]] = {}
    declared_model = ""
    material_channel = None
    executed_nozzle: dict[int, set[float]] = {}
    executed_bed: set[float] = set()
    if limits is not None:
        for key in ("max_nozzle_temperature_c", "max_bed_temperature_c"):
            value = limits.get(key)
            if isinstance(value, bool) or value is None or not math.isfinite(float(value)) or float(value) <= 0:
                raise GCodeValidationError("Die Hardware-Temperaturgrenzen sind ungültig.")

    for raw in handle:
        line_count += 1
        if line_count > 12_000_000:
            raise GCodeValidationError("Die G-Code-Datei enthält unerwartet viele Zeilen.")
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        upper = text.upper()
        command = upper.split(";", 1)[0].strip()
        # Native G-code normally separates words; compact and numbered words
        # must receive the same geometry checks as their spaced equivalents.
        command = re.sub(r"^N\d+\s*", "", command)
        command = re.sub(r"(?<=[0-9.])(?=[A-Z])", " ", command)
        tool = re.fullmatch(r"T(\d+)", command)
        if tool:
            number = int(tool[1])
            if number < 64:
                material_channel = number + 1
            elif number == 255:
                material_channel = None
        if re.match(r"^G[0123]\s", command) and re.search(r"[XYZEIJ]\s*[+-]?(?:NAN|INF(?:INITY)?)", command):
            raise GCodeValidationError("Der Bewegungsbefehl enthält eine nicht endliche Koordinate.")
        if print_started and not material_change and re.match(r"^G28(?:\s|$)", command):
            raise GCodeValidationError("Homing im regulären Druckteil ist nicht durch den Geometrievertrag gedeckt.")
        setting = re.match(r"^;\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", text)
        if setting and setting[1].casefold() == "printer_model":
            declared_model = setting[2].strip().strip('"')
        if setting and setting[1] in wanted_settings:
            observed_settings[setting[1]] = [value.strip().strip('"') for value in re.split(r"[;,]", setting[2])]
        # A1 may be recognized only by an exact machine-model declaration.
        # Other printers require their own supplied hardware authority.
        if limits is None and re.match(r"^;\s*(?:printer_model|printer_settings_id)\s*=\s*BAMBU LAB A1(?:\s+[0-9.]+\s+NOZZLE)?\s*$", upper, re.IGNORECASE):
            limits = {"max_nozzle_temperature_c": 300.0, "max_bed_temperature_c": 100.0,
                      "width_mm": 256.0, "depth_mm": 256.0, "height_mm": 256.0}
        if upper == "; MACHINE_START_GCODE_END":
            print_started = True
        if upper.startswith("; MACHINE_END_GCODE_START"):
            print_started = False
        if _M620_WITH_A.match(command):
            material_change = True
        if _M621_WITH_A.match(command):
            material_change = False
        if command == "G20":
            raise GCodeValidationError("Der geprüfte Druckvertrag benötigt Millimeter; G20 ist nicht zulässig.")
        if command in {"G17", "G18", "G19"}:
            arc_plane = command
        if command in {"G90.1", "G91.1"}:
            relative_arc_centres = command == "G91.1"
        if command == "G90":
            relative_axes = False
        if command == "G91":
            relative_axes = True
        if command == "M82":
            relative_extrusion = False
        if command == "M83":
            relative_extrusion = True
        coords = {key: float(value) for key, value in re.findall(r"(?:^|\s)([XYZE])([+-]?(?:\d+(?:\.\d*)?|\.\d+))", command)}
        if command.startswith("G92 "):
            if print_started and any(key in coords for key in ("X", "Y", "Z")):
                raise GCodeValidationError("Eine Koordinaten-Neuzuordnung im Druckteil ist nicht durch den Maschinenvertrag gedeckt.")
            position.update(coords)
        elif re.match(r"^G[0123](?:\s|$)", command):
            previous = dict(position)
            for key, value in coords.items():
                relative = relative_extrusion if key == "E" else relative_axes
                position[key] = position[key] + value if relative else value
            extrusion = position["E"] - previous["E"] if "E" in coords else 0.0
            if print_started and not material_change and extrusion > 0:
                checked_print_moves += 1
                for axis in ("X", "Y", "Z"):
                    print_bounds[axis][0] = min(print_bounds[axis][0], previous[axis], position[axis])
                    print_bounds[axis][1] = max(print_bounds[axis][1], previous[axis], position[axis])
                if re.match(r"^G[23]\s", command):
                    if arc_plane != "G17" or not relative_arc_centres:
                        raise GCodeValidationError("Der geprüfte Kreisbogenvertrag benötigt die XY-Ebene und relative Mittelpunkte.")
                    for axis, bounds in _arc_bounds(command, previous, position, command.startswith("G2 ")).items():
                        print_bounds[axis][0] = min(print_bounds[axis][0], bounds[0])
                        print_bounds[axis][1] = max(print_bounds[axis][1], bounds[1])
        heater = re.match(r"^(?:N\d+\s*)?(M104|M109|M140|M190)(?=\s|[A-Z]|$)(.*)$", command)
        if heater:
            target = "nozzle" if heater[1] in {"M104", "M109"} else "bed"
            # S sets a target; R also sets a target for wait-for-temperature.
            values = re.findall(r"[SRH]\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?=\s|[A-Z]|$)", heater[2])
            if not values and _UNRESOLVED.search(command):
                raise GCodeValidationError("Der Slicer hat Profil-Template-Platzhalter nicht aufgelöst: " + text[:240])
            if not values or re.search(r"[SRH]\s*(?:NAN|INF|[-+]?INFINITY)", heater[2]):
                raise GCodeValidationError(f"Ungültiger Heizbefehl in Zeile {line_count}: {text[:160]}")
            for raw_value in values:
                value = float(raw_value)
                if value < 0 or not math.isfinite(value):
                    raise GCodeValidationError(f"Ungültige Heiztemperatur in Zeile {line_count}.")
                temperatures[target] = max(temperatures[target], value)
            setpoints = re.findall(r"[SR]\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?=\s|[A-Z]|$)", heater[2])
            if target == "bed":
                executed_bed.update(float(value) for value in setpoints)
            elif material_channel is not None:
                executed_nozzle.setdefault(material_channel, set()).update(float(value) for value in setpoints)

        if h2s:
            # These firmware commands also request heat; standard M104/M109
            # checks alone miss purge, nozzle cleaning and chamber targets.
            heater = re.match(r"^(G150|M620\.10|M141|M191)(?:\s|$)(.*)$", command)
            if heater:
                keys = "TP" if heater[1] == "M620.10" else "T" if heater[1] == "G150" else "SR"
                for key in keys:
                    raw_targets = re.findall(r"(?:^|\s)" + key + r"\s*([^\s]+)", heater[2])
                    for raw in raw_targets:
                        try:
                            value = float(raw)
                        except ValueError as exc:
                            raise GCodeValidationError("Ungültige H2S-Heiztemperatur.") from exc
                        if not math.isfinite(value) or value < 0:
                            raise GCodeValidationError("Ungültige H2S-Heiztemperatur.")
                        if heater[1] in {"M141", "M191"}:
                            if value > float(hardware_limits["max_chamber_temperature_c"]) + .01:
                                raise GCodeValidationError("Der G-Code überschreitet die H2S-Kammertemperaturgrenze.")
                        else:
                            temperatures["nozzle"] = max(temperatures["nozzle"], value)
            if upper.startswith(";===== NOZZLE LOAD LINE"):
                h2s_load_line = True
            if upper.startswith(";===== NOOZLE LOAD LINE END"):
                h2s_load_line = False
            if h2s_load_line and re.match(r"^G1(?:\s|$)", command):
                move = _EXTRUSION.search(command)
                if move and float(move[1]) > 0 and re.search(r"(?:^|\s)[XY][+-]?[0-9.]", command):
                    h2s_prime_move = True
            if re.match(r"^M983\.3(?:\s|$)", command):
                markers["flow_calibration_command"] = True
            if re.match(r"^G150(?:\s|$)", command) and re.search(r"(?:^|\s)T[0-9.]", command):
                markers["nozzle_wipe"] = True
            if h2s_prime_move:
                markers["prime_or_calibration_line"] = True

        load_heater = re.match(r"^M620\.1(?:\s|$)(.*)$", command)
        if load_heater:
            targets = re.findall(r"(?:^|\s)T\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))(?=\s|$)", load_heater[1])
            if re.search(r"(?:^|\s)T\s*(?:NAN|INF|[-+]?INFINITY)", load_heater[1]):
                raise GCodeValidationError(f"Ungültige AMS-Ladetemperatur in Zeile {line_count}.")
            for target in targets:
                value = float(target)
                if value < 0:
                    raise GCodeValidationError(f"Ungültige AMS-Ladetemperatur in Zeile {line_count}.")
                temperatures["nozzle"] = max(temperatures["nozzle"], value)

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
        if not h2s and (command.startswith("M983 ") or command.startswith("M984 ")):
            markers["flow_calibration_command"] = True
        if not h2s and ("WIPE NOZZLE" in upper or "BRUSH MATERIAL WIPE" in upper):
            markers["nozzle_wipe"] = True
        if not h2s and ("EXTRUDE CALI TEST" in upper or command.startswith("M900 C")):
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
    if expected_printer_model is not None:
        def canonical_model(value: str) -> str:
            name = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
            name = re.sub(r"^bambu(?: lab)?\s+", "", name)
            return name.replace(" ", "")
        if not declared_model or canonical_model(declared_model) != canonical_model(expected_printer_model):
            raise GCodeValidationError("Das G-Code-Artefakt gehört nicht nachweislich zum gewählten Druckermodell.")
    if limits is not None:
        for target, key in (("nozzle", "max_nozzle_temperature_c"), ("bed", "max_bed_temperature_c")):
            if temperatures[target] > float(limits[key]) + 0.01:
                label = "Düse" if target == "nozzle" else "Druckbett"
                raise GCodeValidationError(
                    f"{label}: Der G-Code fordert {temperatures[target]:g} °C; "
                    f"der gewählte Drucker erlaubt höchstens {float(limits[key]):g} °C."
                )
        if checked_print_moves and "width_mm" in limits:
            for axis, key in (("X", "width_mm"), ("Y", "depth_mm"), ("Z", "height_mm")):
                if print_bounds[axis][0] < -0.05 or print_bounds[axis][1] > float(limits[key]) + 0.05:
                    raise GCodeValidationError(f"Der extrudierende Druckpfad überschreitet die physische {axis}-Grenze des gewählten Druckers.")
    if runtime_parameters is not None:
        if not runtime_parameters or any(not profile for profile in runtime_parameters):
            raise GCodeValidationError("Der Filamentparameter-Nachweis ist unvollständig.")
        for channel, profile in enumerate(runtime_parameters):
            for key, raw_expected in profile.items():
                expected = raw_expected if isinstance(raw_expected, list) else [raw_expected]
                observed = observed_settings.get(key) or []
                if len(expected) != 1 or not observed or (len(observed) != 1 and channel >= len(observed)):
                    raise GCodeValidationError(f"Materialkanal {channel + 1}: {key} fehlt im G-Code-Parametervertrag.")
                actual = observed[0] if len(observed) == 1 else observed[channel]
                try:
                    matches = abs(float(actual) - float(expected[0])) <= 1e-6
                except (TypeError, ValueError):
                    matches = actual.casefold() == str(expected[0]).strip().strip('"').casefold()
                if not matches:
                    raise GCodeValidationError(f"Materialkanal {channel + 1}: Der Slicer hat {key} nicht unverändert übernommen.")
        for channel, profile in enumerate(runtime_parameters, start=1):
            for key in ("nozzle_temperature", "nozzle_temperature_initial_layer"):
                if key in profile:
                    values = profile[key] if isinstance(profile[key], list) else [profile[key]]
                    expected = float(values[0])
                    if not any(abs(actual - expected) <= .01 for actual in executed_nozzle.get(channel, set())):
                        raise GCodeValidationError(f"Materialkanal {channel}: {key} wurde nicht als Heizbefehl ausgeführt.")
            if expected_bed_temperature_key:
                for key in (expected_bed_temperature_key, expected_bed_temperature_key + "_initial_layer"):
                    values = profile.get(key)
                    if not isinstance(values, list) or len(values) != 1 or not any(abs(actual - float(values[0])) <= .01 for actual in executed_bed):
                        raise GCodeValidationError(f"Materialkanal {channel}: {key} wurde nicht als gemeinsamer Bettheizbefehl ausgeführt.")
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
        temperature_limits_verified=limits is not None,
        max_commanded_nozzle_temperature_c=temperatures["nozzle"],
        max_commanded_bed_temperature_c=temperatures["bed"],
        checked_print_extrusion_moves=checked_print_moves,
        filament_parameter_contract_verified=runtime_parameters is not None,
        declared_printer_model=declared_model,
    )


if __name__ == "__main__":
    import json
    from pathlib import Path
    import sys
    from filament_parameter_contract import BED_TEMPERATURE_KEYS
    from slicer_execution_contract import digest, job_hardware_limits, validate_execution_contract
    if len(sys.argv) not in {3, 4}:
        raise SystemExit("usage: gcode_artifact_validation.py JOB GCODE [MATERIALS]")
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    validate_execution_contract(job)
    parameters = None
    if len(sys.argv) == 4:
        runtime = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        profiles = (job.get("material_plan") or {}).get("filaments") or []
        applied = runtime.get("filaments") or []
        if len(profiles) != len(applied):
            raise GCodeValidationError("Die materialisierten Filamentkanäle passen nicht zum Auftrag.")
        for selected, proof in zip(profiles, applied, strict=True):
            if proof.get("selected_profile_sha256") != digest(selected.get("selected_profile")):
                raise GCodeValidationError("Der Filamentparameter-Nachweis gehört zu einem anderen Profil.")
        parameters = [profile.get("parameter_settings") or {} for profile in applied]
    elif (job.get("process_overrides") or {}).get("require_execution_contract") is True:
        raise GCodeValidationError("Der finale native Filamentparameter-Nachweis fehlt.")
    with Path(sys.argv[2]).open("rb") as stream:
        report = validate_rendered_bambu_gcode(stream, hardware_limits=job_hardware_limits(job), runtime_parameters=parameters,
                                             expected_printer_model=(job.get("target_printer") or {}).get("model"),
                                         expected_bed_temperature_key=BED_TEMPERATURE_KEYS.get((job.get("process_overrides") or {}).get("bambu_bed_type")))
    print(json.dumps(report.as_dict()))
