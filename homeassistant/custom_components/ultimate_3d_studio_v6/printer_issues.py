"""Provider-neutral printer issue normalization for Ultimate 3D Studio V6."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus, urlparse

OFFICIAL_BAMBU_WIKI_HOME = "https://wiki.bambulab.com/en/home?search={query}"
OFFICIAL_BAMBU_ERROR_CODES = "https://wiki.bambulab.com/en/hms/error-code"

_HMS_LEVELS: dict[int, tuple[str, str, str]] = {
    1: ("fatal", "error", "Kritische Druckerstörung"),
    2: ("serious", "error", "Druckerstörung"),
    3: ("common", "warning", "Druckerwarnung"),
    4: ("info", "info", "Druckerhinweis"),
}

_KNOWN_HMS_MESSAGES: dict[str, tuple[str, str]] = {
    "HMS_0500-0400-0001-0044": (
        "AMS-/BMCU-Firmware nicht kompatibel",
        "Die Firmware des als AMS A erkannten AMS-/BMCU-Moduls stimmt nicht mit der Druckerfirmware überein. "
        "Prüfe die Firmwarestände von Drucker und angeschlossenem Modul.",
    ),
}

# Frequently emitted operational error codes. Unknown codes remain fully visible
# and receive the official Bambu help link instead of being discarded.
_KNOWN_PRINT_ERRORS: dict[str, tuple[str, str]] = {
    "0500-4003": (
        "Druckdatei konnte nicht verarbeitet werden",
        "Der Drucker konnte die übertragene Druckdatei nicht parsen. Sende den Auftrag neu. "
        "Tritt der Fehler erneut auf, erzeuge die 3MF-Datei neu und prüfe Datenträger und Übertragung.",
    ),
    "1200-8006": (
        "Filament konnte nicht in den Druckkopf eingezogen werden",
        "Prüfe, ob das Filament im PTFE-Schlauch, AMS-/BMCU-Zuführweg oder Extruder klemmt. "
        "Schneide das Filamentende sauber und gerade ab, stelle sicher, dass die Spule frei läuft, "
        "führe das Filament erneut ein und setze den Druck erst danach fort.",
    ),
    "1201-8006": (
        "Filament konnte nicht in den Druckkopf eingezogen werden",
        "Prüfe den Filamentweg, den PTFE-Schlauch und den Extruder auf eine Blockade. "
        "Nach dem Beheben erneut einziehen und den Druck ausdrücklich fortsetzen.",
    ),
    "1202-8006": (
        "Filament konnte nicht in den Druckkopf eingezogen werden",
        "Prüfe den Filamentweg, den PTFE-Schlauch und den Extruder auf eine Blockade. "
        "Nach dem Beheben erneut einziehen und den Druck ausdrücklich fortsetzen.",
    ),
    "1203-8006": (
        "Filament konnte nicht in den Druckkopf eingezogen werden",
        "Prüfe den Filamentweg, den PTFE-Schlauch und den Extruder auf eine Blockade. "
        "Nach dem Beheben erneut einziehen und den Druck ausdrücklich fortsetzen.",
    ),
    "1200-8011": (
        "AMS-Filament ist aufgebraucht",
        "Lege eine neue Rolle in denselben AMS-Slot ein, führe das Filament bis zur Erkennung ein "
        "und setze den pausierten Druck danach fort.",
    ),
    "1201-8011": (
        "AMS-Filament ist aufgebraucht",
        "Lege eine neue Rolle in denselben AMS-Slot ein, führe das Filament bis zur Erkennung ein "
        "und setze den pausierten Druck danach fort.",
    ),
    "1202-8011": (
        "AMS-Filament ist aufgebraucht",
        "Lege eine neue Rolle in denselben AMS-Slot ein, führe das Filament bis zur Erkennung ein "
        "und setze den pausierten Druck danach fort.",
    ),
    "1203-8011": (
        "AMS-Filament ist aufgebraucht",
        "Lege eine neue Rolle in denselben AMS-Slot ein, führe das Filament bis zur Erkennung ein "
        "und setze den pausierten Druck danach fort.",
    ),
    "0300-8004": (
        "Filament ist aufgebraucht",
        "Lade neues Filament, prüfe den korrekten Einzug und setze den Druck danach fort.",
    ),
    "0300-8015": (
        "Filament ist aufgebraucht",
        "Lade neues Filament über die Filamentsteuerung, prüfe den Einzug und setze den Druck danach fort.",
    ),
    "1200-8004": (
        "Filament konnte nicht aus dem Druckkopf zurückgezogen werden",
        "Prüfe Filament, PTFE-Schlauch, Spule und Extruder auf eine Blockade oder gebrochenes Filament. "
        "Behebe die Ursache und starte den Rückzug erneut.",
    ),
    "1200-8003": (
        "Filament konnte nicht aus dem Extruder entfernt werden",
        "Prüfe den Extruder auf Verstopfung oder gebrochenes Filament. Entferne die Blockade und versuche es erneut.",
    ),
    "1200-8002": (
        "Filamentschneider klemmt",
        "Prüfe, ob der Schneidhebel frei beweglich und vollständig zurückgesprungen ist. "
        "Entferne Filamentreste und versuche es erneut.",
    ),
    "1200-8001": (
        "Filament konnte nicht geschnitten werden",
        "Prüfe Schneidhebel, Klinge und Filamentweg auf eine Blockade. Behebe die Ursache und versuche es erneut.",
    ),
    "1200-8012": (
        "AMS-Zuordnung konnte nicht gelesen werden",
        "Prüfe AMS-/BMCU-Verbindung und Filamentzuordnung und starte den Vorgang danach erneut.",
    ),
    "1200-8013": (
        "Altes Filament konnte nicht rechtzeitig ausgespült werden",
        "Prüfe auf verklemmtes Filament oder eine verstopfte Düse beziehungsweise einen blockierten Extruder. "
        "Behebe die Ursache und versuche es erneut.",
    ),
    "1200-8014": (
        "Filamentposition im Druckkopf wurde nicht erkannt",
        "Prüfe, ob das Filament den Extruder erreicht, ob der Filamentsensor frei ist und ob im Zuführweg eine Blockade besteht.",
    ),
    "1200-8016": (
        "Extruder fördert nicht normal",
        "Prüfe Düse und Extruder auf Verstopfung sowie das Filament auf Klemmen. "
        "Nur fortsetzen, wenn die bisherige Druckqualität noch akzeptabel ist.",
    ),
    "0300-4006": (
        "Düse ist verstopft",
        "Stoppe den Druck, wenn kein Material mehr austritt, und reinige Düse und Extruder entsprechend dem tatsächlichen Zustand.",
    ),
    "0300-8008": (
        "Problem mit der Düsentemperatur",
        "Prüfe Hotend, Heizer, Thermistor und Steckverbindungen. Den Druck nicht fortsetzen, solange die Temperaturregelung fehlerhaft ist.",
    ),
    "0300-8005": (
        "Frontabdeckung des Druckkopfs wurde gelöst",
        "Setze die Frontabdeckung korrekt ein und prüfe, ob Druckteil und Druckkopf unbeschädigt sind, bevor du fortsetzt.",
    ),
    "0300-8009": (
        "Störung der Heizbetttemperatur",
        "Prüfe Heizbett, Temperaturfühler und Verkabelung. Den Druck nicht fortsetzen, solange die Temperaturregelung fehlerhaft ist.",
    ),
    "0300-8019": (
        "Keine Druckplatte erkannt",
        "Lege die Druckplatte korrekt und vollständig auf das Heizbett und kontrolliere ihre Ausrichtung.",
    ),
}


def integer(value: Any) -> int | None:
    """Parse decimal, hexadecimal and numeric values without guessing invalid data."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        if raw.lower().startswith("0x"):
            return int(raw, 16)
        if any(char in "abcdefABCDEF" for char in raw):
            return int(raw, 16)
        return int(raw, 10)
    except (TypeError, ValueError):
        return None


