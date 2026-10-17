"""Editable H2S profiles captured from installed native sources."""
from copy import deepcopy
import hashlib
import re
from .printer_model_contract import h2s_defaults, hardware_limits


def _profile(identifier, name, kind, payload):
    return {"id": identifier, "name": name, "kind": kind, "source": "local", "builtin": False,
            "base_id": None, "version": "20261003", "created_at": None, "updated_at": None,
            "payload": payload}


H2S_PROFILES = [_profile("local.printer.h2s", "Bambu Lab H2S", "printer", {
    "vendor": "Bambu Lab", "model": "H2S", "technology": "FFF", "build_volume_mm": [340,320,340],
    **hardware_limits("H2S"), "physical_extruder_count": 1})]
for diameter, machine in h2s_defaults()["machines"].items():
    process = h2s_defaults()["processes"][diameter]
    suffix = diameter.replace(".", "_")
    H2S_PROFILES += [
        _profile("local.nozzle.h2s_" + suffix, "H2S " + diameter + " mm gehärteter Stahl", "nozzle",
                 {"printer": "Bambu Lab H2S", "diameter_mm": float(diameter), "material": "hardened_steel"}),
        _profile("local.process.h2s_" + suffix, "H2S " + str(process["layer_height"]) + " mm Standard", "process",
                 {"printer_model": "H2S", "target_printer": "Bambu Lab H2S", "nozzle_diameter_mm": float(diameter),
                  "layer_height_mm": process["layer_height"], "first_layer_height_mm": .2,
                  "slicing_supported": True})]
for surface, name in [("textured_pei", "Texturierte PEI"), ("smooth_pei", "Glatte PEI")]:
    H2S_PROFILES.append(_profile("local.build_plate.h2s_" + surface, "H2S " + name + " · 340×320 mm", "build_plate",
        {"surface": surface, "width_mm": 340, "depth_mm": 320, "printer_model": "H2S"}))
for name, authority in h2s_defaults()["filaments"].items():
    payload = {key: ([value[0]] if isinstance(value, list) and value else deepcopy(value)) for key, value in authority["settings"].items()}
    payload.update({"printer_model": "H2S", "target_printer": "Bambu Lab H2S", "native_profile_name": name,
        "inherits": name, "profile_completeness": "validated_complete", "slicing_supported": True,
        "material": payload["filament_type"][0], "vendor": "Generic",
        "compatible_nozzle_diameters_mm": sorted({float(re.search(r"([0-9.]+) nozzle", p)[1]) for p in authority["compatible_printers"]}),
        "ams_compatible": authority["ams_supported"],
        "hardened_nozzle_required": True})
    payload.setdefault("filament_start_gcode", "; filament start gcode\n")
    payload.setdefault("filament_end_gcode", "; filament end gcode\n")
    H2S_PROFILES.append(_profile("local.filament.h2s_" + hashlib.sha256(name.encode()).hexdigest()[:12], name, "filament", payload))
H2S_PROFILES = tuple(H2S_PROFILES)
