"""Synthetic Bambu material addressing; no network or printer commands."""
from __future__ import annotations
import ast
import importlib.util
from pathlib import Path
import sys
import types
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / "deploy/homeassistant/custom_components/ultimate_3d_studio"
PACKAGE = "studio_material_topology_test"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package

def load(name):
    spec = importlib.util.spec_from_file_location(PACKAGE + "." + name, COMPONENT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

topology = load("ams_topology")

class MaterialTopologyTests(unittest.TestCase):
    def test_telemetry_normalization_preserves_multiple_units_and_external(self):
        issues = types.ModuleType(PACKAGE + ".printer_issues")
        issues.normalize_hms_item = lambda value: value
        issues.normalize_print_error = lambda value: value
        sys.modules[issues.__name__] = issues
        telemetry = load("telemetry")
        result = telemetry.normalize_ams({"print": {
            "ams": {"tray_now": "4", "ams": [
                {"id": "0", "info": "1", "tray": [{"id": "0", "tray_type": "PLA"}]},
                {"id": "1", "info": "3", "humidity": "4", "humidity_raw": "23", "dry_time": 45, "tray": [{"id": "0", "tray_type": "PETG"}]},
            ]}, "vt_tray": {"id": "254", "tray_type": "PLA", "tray_color": "112233FF"}}})
        self.assertEqual([slot["slot_index"] for slot in result["slots"]], [0, 4])
        self.assertEqual([slot["active"] for slot in result["slots"]], [False, True])
        self.assertEqual(result["kind"], "ams_mixed")
        self.assertEqual(result["units"][1]["humidity_percent"], 23)
        self.assertEqual(result["units"][1]["humidity_level"], 4)
        self.assertEqual(result["units"][1]["drying_remaining_minutes"], 45)
        self.assertEqual(result["external_spool"]["color"], "#112233")
        self.assertFalse(result["external_spool"]["loaded"])
        missing = telemetry.normalize_ams({"ams": {"tray": [{"tray_type": "PLA"}]}})
        self.assertEqual(missing["slots"][0]["slot_index"], -1)

    def test_protocol_generation_bits(self):
        for value, kind in [("1001", "ams"), ("2", "ams_lite"), ("103", "ams_2_pro"), ("4", "ams_ht")]:
            with self.subTest(value=value):
                self.assertEqual(topology.ams_identity({"info": value})["kind"], kind)

    def test_four_slots_do_not_identify_generation(self):
        self.assertEqual(topology.ams_identity({"tray": [{"id": str(i)} for i in range(4)]})["kind"], "ams_unknown")
        self.assertFalse(topology.ams_identity({"info": "corrupt"})["generation_known"])

    def test_explicit_ams_names(self):
        self.assertEqual(topology.ams_identity({"model": "AMS 2 Pro"})["type_code"], 3)
        self.assertIsNone(topology.ams_identity({"model": "AMS 2"})["type_code"])

    def test_multiple_units_have_distinct_firmware_slots(self):
        addresses = [topology.global_slot_index(unit, tray, 3) for unit in range(4) for tray in range(4)]
        self.assertEqual(addresses, list(range(16)))
        self.assertFalse(topology.active_slot("4", "0", "0", 0))
        self.assertTrue(topology.active_slot("4", "1", "0", 4))
        self.assertTrue(topology.active_slot("1:0", "1", "0", 4))

    def test_ht_uses_own_address_space(self):
        self.assertEqual(topology.global_slot_index(128, 0, 4), 16)
        self.assertEqual(topology.global_slot_index(129, 0, 4), 17)
        self.assertIsNone(topology.global_slot_index(128, 1, 4))

    def test_unknown_and_virtual_addresses_are_not_ams_slots(self):
        for unit, tray in [(255, 0), (254, 0), (-1, 0), (0, 254), (True, 0), (None, 0)]:
            with self.subTest(unit=unit, tray=tray):
                self.assertIsNone(topology.global_slot_index(unit, tray, None))
        self.assertFalse(topology.active_slot("254", 0, 0, 0))

    def test_external_serialization_and_regular_slots(self):
        tree = ast.parse((COMPONENT / "network_plugin/commands.py").read_text(encoding="utf-8-sig"))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "build_ams_filament_setting")
        namespace = {"Any": object, "NetworkCommand": dict, "build_command": lambda *args, **fields: fields}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "material-command", "exec"), namespace)
        build = namespace[function.name]
        fields = dict(tray_info_idx="GFA99", tray_color="#123456", nozzle_temp_min=190, nozzle_temp_max=240, tray_type="PLA")
        external = build(ams_id=255, tray_id=0, **fields)
        self.assertEqual((external["ams_id"], external["slot_id"], external["tray_id"]), (255, 0, 254))
        self.assertEqual(external["tray_color"], "123456FF")
        regular = build(ams_id=2, tray_id=3, **fields)
        self.assertEqual((regular["ams_id"], regular["slot_id"], regular["tray_id"]), (2, 3, 3))
        with self.assertRaises(ValueError):
            build(ams_id=255, tray_id=254, **fields)

    def test_x1c_identity_and_conflicts(self):
        identity = load("printer_identity")
        self.assertEqual(identity.resolve_connected_printer_model("BL-P001", "00M000000000001"), "X1C")
        self.assertIsNone(identity.resolve_connected_printer_model("A1", "00M000000000001"))
        self.assertIsNone(identity.resolve_connected_printer_model("X1C", "00W000000000001"))

    def test_x1c_catalog_is_not_a1_and_no_unknown_fallback(self):
        catalog = load("manual_filament_catalog")
        printer = types.SimpleNamespace(model="X1C", serial="00M000000000001")
        rows = catalog.catalog_for_printer(printer)
        self.assertGreater(len(rows), 10)
        self.assertTrue(all("@BBL" not in row["name"] or "@BBL X1C" in row["name"] for row in rows))
        self.assertIn("Fiberon PA12-CF @BBL X1C", {row["name"] for row in rows})
        self.assertIn("Bambu Lab", {row["vendor"] for row in rows})
        self.assertIn("SUNLU", {row["vendor"] for row in rows})
        self.assertTrue(all("ams_slot" not in row["targets"] for row in rows if row["material_type"] == "TPU" and "for AMS" not in row["name"]))
        self.assertEqual(catalog.catalog_for_printer(types.SimpleNamespace(model="X1C", serial=None)), [])

    def test_conflicting_material_id_stays_excluded_after_third_variant(self):
        from unittest.mock import patch
        catalog = load("manual_filament_catalog")
        settings = {"filament_id": ["synthetic-id"], "filament_type": ["PLA"],
                    "nozzle_temperature_range_low": [190], "nozzle_temperature_range_high": [240]}
        rows = {str(i): {"settings": {**settings, "nozzle_temperature_range_high": [high]}}
                for i, high in enumerate([240, 250, 240])}
        printer = types.SimpleNamespace(model="X1C", serial="00M000000000001")
        with patch.object(catalog, "native_defaults", return_value={"filaments": rows}):
            self.assertEqual(catalog.catalog_for_printer(printer), [])

    def test_machine_start_uses_selected_nozzle_authority(self):
        presets = load("gcode_preset_contract")
        authority = load("printer_model_contract").x1c_defaults()
        starts = []
        for diameter in (0.2, 0.4, 0.6, 0.8):
            catalog = {"selection": {"nozzle_profile_id": "test-nozzle"}, "profiles": [
                *presets.GCODE_DEFAULT_PROFILES,
                {"id": "test-nozzle", "kind": "nozzle", "payload": {"diameter_mm": diameter}},
            ]}
            result = presets.resolve_gcode_presets(catalog, "X1C")
            native = authority["machines"][str(diameter)]["machine_start_gcode"]
            self.assertEqual(result["settings"]["machine_start_gcode"], native)
            self.assertEqual(result["nozzle_diameter_mm"], diameter)
            starts.append(native)
        self.assertEqual(len(set(starts)), 4)

    def test_cross_nozzle_start_preset_is_rejected(self):
        presets = load("gcode_preset_contract")
        catalog = {"selection": {"nozzle_profile_id": "test-nozzle", "gcode_preset_ids": {
            "gcode_1": "builtin.x1c.0_4.gcode_1"}}, "profiles": [*presets.GCODE_DEFAULT_PROFILES,
            {"id": "test-nozzle", "kind": "nozzle", "payload": {"diameter_mm": 0.2}}]}
        with self.assertRaisesRegex(ValueError, "Düse"):
            presets.resolve_gcode_presets(catalog, "X1C")

if __name__ == "__main__":
    unittest.main()
