"""Independent authority for supported single-nozzle Bambu printers."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re


def canonical_model(value: object) -> str | None:
    key = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    aliases = {"a1": "A1", "bambu a1": "A1", "bambu lab a1": "A1",
               "x1c": "X1C", "x1 carbon": "X1C", "x1 carbon combo": "X1C",
               "bambu x1c": "X1C", "bambu lab x1c": "X1C",
               "bambu lab x1 carbon": "X1C", "3dprinter x1 carbon": "X1C",
               "h2s": "H2S", "bambu h2s": "H2S", "bambu lab h2s": "H2S"}
    return aliases.get(key)


def hardware_limits(value: object) -> dict | None:
    model = canonical_model(value)
    if model == "A1":
        return {"max_nozzle_temperature_c": 300., "max_bed_temperature_c": 100.,
                "width_mm": 256., "depth_mm": 256., "height_mm": 256.}
    if model == "X1C":
        # Manufacturer: 110 C at 220 V, 120 C at 110 V. Use the common safe limit.
        return {"max_nozzle_temperature_c": 300., "max_bed_temperature_c": 110.,
                "width_mm": 256., "depth_mm": 256., "height_mm": 256.}
    if model == "H2S":
        return {"max_nozzle_temperature_c": 350., "max_bed_temperature_c": 120.,
                "max_chamber_temperature_c": 65., "width_mm": 340.,
                "depth_mm": 320., "height_mm": 340.}
    return None


@lru_cache(maxsize=1)
def h2s_defaults() -> dict:
    data = json.loads(Path(__file__).with_name("h2s_native_defaults.json").read_text())
    if data.get("schema") != 1 or data.get("model") != "H2S":
        raise ValueError("Ungültige native H2S-Profilautorität.")
    return deepcopy(data)



@lru_cache(maxsize=1)
def x1c_defaults() -> dict:
    data = json.loads(Path(__file__).with_name("x1c_native_defaults.json").read_text())
    if data.get("schema") != 1 or data.get("model") != "X1C":
        raise ValueError("Invalid native X1 Carbon profile authority.")
    return deepcopy(data)


def native_defaults(value: object) -> dict:
    model = canonical_model(value)
    if model == "H2S":
        return h2s_defaults()
    if model == "X1C":
        return x1c_defaults()
    raise ValueError("No native profile authority for this printer.")


def max_material_channels(value: object) -> int:
    return 16 if canonical_model(value) == "X1C" else 4
