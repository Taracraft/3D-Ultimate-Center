"""Independent authority for supported single-nozzle Bambu printers."""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re


def canonical_model(value: object) -> str | None:
    key = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    aliases = {"a1": "A1", "bambu a1": "A1", "bambu lab a1": "A1",
               "h2s": "H2S", "bambu h2s": "H2S", "bambu lab h2s": "H2S"}
    return aliases.get(key)


def hardware_limits(value: object) -> dict | None:
    model = canonical_model(value)
    if model == "A1":
        return {"max_nozzle_temperature_c": 300., "max_bed_temperature_c": 100.,
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
