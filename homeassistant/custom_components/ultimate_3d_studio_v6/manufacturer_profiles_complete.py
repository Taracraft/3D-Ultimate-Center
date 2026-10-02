"""Complete distinct eSUN and SUNLU FDM material families for Bambu Lab A1.

Color-only variants, spool weights and bundles deliberately share their material
profile. Every record is local, cloud-sync protected and removable/hideable.
"""
from __future__ import annotations

from typing import Any

from .curated_local_profiles import _filament, _local


def _a1_process(profile_id: str, name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _local(profile_id, "process", f"Bambu Lab A1 · {name}", {
        "printer_vendor": "Bambu Lab",
        "printer_model": "A1",
        "target_printer": "Bambu Lab A1",
        "a1_specific": True,
        **payload,
    })


A1_COMPLETE_PROCESS_PROFILES: tuple[dict[str, Any], ...] = (
    _a1_process("local.process.a1_0_2_0_06_ultra", "0,2 mm Düse · 0,06 mm Ultra Detail", {"nozzle_diameter_mm": 0.2, "layer_height_mm": 0.06, "first_layer_height_mm": 0.12, "walls": 3, "top_shell_layers": 8, "bottom_shell_layers": 6, "infill_percent": 15, "outer_wall_speed_mm_s": 25, "inner_wall_speed_mm_s": 45, "travel_speed_mm_s": 300}),
    _a1_process("local.process.a1_0_2_0_10_detail", "0,2 mm Düse · 0,10 mm Detail", {"nozzle_diameter_mm": 0.2, "layer_height_mm": 0.10, "first_layer_height_mm": 0.14, "walls": 3, "top_shell_layers": 7, "bottom_shell_layers": 6, "infill_percent": 15, "outer_wall_speed_mm_s": 30, "inner_wall_speed_mm_s": 55, "travel_speed_mm_s": 320}),
    _a1_process("local.process.a1_0_4_0_12_quality", "0,4 mm Düse · 0,12 mm Qualität", {"nozzle_diameter_mm": 0.4, "layer_height_mm": 0.12, "first_layer_height_mm": 0.20, "walls": 3, "top_shell_layers": 6, "bottom_shell_layers": 5, "infill_percent": 15, "outer_wall_speed_mm_s": 50, "inner_wall_speed_mm_s": 100, "travel_speed_mm_s": 450}),
    _a1_process("local.process.a1_0_4_0_16_optimal", "0,4 mm Düse · 0,16 mm Optimal", {"nozzle_diameter_mm": 0.4, "layer_height_mm": 0.16, "first_layer_height_mm": 0.20, "walls": 3, "top_shell_layers": 5, "bottom_shell_layers": 4, "infill_percent": 15, "outer_wall_speed_mm_s": 60, "inner_wall_speed_mm_s": 130, "travel_speed_mm_s": 500}),
    _a1_process("local.process.a1_0_4_0_20_standard", "0,4 mm Düse · 0,20 mm Standard", {"nozzle_diameter_mm": 0.4, "layer_height_mm": 0.20, "first_layer_height_mm": 0.20, "walls": 3, "top_shell_layers": 5, "bottom_shell_layers": 4, "infill_percent": 15, "outer_wall_speed_mm_s": 70, "inner_wall_speed_mm_s": 150, "travel_speed_mm_s": 500}),
    _a1_process("local.process.a1_0_4_petg_quality", "0,4 mm Düse · PETG Qualität", {"nozzle_diameter_mm": 0.4, "material_class": "PETG", "layer_height_mm": 0.20, "first_layer_height_mm": 0.24, "walls": 3, "top_shell_layers": 5, "bottom_shell_layers": 5, "infill_percent": 15, "outer_wall_speed_mm_s": 45, "inner_wall_speed_mm_s": 90, "travel_speed_mm_s": 400}),
    _a1_process("local.process.a1_0_4_silk_quality", "0,4 mm Düse · Silk Glanz", {"nozzle_diameter_mm": 0.4, "material_class": "PLA Silk", "layer_height_mm": 0.16, "first_layer_height_mm": 0.20, "walls": 3, "top_shell_layers": 6, "bottom_shell_layers": 5, "infill_percent": 12, "outer_wall_speed_mm_s": 35, "inner_wall_speed_mm_s": 70, "travel_speed_mm_s": 350}),
    _a1_process("local.process.a1_0_4_tpu", "0,4 mm Düse · TPU/Flex", {"nozzle_diameter_mm": 0.4, "material_class": "TPU", "layer_height_mm": 0.20, "first_layer_height_mm": 0.24, "walls": 3, "top_shell_layers": 5, "bottom_shell_layers": 5, "infill_percent": 12, "outer_wall_speed_mm_s": 25, "inner_wall_speed_mm_s": 35, "travel_speed_mm_s": 180}),
    _a1_process("local.process.a1_0_6_0_24_strength", "0,6 mm Düse · 0,24 mm Stärke", {"nozzle_diameter_mm": 0.6, "layer_height_mm": 0.24, "first_layer_height_mm": 0.28, "walls": 4, "top_shell_layers": 5, "bottom_shell_layers": 5, "infill_percent": 25, "outer_wall_speed_mm_s": 60, "inner_wall_speed_mm_s": 120, "travel_speed_mm_s": 450}),
    _a1_process("local.process.a1_0_6_0_30_standard", "0,6 mm Düse · 0,30 mm Standard", {"nozzle_diameter_mm": 0.6, "layer_height_mm": 0.30, "first_layer_height_mm": 0.30, "walls": 3, "top_shell_layers": 4, "bottom_shell_layers": 4, "infill_percent": 18, "outer_wall_speed_mm_s": 70, "inner_wall_speed_mm_s": 135, "travel_speed_mm_s": 450}),
    _a1_process("local.process.a1_0_8_0_40_draft", "0,8 mm Düse · 0,40 mm Entwurf", {"nozzle_diameter_mm": 0.8, "layer_height_mm": 0.40, "first_layer_height_mm": 0.40, "walls": 3, "top_shell_layers": 4, "bottom_shell_layers": 4, "infill_percent": 15, "outer_wall_speed_mm_s": 65, "inner_wall_speed_mm_s": 120, "travel_speed_mm_s": 420}),
)


ESUN_MISSING_PROFILES: tuple[dict[str, Any], ...] = (
    _filament("local.filament.esun_pla_silk_candy", "eSUN", "PLA-Silk Candy", "PLA Silk", (210, 230), 55, 11, fan=(50, 100), drying=(45, 4)),
    _filament("local.filament.esun_pla_coffee", "eSUN", "PLA-Coffee", "PLA Filled", (205, 225), 55, 10, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_luminous_rainbow", "eSUN", "PLA-Luminous Rainbow", "PLA Glow", (205, 230), 55, 9, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_pla_refill", "eSUN", "PLA+ Refilament", "PLA+", (205, 225), 55, 20, drying=(45, 4)),
    _filament("local.filament.esun_pla_matte_refill", "eSUN", "PLA-Matte Refilament", "PLA Matte", (190, 220), 55, 16, drying=(45, 4)),
    _filament("local.filament.esun_epa", "eSUN", "ePA", "PA", (250, 280), 80, 8, fan=(0, 30), drying=(80, 12), enclosure="recommended"),
    _filament("local.filament.esun_epa_cf", "eSUN", "ePA-CF", "PA-CF", (260, 290), 85, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_epa_gf", "eSUN", "ePA-GF", "PA-GF", (260, 290), 85, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_epa_ht_cf", "eSUN", "ePAHT-CF", "PAHT-CF", (280, 300), 100, 6, fan=(0, 15), drying=(90, 12), enclosure="required", abrasive=True, hardened_nozzle=True, notes="Visible for catalog completeness; A1 open frame is not recommended."),
    _filament("local.filament.esun_epa12_cf", "eSUN", "ePA12-CF", "PA12-CF", (260, 290), 85, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.esun_tpu_hs", "eSUN", "TPU-HS", "TPU High Speed", (220, 245), 45, 6, fan=(50, 100), drying=(55, 6)),
    _filament("local.filament.esun_tpu_87a", "eSUN", "TPU-87A", "TPU 87A", (220, 245), 45, 3, fan=(50, 100), drying=(55, 8)),
    _filament("local.filament.esun_tpu_85a", "eSUN", "TPU-85A", "TPU 85A", (220, 245), 45, 2.8, fan=(50, 100), drying=(55, 8)),
)


SUNLU_MISSING_PROFILES: tuple[dict[str, Any], ...] = (
    _filament("local.filament.sunlu_antistring_pla", "SUNLU", "AntiString PLA", "PLA", (195, 215), 55, 18, drying=(45, 4)),
    _filament("local.filament.sunlu_easy_abs", "SUNLU", "Easy ABS", "ABS", (235, 255), 90, 14, fan=(0, 20), drying=(70, 6), enclosure="required"),
    _filament("local.filament.sunlu_high_speed_abs", "SUNLU", "High Speed ABS", "ABS-HS", (250, 270), 100, 20, fan=(0, 15), drying=(70, 6), enclosure="required"),
    _filament("local.filament.sunlu_abs_gf", "SUNLU", "ABS-GF", "ABS-GF", (250, 270), 100, 10, fan=(0, 15), drying=(75, 8), enclosure="required", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_abs_fr", "SUNLU", "ABS-FR", "ABS-FR", (250, 275), 100, 9, fan=(0, 10), drying=(75, 8), enclosure="required"),
    _filament("local.filament.sunlu_pc_abs", "SUNLU", "PC-ABS", "PC-ABS", (260, 290), 100, 8, fan=(0, 15), drying=(80, 10), enclosure="required"),
    _filament("local.filament.sunlu_pp", "SUNLU", "PP", "PP", (220, 250), 85, 8, fan=(0, 30), drying=(65, 8), enclosure="recommended", notes="Requires PP-compatible build surface or packing-tape adhesion."),
    _filament("local.filament.sunlu_peek", "SUNLU", "PEEK", "PEEK", (360, 420), 140, 3, fan=(0, 0), drying=(120, 12), enclosure="required", notes="Catalog completeness only: outside Bambu Lab A1 temperature capability; do not select for A1 printing."),
    _filament("local.filament.sunlu_easy_pa", "SUNLU", "Easy PA", "PA", (245, 275), 80, 8, fan=(0, 30), drying=(80, 12), enclosure="recommended"),
    _filament("local.filament.sunlu_pa6_cf", "SUNLU", "PA6-CF", "PA6-CF", (270, 300), 90, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pa6_gf", "SUNLU", "PA6-GF", "PA6-GF", (270, 300), 90, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pa12_cf", "SUNLU", "PA12-CF", "PA12-CF", (260, 290), 85, 7, fan=(0, 20), drying=(85, 12), enclosure="recommended", abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_tpu_silk", "SUNLU", "TPU-Silk", "TPU Silk", (215, 240), 45, 3.5, fan=(50, 100), drying=(55, 8)),
    _filament("local.filament.sunlu_pvb", "SUNLU", "PVB", "PVB", (190, 220), 55, 10, fan=(50, 100), drying=(45, 6)),
    _filament("local.filament.sunlu_lw_pla", "SUNLU", "LW-PLA", "PLA-LW", (210, 250), 55, 8, fan=(50, 100), drying=(50, 5), notes="Foaming filament; calibrate flow ratio at selected temperature."),
    _filament("local.filament.sunlu_pla_transparent", "SUNLU", "PLA Transparent", "PLA Transparent", (200, 225), 55, 14, fan=(30, 80), drying=(45, 4)),
    _filament("local.filament.sunlu_pla_transparent_rainbow", "SUNLU", "PLA Transparent Rainbow", "PLA Transparent", (200, 225), 55, 13, fan=(30, 80), drying=(45, 4)),
    _filament("local.filament.sunlu_pla_glow", "SUNLU", "PLA Glow in the Dark", "PLA Glow", (205, 230), 55, 9, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_petg_glow", "SUNLU", "PETG Glow in the Dark", "PETG Glow", (235, 260), 75, 10, fan=(30, 70), drying=(60, 8), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pla_twinkling", "SUNLU", "PLA Twinkling", "PLA Glitter", (205, 230), 55, 10, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pla_galaxy", "SUNLU", "PLA Galaxy", "PLA Glitter", (205, 230), 55, 10, drying=(45, 5), abrasive=True, hardened_nozzle=True),
    _filament("local.filament.sunlu_pla_matte_dual", "SUNLU", "PLA Matte Dual-Color", "PLA Matte", (200, 225), 55, 15, drying=(45, 4)),
    _filament("local.filament.sunlu_silk_pla_plus", "SUNLU", "Silk PLA+", "PLA Silk", (210, 235), 55, 11, fan=(50, 100), drying=(45, 4)),
    _filament("local.filament.sunlu_multi_color_silk", "SUNLU", "Multi-Color Silk PLA", "PLA Silk", (210, 235), 55, 10, fan=(50, 100), drying=(45, 4)),
    _filament("local.filament.sunlu_petg_rainbow", "SUNLU", "PETG Rainbow", "PETG", (235, 255), 70, 12, fan=(30, 70), drying=(60, 6)),
    _filament("local.filament.sunlu_high_speed_pla_plus", "SUNLU", "High Speed PLA+", "PLA+HS", (210, 235), 55, 25, drying=(45, 4)),
    _filament("local.filament.sunlu_high_speed_matte_pla", "SUNLU", "High Speed Matte PLA", "PLA Matte HS", (210, 235), 55, 22, drying=(45, 4)),
)


COMPLETE_MANUFACTURER_PROFILES: tuple[dict[str, Any], ...] = (
    *A1_COMPLETE_PROCESS_PROFILES,
    *ESUN_MISSING_PROFILES,
    *SUNLU_MISSING_PROFILES,
)