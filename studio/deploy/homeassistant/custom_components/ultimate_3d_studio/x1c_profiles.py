"""Editable X1 Carbon profiles derived from pinned Bambu manufacturer sources."""
from copy import deepcopy
import hashlib
import re
from .printer_model_contract import hardware_limits, x1c_defaults

def _profile(identifier, name, kind, payload):
    return {"id": identifier, "name": name, "kind": kind, "source": "local", "builtin": False,
            "base_id": None, "version": "20261019", "created_at": None, "updated_at": None,
            "payload": payload}

X1C_PROFILES = [_profile("local.printer.x1c", "Bambu Lab X1 Carbon", "printer", {
    "vendor": "Bambu Lab", "model": "X1C", "technology": "FFF", "build_volume_mm": [256,256,256],
    **hardware_limits("X1C"), "physical_extruder_count": 1, "max_material_channels": 16,
    "heated_chamber": False, "sound_source": "manufacturer_machine_gcode"})]
for diameter, machine in x1c_defaults()["machines"].items():
    process = x1c_defaults()["processes"][diameter]
    suffix = diameter.replace(".", "_")
    material = "stainless_steel" if diameter == "0.2" else "hardened_steel"
    X1C_PROFILES += [
        _profile("local.nozzle.x1c_" + suffix, "X1 Carbon " + diameter + " mm " + ("Edelstahl" if diameter == "0.2" else "gehärteter Stahl"), "nozzle",
                 {"printer": "Bambu Lab X1C", "diameter_mm": float(diameter), "material": material}),
        _profile("local.process.x1c_" + suffix, "X1 Carbon " + str(process["layer_height"]) + " mm Standard", "process",
                 {"printer_vendor": "Bambu Lab", "printer_model": "X1C", "target_printer": "Bambu Lab X1C",
                  "nozzle_diameter_mm": float(diameter), "layer_height_mm": process["layer_height"],
                  "first_layer_height_mm": .2, "slicing_supported": True})]
for surface, name in [("textured_pei", "Texturierte PEI"), ("smooth_pei", "Glatte PEI"), ("cool_plate", "Cool Plate"), ("engineering_plate", "Engineering Plate"), ("cool_plate_super_tack", "Cool Plate SuperTack")]:
    X1C_PROFILES.append(_profile("local.build_plate.x1c_" + surface, "X1 Carbon " + name + " · 256×256 mm", "build_plate",
        {"surface": surface, "width_mm": 256, "depth_mm": 256, "printer_model": "X1C"}))
for name, authority in x1c_defaults()["filaments"].items():
    metadata = {"compatible_printers", "compatible_prints", "compatible_printers_condition", "compatible_prints_condition"}
    payload = {key: [value[0]] if isinstance(value, list) and value and key not in metadata else deepcopy(value) for key, value in authority["settings"].items()}
    # Retain manufacturer references without requesting an absent chamber heater.
    chamber = payload.get("chamber_temperatures", ["0"])
    if any(float(value) != 0 for value in chamber):
        payload["manufacturer_chamber_temperatures"] = deepcopy(chamber)
        payload["chamber_temperatures"] = ["0"]
    high = payload.get("nozzle_temperature_range_high", [])
    limit = hardware_limits("X1C")["max_nozzle_temperature_c"]
    if any(float(value) > limit for value in high):
        payload["manufacturer_nozzle_temperature_range_high"] = deepcopy(high)
        payload["nozzle_temperature_range_high"] = [f"{min(float(value), limit):g}" for value in high]
    payload.update({"printer_model": "X1C", "target_printer": "Bambu Lab X1C", "native_profile_name": name,
        "inherits": name, "profile_completeness": "validated_complete", "slicing_supported": True,
        "material": payload["filament_type"][0], "vendor": payload["filament_vendor"][0],
        "compatible_nozzle_diameters_mm": sorted({float(re.search(r"([0-9.]+) nozzle", p)[1]) for p in authority["compatible_printers"]}),
        "ams_compatible": authority["ams_supported"], "ams_dry_material_required": authority.get("ams_dry_material_required", False),
        "hardened_nozzle_required": "-CF" in name or "-GF" in name})
    payload.setdefault("filament_start_gcode", "; filament start gcode\n")
    payload.setdefault("filament_end_gcode", "; filament end gcode\n")
    X1C_PROFILES.append(_profile("local.filament.x1c_" + hashlib.sha256(name.encode()).hexdigest()[:12], name + " · X1 Carbon", "filament", payload))
X1C_PROFILES = tuple(X1C_PROFILES)
