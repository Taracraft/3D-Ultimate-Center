"""Human-readable Bambu print-stage normalization for V6."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .telemetry import find, number, text


@dataclass(frozen=True, slots=True)
class PrintStage:
    code: int | None
    key: str
    label: str
    detail: str
    active: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "key": self.key,
            "label": self.label,
            "detail": self.detail,
            "active": self.active,
        }


_STAGE_MAP: dict[int, tuple[str, str, str]] = {
    0: ("printing_model", "Modell wird gedruckt", "Der eigentliche Modelldruck läuft."),
    1: ("bed_leveling", "Druckbett wird nivelliert", "Die automatische Druckbettnivellierung läuft."),
    2: ("bed_heating", "Druckbett wird aufgeheizt", "Das Druckbett erreicht die Solltemperatur."),
    3: ("mechanical_check", "Mechanik wird geprüft", "Der Drucker prüft die XY-Mechanik."),
    4: ("filament_change", "Filament wird gewechselt", "Der Drucker führt einen Materialwechsel aus."),
    5: ("waiting", "Drucker wartet", "Ein interner Wartepunkt wird abgearbeitet."),
    6: ("filament_runout", "Filament fehlt", "Der Druck ist wegen Filamentmangel pausiert."),
    7: ("nozzle_heating", "Düse wird aufgeheizt", "Die Düse erreicht die Solltemperatur."),
    8: ("flow_calibration", "Filamentfluss wird kalibriert", "Die Extrusions- und Flusskalibrierung läuft."),
    9: ("bed_scan", "Druckbett wird gescannt", "Die Druckoberfläche wird geprüft."),
    10: ("first_layer_check", "Erste Schicht wird geprüft", "Der Drucker kontrolliert die erste Schicht."),
    11: ("plate_detection", "Druckplatte wird erkannt", "Der Druckplattentyp wird identifiziert."),
    12: ("lidar_calibration", "Sensor wird kalibriert", "Die optische Kalibrierung läuft."),
    13: ("homing", "Druckkopf wird referenziert", "Der Druckkopf fährt seine Referenzposition an."),
    14: ("nozzle_cleaning", "Druckkopf wird gereinigt", "Die Düse wird am Wischer gereinigt."),
    15: ("extruder_temperature_check", "Extrudertemperatur wird geprüft", "Der Drucker kontrolliert die Düsentemperatur."),
    16: ("paused_by_user", "Druck pausiert", "Der Druck wurde durch den Benutzer pausiert."),
    17: ("cover_open", "Abdeckung prüfen", "Eine Druckerabdeckung ist geöffnet oder wurde entfernt."),
    18: ("sensor_calibration", "Sensorprüfung läuft", "Die optische Sensorprüfung läuft."),
    19: ("test_strip", "Teststreifen wird gedruckt", "Der Kalibrier- beziehungsweise Flussteststreifen wird gedruckt."),
    20: ("nozzle_temperature_error", "Düsentemperatur fehlerhaft", "Der Druck ist wegen der Düsentemperatur pausiert."),
    21: ("bed_temperature_error", "Betttemperatur fehlerhaft", "Der Druck ist wegen der Betttemperatur pausiert."),
    22: ("filament_unloading", "Filament wird zurückgezogen", "Das bisherige Filament wird aus dem Extruder zurückgezogen."),
    23: ("skip_step_pause", "Druck pausiert", "Der Druck wartet auf eine interne Fortsetzung."),
    24: ("filament_loading", "Filament wird eingezogen", "Das ausgewählte Filament wird bis zur Düse eingezogen."),
    25: ("motor_calibration", "Motoren werden kalibriert", "Die Motorgeräusch- und Bewegungsprüfung läuft."),
    26: ("ams_connection_lost", "AMS-Verbindung unterbrochen", "Der Druck wartet auf die Materialeinheit."),
    27: ("fan_error", "Lüfterprüfung erforderlich", "Der Druck ist wegen einer Lüfterabweichung pausiert."),
    28: ("chamber_temperature_error", "Bauraumtemperatur fehlerhaft", "Der Druck ist wegen der Bauraumtemperatur pausiert."),
    29: ("chamber_cooling", "Bauraum wird gekühlt", "Der Drucker reduziert die Bauraumtemperatur."),
    30: ("gcode_pause", "Druckprogramm pausiert", "Der G-Code hat einen Pausepunkt erreicht."),
    31: ("motor_check", "Motorprüfung läuft", "Die Motoren werden geprüft."),
    32: ("nozzle_filament_check", "Düse wird geprüft", "Der Drucker prüft Filament an der Düse."),
    33: ("cutter_error", "Filamentschneider prüfen", "Der Druck ist wegen des Filamentschneiders pausiert."),
    34: ("first_layer_error", "Fehler in der ersten Schicht", "Der Druck ist wegen einer fehlerhaften ersten Schicht pausiert."),
    35: ("nozzle_clog", "Düse möglicherweise verstopft", "Der Druck ist wegen einer möglichen Düsenverstopfung pausiert."),
    36: ("filament_purging", "Altes Filament wird ausgespült", "Restmaterial wird aus der Düse gespült und gereinigt."),
}

_ACTIVE_STATES = {
    "running",
    "printing",
    "prepare",
    "preparing",
    "pause",
    "paused",
}


def resolve_print_stage(payload: dict[str, Any]) -> PrintStage:
    raw_code = number(find(payload, ("stg_cur", "mc_print_stage", "print_stage", "stage")))
    code = int(raw_code) if raw_code is not None else None
    state = text(find(payload, ("gcode_state", "print_status", "state")), "unknown").casefold()
    active = state in _ACTIVE_STATES

    if code is not None and code in _STAGE_MAP:
        key, label, detail = _STAGE_MAP[code]
        return PrintStage(code=code, key=key, label=label, detail=detail, active=active)

    if state in {"pause", "paused"}:
        return PrintStage(code=code, key="paused", label="Druck pausiert", detail="Der Drucker wartet auf Fortsetzung oder Abbruch.", active=True)
    if state in {"finish", "finished", "complete", "completed"}:
        return PrintStage(code=code, key="completed", label="Druck abgeschlossen", detail="Der Druckauftrag wurde beendet.", active=False)
    if state in {"failed", "error"}:
        return PrintStage(code=code, key="failed", label="Druck fehlgeschlagen", detail="Der Drucker hat einen Fehler gemeldet.", active=False)
    if state in {"idle", "ready"}:
        return PrintStage(code=code, key="idle", label="Drucker bereit", detail="Aktuell läuft kein Druckauftrag.", active=False)
    if active:
        return PrintStage(code=code, key="processing", label="Druckvorbereitung läuft", detail="Der Drucker arbeitet den aktuellen Vorbereitungsschritt ab.", active=True)
    return PrintStage(code=code, key="unknown", label="Druckstatus wird ermittelt", detail="Der Drucker hat noch keinen bekannten Arbeitsschritt gemeldet.", active=False)
