"""Printer-bound manufacturer choices for manual AMS/external spool settings."""
from __future__ import annotations
from .a1_filament_catalog import catalog_payload as a1_catalog
from .printer_identity import resolve_connected_printer_model
from .printer_model_contract import native_defaults

def printer_model(printer):
    return resolve_connected_printer_model(getattr(printer, "model", None), getattr(printer, "serial", None))

def catalog_for_printer(printer):
    model = printer_model(printer)
    if model == "A1":
        return a1_catalog()
    if model not in {"H2S", "X1C"}:
        return []
    result = {}
    def first(value):
        return value[0] if isinstance(value, list) and value else value
    for name, authority in native_defaults(model)["filaments"].items():
        values = authority["settings"]
        identifier = str(first(values.get("filament_id")) or "")
        if not identifier:
            continue
        row = {"id": identifier, "name": name,
               "vendor": str(first(values.get("filament_vendor")) or "Generic"),
               "material_type": str(first(values["filament_type"])),
               "nozzle_temp_min": int(first(values["nozzle_temperature_range_low"])),
               "nozzle_temp_max": int(first(values["nozzle_temperature_range_high"])),
               "setting_id": str(first(values.get("setting_id")) or ""),
               "targets": ["external_spool"] + (["ams_slot"] if authority.get("ams_supported") is True else [])}
        if identifier in result and result[identifier] is None:
            continue
        previous = result.get(identifier)
        if previous is not None and any(previous[key] != row[key] for key in ("vendor", "material_type", "nozzle_temp_min", "nozzle_temp_max", "targets")):
            # Conflicting material metadata needs explicit nozzle context.
            result[identifier] = None
        elif identifier not in result:
            result[identifier] = row
    return [row for row in result.values() if row is not None]

def filament_for_printer(printer, identifier, material_type=None):
    rows = catalog_for_printer(printer)
    if identifier:
        return next((row for row in rows if row["id"] == identifier), None)
    generic = [row for row in rows if row["vendor"] == "Generic" and row["material_type"].casefold() == str(material_type or "").casefold()]
    return generic[0] if len(generic) == 1 else None