def safe_text(value: Any, maximum: int = 500) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return ""
    result = str(value).strip()
    return result[:maximum]


def _official_url(value: Any) -> str | None:
    candidate = safe_text(value, 1000)
    if not candidate:
        return None
    try:
        parsed = urlparse(candidate)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"http", "https"}:
        return None
    if host == "bambulab.com" or host.endswith(".bambulab.com"):
        return candidate
    return None


def help_url(code: str, explicit: Any = None, *, print_error: bool = False) -> str:
    """Return an official Bambu help target for every known or unknown code."""
    official = _official_url(explicit)
    if official:
        return official
    if print_error:
        return OFFICIAL_BAMBU_ERROR_CODES
    query = code or "Bambu printer error"
    return OFFICIAL_BAMBU_WIKI_HOME.format(query=quote_plus(query))


def format_hms_code(attr_value: Any, code_value: Any) -> dict[str, Any] | None:
    """Build the 16-digit HMS code exactly like Bambu Studio's DevHMS parser."""
    attr = integer(attr_value)
    code = integer(code_value)
    if attr is None or code is None:
        return None
    attr &= 0xFFFFFFFF
    code &= 0xFFFFFFFF
    module_id = (attr >> 24) & 0xFF
    module_number = (attr >> 16) & 0xFF
    part_id = (attr >> 8) & 0xFF
    reserved = attr & 0xFF
    message_level = (code >> 16) & 0xFFFF
    message_code = code & 0xFFFF
    compact = (
        f"{module_id:02X}{module_number:02X}{part_id:02X}{reserved:02X}"
        f"00{message_level:02X}{message_code:04X}"
    )
    display = "HMS_" + "-".join(
        compact[index:index + 4] for index in range(0, len(compact), 4)
    )
    level_key, severity, title = _HMS_LEVELS.get(
        message_level,
        ("unknown", "warning", "Unbekannte Bambu-HMS-Meldung"),
    )
    return {
        "code": display,
        "code_compact": compact,
        "code_type": "hms",
        "attr": attr,
        "raw_code": code,
        "module_id": module_id,
        "module_number": module_number,
        "part_id": part_id,
        "reserved": reserved,
        "message_level": message_level,
        "message_code": message_code,
        "level": level_key,
        "severity": severity,
        "title": title,
        "blocking": message_level in {1, 2, 3},
    }


