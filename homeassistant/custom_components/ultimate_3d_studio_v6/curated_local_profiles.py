"""Curated local Bambu A1, eSUN and SUNLU profile catalog.

These profiles are intentionally independent from Bambu Cloud synchronization.
They remain removable through the normal V6 profile removal workflow.
"""
from __future__ import annotations

from typing import Any

STAMP = "2026-07-22T00:00:00+00:00"


def _local(profile_id: str, kind: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "process":
        payload = {
            "start_sound_gcode": "",
            "end_sound_gcode": "",
            "custom_gcode_1": "",
            "custom_gcode_2": "",
            **payload,
        }
    return {
        "id": profile_id,
        "kind": kind,
        "name": name,
        "source": "local",
        "payload": {
            **payload,
            "profile_origin": "Studio curated local catalog",
            "cloud_sync_protected": True,
        },
        "builtin": False,
        "cloud_managed": False,
        "curated_local": True,
        "created_at": STAMP,
        "updated_at": STAMP,
    }


def _filament(
    profile_id: str,
    vendor: str,
    name: str,
    material: str,
    nozzle: tuple[int, int],
    bed: int,
    mvs: float,
    *,
    fan: tuple[int, int] = (30, 100),
    density: float | None = None,
    drying: tuple[int, int] | None = None,
    enclosure: str = "optional",
    abrasive: bool = False,
    hardened_nozzle: bool = False,
    notes: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "vendor": vendor,
        "material": material,
        "sub_brand": name,
        "diameter_mm": 1.75,
        "nozzle_temperature_c": list(nozzle),
        "recommended_nozzle_temperature_c": round((nozzle[0] + nozzle[1]) / 2),
        "bed_temperature_c": bed,
        "max_volumetric_speed_mm3_s": mvs,
        "cooling_fan_min_percent": fan[0],
        "cooling_fan_max_percent": fan[1],
        "enclosure": enclosure,
        "abrasive": abrasive,
        "hardened_nozzle_required": hardened_nozzle,
        "bambu_a1_compatibility": "supported" if enclosure != "required" else "limited_open_frame",
        "tuning_strategy": "manufacturer range with conservative Bambu A1 flow limit",
    }
    if density is not None:
        payload["density_g_cm3"] = density
    if drying is not None:
        payload["drying_temperature_c"] = drying[0]
        payload["drying_time_hours"] = drying[1]
    if notes:
        payload["notes"] = notes
    return _local(profile_id, "filament", f"{vendor} {name}", payload)


A1_LOCAL_PROFILES: tuple[dict[str, Any], ...] = (
    _local("local.printer.bambu_a1_0_2", "printer", "Bambu Lab A1 · 0,2 mm", {
        "vendor": "Bambu Lab", "model": "A1", "technology": "FFF",
        "build_volume_mm": [256, 256, 256], "nozzle_diameter_mm": 0.2,
        "default_nozzle_profile_id": "local.nozzle.a1_0_2_stainless",
        "max_nozzle_temperature_c": 300, "max_bed_temperature_c": 100,
    }),
    _local("local.printer.bambu_a1_0_4", "printer", "Bambu Lab A1 · 0,4 mm", {
        "vendor": "Bambu Lab", "model": "A1", "technology": "FFF",
        "build_volume_mm": [256, 256, 256], "nozzle_diameter_mm": 0.4,
        "default_nozzle_profile_id": "local.nozzle.a1_0_4_stainless",
        "max_nozzle_temperature_c": 300, "max_bed_temperature_c": 100,
    }),
    _local("local.printer.bambu_a1_0_6", "printer", "Bambu Lab A1 · 0,6 mm", {
        "vendor": "Bambu Lab", "model": "A1", "technology": "FFF",
        "build_volume_mm": [256, 256, 256], "nozzle_diameter_mm": 0.6,
        "default_nozzle_profile_id": "local.nozzle.a1_0_6_hardened",
        "max_nozzle_temperature_c": 300, "max_bed_temperature_c": 100,
    }),
    _local("local.printer.bambu_a1_0_8", "printer", "Bambu Lab A1 · 0,8 mm", {
        "vendor": "Bambu Lab", "model": "A1", "technology": "FFF",
        "build_volume_mm": [256, 256, 256], "nozzle_diameter_mm": 0.8,
        "default_nozzle_profile_id": "local.nozzle.a1_0_8_hardened",
        "max_nozzle_temperature_c": 300, "max_bed_temperature_c": 100,
    }),
    _local("local.nozzle.a1_0_2_stainless", "nozzle", "A1 0,2 mm Edelstahl", {"diameter_mm": 0.2, "material": "stainless_steel", "printer": "Bambu Lab A1"}),
    _local("local.nozzle.a1_0_4_stainless", "nozzle", "A1 0,4 mm Edelstahl", {"diameter_mm": 0.4, "material": "stainless_steel", "printer": "Bambu Lab A1"}),
    _local("local.nozzle.a1_0_6_stainless", "nozzle", "A1 0,6 mm Edelstahl", {"diameter_mm": 0.6, "material": "stainless_steel", "printer": "Bambu Lab A1"}),
    _local("local.nozzle.a1_0_8_stainless", "nozzle", "A1 0,8 mm Edelstahl", {"diameter_mm": 0.8, "material": "stainless_steel", "printer": "Bambu Lab A1"}),
    _local("local.nozzle.a1_0_4_hardened", "nozzle", "A1 0,4 mm gehärteter Stahl", {"diameter_mm": 0.4, "material": "hardened_steel", "printer": "Bambu Lab A1"}),
    _local("local.nozzle.a1_0_6_hardened", "nozzle", "A1 0,6 mm gehärteter Stahl", {"diameter_mm": 0.6, "material": "hardened_steel", "printer": "Bambu Lab A1"}),
    _local("local.nozzle.a1_0_8_hardened", "nozzle", "A1 0,8 mm gehärteter Stahl", {"diameter_mm": 0.8, "material": "hardened_steel", "printer": "Bambu Lab A1"}),
    _local("local.process.a1_0_08_hq", "process", "A1 0,08 mm High Quality", {"layer_height_mm": 0.08, "first_layer_height_mm": 0.16, "walls": 3, "top_shell_layers": 7, "bottom_shell_layers": 5, "infill_percent": 15, "outer_wall_speed_mm_s": 40, "inner_wall_speed_mm_s": 80, "travel_speed_mm_s": 400}),
    _local("local.process.a1_0_12_hq", "process", "A1 0,12 mm High Quality", {"layer_height_mm": 0.12, "first_layer_height_mm": 0.20, "walls": 3, "top_shell_layers": 6, "bottom_shell_layers": 5, "infill_percent": 15, "outer_wall_speed_mm_s": 50, "inner_wall_speed_mm_s": 100, "travel_speed_mm_s": 450}),
    _local("local.process.a1_0_16_optimal", "process", "A1 0,16 mm Optimal", {"layer_height_mm": 0.16, "first_layer_height_mm": 0.20, "walls": 3, "top_shell_layers": 5, "bottom_shell_layers": 4, "infill_percent": 15, "outer_wall_speed_mm_s": 60, "inner_wall_speed_mm_s": 130, "travel_speed_mm_s": 500}),
    _local("local.process.a1_0_20_standard", "process", "A1 0,20 mm Standard", {"layer_height_mm": 0.20, "first_layer_height_mm": 0.20, "walls": 3, "top_shell_layers": 5, "bottom_shell_layers": 4, "infill_percent": 15, "outer_wall_speed_mm_s": 70, "inner_wall_speed_mm_s": 150, "travel_speed_mm_s": 500}),
    _local("local.process.a1_0_24_strength", "process", "A1 0,24 mm Stärke", {"layer_height_mm": 0.24, "first_layer_height_mm": 0.24, "walls": 4, "top_shell_layers": 5, "bottom_shell_layers": 5, "infill_percent": 25, "outer_wall_speed_mm_s": 65, "inner_wall_speed_mm_s": 140, "travel_speed_mm_s": 500}),
    _local("local.process.a1_0_28_draft", "process", "A1 0,28 mm Entwurf", {"layer_height_mm": 0.28, "first_layer_height_mm": 0.24, "walls": 2, "top_shell_layers": 4, "bottom_shell_layers": 4, "infill_percent": 10, "outer_wall_speed_mm_s": 90, "inner_wall_speed_mm_s": 180, "travel_speed_mm_s": 500}),
)


ESUN_LOCAL_PROFILES: tuple[dict[str, Any], ...] = (
    _filament("local.filament.esun_pla_basic", "eSUN", "PLA Basic", "PLA", (190, 220), 55, 18, drying=(45, 4)),
    _filament("local.filament.esun_pla_plus", "eSUN", "PLA+", "PLA+", (205, 225), 55, 20, drying=(45, 4)),
    _filament("local.filament.esun_pla_plus_hs", "eSUN", "PLA+HS", "PLA+HS", (210, 230), 55, 24, drying=(45, 4)),
    _filament("local.filament.esun_pla_hs", "eSUN", "PLA-HS", "PLA-HS", (210, 230), 55, 25, drying=(45, 4)),
    _filament("local.filament.esun_pla_hf", "eSUN", "PLA-HF", "PLA-HF", (210, 230), 55, 26, drying=(45, 4)),
    _filament("local.filament.esun_pla_lite", "eSUN", "PLA-Lite", "PLA", (190, 220), 50, 16, drying=(45, 4)),
    _filament("local.filament.esun_pla_matte", "eSUN", "PLA Matte", "PLA Matte", (190, 220), 55, 16, drying=(45, 4)),
    _filament("local.filament.esun_pla_silk", "eSUN", "PLA Silk", "PLA Silk", (210, 230), 55, 12, fan=(50, 100), drying=(45, 4)),
    _filament("local.filament.esun_pla_silk_magic", "eSUN", "PLA Silk Magic", "PLA Silk", (210, 230), 55, 11, drying=(45, 4)),
    _filament("local.filament.esun_pla_silk_mystic", "eSUN", "PLA Silk Mystic", "PLA Silk", (210, 230), 55, 11, drying=(45, 4)),
    _filament("local.filament.esun_pla_silk_rainbow", "eSUN", "PLA Silk Rainbow", "PLA Silk", (210, 230), 55, 11, drying=(45, 4)),
    _filament("local.filament.esun_pla_marble", "eSUN", "PLA Marble", "PLA", (205, 225), 55, 13, drying=(45, 4), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_wood", "eSUN", "PLA Wood", "PLA Wood", (190, 220), 50, 10, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_metal", "eSUN", "PLA Metal", "PLA Metal", (205, 230), 55, 10, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_cf", "eSUN", "PLA-CF", "PLA-CF", (210, 230), 55, 12, drying=(50, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_gf", "eSUN", "PLA-GF", "PLA-GF", (210, 235), 55, 12, drying=(50, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_st", "eSUN", "PLA-ST", "PLA-ST", (210, 230), 55, 16, drying=(45, 4)),
    _filament("local.filament.esun_pla_lw", "eSUN", "PLA-LW", "PLA-LW", (210, 250), 55, 8, fan=(50, 100), drying=(50, 5), notes="Foaming material; calibrate flow ratio per temperature."),
    _filament("local.filament.esun_pla_cast", "eSUN", "PLA Cast", "PLA Cast", (190, 220), 50, 10, drying=(45, 4)),
    _filament("local.filament.esun_pla_luminous", "eSUN", "PLA Luminous", "PLA", (205, 225), 55, 10, drying=(45, 4), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_color_change", "eSUN", "PLA Color Change", "PLA", (205, 225), 55, 12, drying=(45, 4)),
    _filament("local.filament.esun_petg", "eSUN", "PETG", "PETG", (230, 250), 70, 13, fan=(30, 70), drying=(60, 6), notes="Conservative A1 profile to reduce stringing and weak glossy layers."),
    _filament("local.filament.esun_petg_basic", "eSUN", "PETG Basic", "PETG", (230, 250), 70, 14, fan=(30, 70), drying=(60, 6)),
    _filament("local.filament.esun_petg_plus", "eSUN", "PETG+", "PETG+", (235, 255), 70, 15, fan=(25, 65), drying=(60, 6)),
    _filament("local.filament.esun_petg_plus_hs", "eSUN", "PETG+HS", "PETG+HS", (240, 260), 70, 20, fan=(30, 70), drying=(60, 6), notes="High-speed PETG; start at 18 mm³/s and increase only after flow calibration."),
    _filament("local.filament.esun_petg_hs", "eSUN", "PETG HS", "PETG HS", (240, 260), 70, 20, fan=(30, 70), drying=(60, 6)),
    _filament("local.filament.esun_petg_matte", "eSUN", "PETG Matte", "PETG Matte", (240, 260), 65, 16, fan=(50, 100), density=1.35, drying=(60, 6)),
    _filament("local.filament.esun_petg_cf", "eSUN", "PETG-CF", "PETG-CF", (240, 260), 75, 12, fan=(20, 60), drying=(65, 8), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_petg_esd", "eSUN", "PETG-ESD", "PETG-ESD", (240, 265), 75, 10, fan=(20, 50), drying=(65, 8), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_petg_lw", "eSUN", "PETG-LW", "PETG-LW", (240, 270), 70, 8, fan=(30, 70), drying=(60, 8)),
    _filament("local.filament.esun_petg_uv", "eSUN", "PETG UV Color Change", "PETG", (235, 255), 70, 12, fan=(30, 70), drying=(60, 6)),
    _filament("local.filament.esun_abs", "eSUN", "ABS", "ABS", (240, 260), 95, 14, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.esun_abs_plus", "eSUN", "ABS+", "ABS+", (240, 260), 95, 15, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.esun_abs_plus_hs", "eSUN", "ABS+HS", "ABS+HS", (250, 270), 100, 20, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.esun_abs_ht", "eSUN", "ABS-HT", "ABS-HT", (250, 275), 100, 12, fan=(0, 10), drying=(75, 8), enclosure="required"),
    _filament("local.filament.esun_abs_cf", "eSUN", "ABS-CF", "ABS-CF", (250, 270), 100, 11, fan=(0, 15), drying=(75, 8), enclosure="required", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_abs_gf", "eSUN", "ABS-GF", "ABS-GF", (250, 270), 100, 11, fan=(0, 15), drying=(75, 8), enclosure="required", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_abs_esd", "eSUN", "ABS-ESD", "ABS-ESD", (250, 275), 100, 9, fan=(0, 10), drying=(75, 8), enclosure="required", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_asa", "eSUN", "ASA", "ASA", (245, 265), 100, 12, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.esun_asa_cf", "eSUN", "ASA-CF", "ASA-CF", (250, 275), 100, 10, fan=(0, 15), drying=(75, 8), enclosure="required", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pa", "eSUN", "PA", "PA", (250, 280), 80, 8, fan=(0, 30), drying=(80, 12), enclosure="recommended"),
    _filament("local.filament.esun_pa6_cf", "eSUN", "PA6-CF", "PA6-CF", (270, 300), 90, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pa_cf", "eSUN", "PA-CF", "PA-CF", (260, 290), 85, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pa12", "eSUN", "PA12", "PA12", (250, 280), 80, 8, fan=(0, 25), drying=(80, 12), enclosure="recommended"),
    _filament("local.filament.esun_pa12_cf", "eSUN", "PA12-CF", "PA12-CF", (260, 290), 85, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pc", "eSUN", "PC", "PC", (260, 290), 100, 8, fan=(0, 20), drying=(80, 10), enclosure="required"),
    _filament("local.filament.esun_pc_esd", "eSUN", "PC-ESD", "PC-ESD", (270, 300), 100, 7, fan=(0, 15), drying=(85, 12), enclosure="required", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_tpu_95a", "eSUN", "TPU-95A", "TPU 95A", (220, 240), 45, 4.5, fan=(50, 100), drying=(55, 6)),
    _filament("local.filament.esun_tpu_90a", "eSUN", "TPU-90A", "TPU 90A", (220, 245), 45, 3.5, fan=(50, 100), drying=(55, 6)),
    _filament("local.filament.esun_tpu_64d", "eSUN", "TPU-64D", "TPU 64D", (225, 250), 50, 5, fan=(40, 100), drying=(60, 6)),
    _filament("local.filament.esun_tpe_83a", "eSUN", "TPE-83A", "TPE 83A", (220, 245), 40, 2.5, fan=(50, 100), drying=(55, 8)),
    _filament("local.filament.esun_peba_85a", "eSUN", "PEBA-85A", "PEBA 85A", (230, 260), 45, 3, fan=(40, 100), drying=(70, 8)),
    _filament("local.filament.esun_peba_90a", "eSUN", "PEBA-90A", "PEBA 90A", (230, 260), 45, 3.5, fan=(40, 100), drying=(70, 8)),
    _filament("local.filament.esun_peba_lw", "eSUN", "PEBA-LW", "PEBA-LW", (235, 265), 45, 2.5, fan=(40, 100), drying=(70, 8)),
    _filament("local.filament.esun_pva", "eSUN", "PVA", "PVA Support", (190, 220), 50, 4, fan=(50, 100), drying=(55, 10)),
    _filament("local.filament.esun_hips", "eSUN", "HIPS", "HIPS Support", (230, 250), 95, 9, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.esun_clean", "eSUN", "Cleaning Filament", "Cleaning", (180, 260), 0, 2, fan=(0, 0)),
    _filament("local.filament.esun_pet_fr", "eSUN", "PET-FR", "PET-FR", (250, 280), 80, 8, fan=(10, 40), drying=(75, 8), enclosure="recommended"),
)


SUNLU_LOCAL_PROFILES: tuple[dict[str, Any], ...] = (
    _filament("local.filament.sunlu_pla", "SUNLU", "PLA", "PLA", (200, 220), 55, 18, drying=(45, 4)),
    _filament("local.filament.sunlu_pla_plus", "SUNLU", "PLA+", "PLA+", (205, 225), 55, 20, drying=(45, 4)),
    _filament("local.filament.sunlu_hs_pla", "SUNLU", "High Speed PLA", "PLA-HS", (210, 230), 55, 24, drying=(45, 4)),
    _filament("local.filament.sunlu_hs_pla_plus_2", "SUNLU", "High Speed PLA+ 2.0", "PLA+HS", (210, 235), 55, 26, drying=(45, 4)),
    _filament("local.filament.sunlu_pla_meta", "SUNLU", "PLA Meta", "PLA Meta", (185, 205), 50, 16, drying=(45, 4)),
    _filament("local.filament.sunlu_pla_matte", "SUNLU", "PLA Matte", "PLA Matte", (200, 220), 55, 16, drying=(45, 4)),
    _filament("local.filament.sunlu_pla_silk", "SUNLU", "Silk PLA", "PLA Silk", (210, 230), 55, 11, drying=(45, 4)),
    _filament("local.filament.sunlu_pla_rainbow", "SUNLU", "Rainbow PLA", "PLA", (205, 225), 55, 12, drying=(45, 4)),
    _filament("local.filament.sunlu_pla_marble", "SUNLU", "Marble PLA", "PLA", (205, 225), 55, 12, drying=(45, 4), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_hs_marble_pla", "SUNLU", "High Speed Marble PLA", "PLA-HS", (210, 230), 55, 18, drying=(45, 4), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pla_wood", "SUNLU", "Wood PLA", "PLA Wood", (190, 220), 50, 10, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pla_cf", "SUNLU", "PLA-CF", "PLA-CF", (210, 230), 55, 12, drying=(50, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_petg", "SUNLU", "PETG", "PETG", (230, 250), 70, 13, fan=(30, 70), drying=(60, 6), notes="Conservative A1 PETG profile; dry before tuning."),
    _filament("local.filament.sunlu_petg_plus", "SUNLU", "PETG+", "PETG+", (235, 255), 70, 15, fan=(25, 65), drying=(60, 6)),
    _filament("local.filament.sunlu_hs_matte_petg", "SUNLU", "High Speed Matte PETG", "PETG HS Matte", (240, 260), 75, 20, fan=(35, 75), density=1.28, drying=(50, 6), notes="For A1 use 240-260°C and begin at 18-20 mm³/s; manufacturer advertises higher speed at hotter extrusion."),
    _filament("local.filament.sunlu_petg_cf", "SUNLU", "PETG-CF", "PETG-CF", (240, 260), 75, 12, fan=(20, 60), drying=(65, 8), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_abs", "SUNLU", "ABS", "ABS", (240, 260), 95, 14, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.sunlu_abs_like", "SUNLU", "ABS Like", "ABS", (235, 255), 90, 13, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.sunlu_asa", "SUNLU", "ASA", "ASA", (245, 265), 100, 12, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.sunlu_tpu", "SUNLU", "TPU", "TPU 95A", (210, 230), 45, 4, fan=(50, 100), drying=(55, 6)),
    _filament("local.filament.sunlu_tpu_95a", "SUNLU", "TPU 95A", "TPU 95A", (215, 235), 45, 4.5, fan=(50, 100), drying=(55, 6)),
    _filament("local.filament.sunlu_pa", "SUNLU", "PA Nylon", "PA", (250, 280), 80, 8, fan=(0, 30), drying=(80, 12), enclosure="recommended"),
    _filament("local.filament.sunlu_pa_cf", "SUNLU", "PA-CF", "PA-CF", (260, 290), 85, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pc", "SUNLU", "PC", "PC", (260, 290), 100, 8, fan=(0, 20), drying=(80, 10), enclosure="required"),
    _filament("local.filament.sunlu_pva", "SUNLU", "PVA Support", "PVA Support", (190, 220), 50, 4, fan=(50, 100), drying=(55, 10)),
    _filament("local.filament.sunlu_hips", "SUNLU", "HIPS", "HIPS Support", (230, 250), 95, 9, fan=(0, 20), drying=(70, 6), enclosure="required"),
)


CURATED_LOCAL_PROFILES: tuple[dict[str, Any], ...] = (
    *A1_LOCAL_PROFILES,
    *ESUN_LOCAL_PROFILES,
    *SUNLU_LOCAL_PROFILES,
)