def normalize_hms_item(item: dict[str, Any]) -> dict[str, Any] | None:
    formatted = format_hms_code(item.get("attr"), item.get("code"))
    if formatted is None:
        raw_code = safe_text(
            item.get("hms_code")
            or item.get("ecode")
            or item.get("id")
            or item.get("code")
        )
        if not raw_code:
            return None
        formatted = {
            "code": raw_code,
            "code_compact": raw_code.replace("HMS_", "").replace("-", ""),
            "code_type": "hms",
            "level": safe_text(item.get("level") or item.get("severity")) or "unknown",
            "severity": safe_text(item.get("severity")) or "warning",
            "title": "Bambu-HMS-Meldung",
            "blocking": True,
        }

    message = safe_text(
        item.get("message")
        or item.get("msg")
        or item.get("text")
        or item.get("description")
        or item.get("intro")
    )
    code = str(formatted["code"])
    known = _KNOWN_HMS_MESSAGES.get(code)
    known_title = known[0] if known else ""
    known_message = known[1] if known else ""
    url = help_url(
        code,
        item.get("help_url")
        or item.get("wiki_url")
        or item.get("url")
        or item.get("link"),
    )
    return {
        **formatted,
        "title": known_title or str(formatted["title"]),
        "message": message or known_message or (
            "Der Drucker hat eine Bambu-HMS-Meldung ausgegeben. "
            "Öffne die offizielle Hilfe und suche dort nach dem vollständig angezeigten HMS-Code."
        ),
        "help_url": url,
        "qr_url": url,
        "source": "bambu_hms",
        "active": True,
    }


def normalize_print_error(code_value: Any, message_value: Any = None) -> dict[str, Any] | None:
    numeric = integer(code_value)
    raw_text = safe_text(code_value)
    supplied_message = safe_text(message_value)
    if numeric in (None, 0) and not raw_text and not supplied_message:
        return None
    if numeric is not None:
        compact = f"{numeric & 0xFFFFFFFF:08X}"
        display = f"{compact[:4]}-{compact[4:]}"
    else:
        compact = raw_text.replace("-", "").replace("0x", "").upper()
        display = raw_text or "UNBEKANNT"

    known = _KNOWN_PRINT_ERRORS.get(display)
    title = known[0] if known else "Druckerfehler"
    known_message = known[1] if known else ""
    generic_messages = {
        "Der Drucker hat eine Bambu-HMS-Meldung ausgegeben. Die offizielle Hilfe enthält die gerätespezifischen Prüfschritte.",
        "Der Drucker hat eine Bambu-HMS-Meldung ausgegeben. Öffne die offizielle Hilfe und suche dort nach dem vollständig angezeigten HMS-Code.",
    }
    effective_supplied = "" if supplied_message in generic_messages else supplied_message
    url = help_url(display, print_error=True)
    return {
        "code": display,
        "code_compact": compact,
        "code_type": "print_error",
        "level": "error",
        "severity": "error",
        "title": title,
        "message": effective_supplied or known_message or (
            "Der Drucker hat den Druck wegen einer Störung angehalten. "
            "Öffne die offizielle Bambu-Fehlercodeliste, behebe die Ursache und setze den Druck anschließend ausdrücklich fort."
        ),
        "help_url": url,
        "qr_url": url,
        "source": "bambu_print_error",
        "blocking": True,
        "active": True,
        "raw_code": numeric if numeric is not None else raw_text,
        "known_code": known is not None,
    }


def issue_signature(issues: list[dict[str, Any]]) -> str:
    return "|".join(
        sorted(
            f"{safe_text(item.get('code'))}:{safe_text(item.get('message'))}:{safe_text(item.get('severity'))}"
            for item in issues
        )
    )