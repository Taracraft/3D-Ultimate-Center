"""Cura graph regressions use temporary synthetic data, never a real engine."""
from dataclasses import FrozenInstanceError
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio_cura_definitions", ROOT / "Slicer-Server/cura_definitions.py")
definitions = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = definitions
spec.loader.exec_module(definitions)


class DefinitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.resources = Path(self.temp.name) / "resources"
        for kind in ("definitions", "extruders"):
            (self.resources / kind).mkdir(parents=True)
        self.write("fdmprinter", settings={})
        self.write("fdmextruder", settings={})
        self.write("base", inherits="fdmprinter", metadata={"machine_extruder_trains": {"0": "nozzle"}})
        self.write("printer", inherits="base")
        self.write("nozzle", kind="extruders", inherits="fdmextruder")

    def write(self, ident, kind="definitions", **extra):
        path = self.resources / kind / (ident + ".def.json")
        path.write_text(json.dumps({"version": 2, "name": ident, **extra}), encoding="utf-8")
        return path

    def inspect(self):
        return definitions.inspect_definitions(self.resources)

    def reject(self, code):
        with self.assertRaisesRegex(definitions.DefinitionError, "^" + code + "$"):
            self.inspect()

    def test_valid_counts_and_inherited_dependencies(self):
        result = self.inspect()
        self.assertEqual(result.summary()["definitions"], 4)
        self.assertEqual(result.summary()["extruders"], 1)
        self.assertEqual(result.summary()["parent_edges"], 3)
        self.assertEqual(result.summary()["train_references"], 1)
        self.assertEqual({f.id for f in result.dependencies("printer")},
                         {"printer", "base", "fdmprinter", "nozzle", "fdmextruder"})

    def test_byte_hashes_and_immutable_result(self):
        result = self.inspect()
        for row in result.files:
            data = (self.resources / row.relative_path).read_bytes()
            self.assertEqual(row.sha256, hashlib.sha256(data).hexdigest())
            self.assertEqual(row.size_bytes, len(data))
        with self.assertRaises(FrozenInstanceError):
            result.files[0].id = "changed"

    def test_dependency_selection_rejects_unknown_and_extruder(self):
        result = self.inspect()
        for value in ["absent", "../printer", "nozzle", "fdmextruder", [], None]:
            with self.subTest(value=value), self.assertRaisesRegex(definitions.DefinitionError, "unknown_printer"):
                result.dependencies(value)

    def test_missing_parent(self):
        self.write("printer", inherits="absent")
        self.reject("missing_parent")

    def test_parent_cycle(self):
        self.write("base", inherits="printer")
        self.reject("inheritance_cycle")

    def test_self_parent(self):
        self.write("printer", inherits="printer")
        self.reject("inheritance_cycle")

    def test_chain_limit(self):
        with patch.object(definitions, "MAX_CHAIN", 2):
            self.reject("inheritance_depth_limit")

    def test_missing_base(self):
        (self.resources / "definitions/fdmprinter.def.json").unlink()
        self.reject("missing_base_definition")

    def test_base_cannot_inherit(self):
        self.write("fdmprinter", inherits="base")
        self.reject("missing_base_definition")

    def test_unrecognized_root(self):
        self.write("printer")
        self.reject("wrong_base_definition")

    def test_printer_cannot_inherit_extruder(self):
        self.write("printer", inherits="fdmextruder")
        self.reject("wrong_base_definition")

    def test_extruder_cannot_inherit_printer(self):
        self.write("nozzle", kind="extruders", inherits="fdmprinter")
        self.reject("wrong_base_definition")

    def test_base_extruder_is_a_valid_default_train(self):
        self.write("fdmprinter", settings={}, metadata={"machine_extruder_trains": {"0": "fdmextruder"}})
        result = self.inspect()
        self.assertIn("fdmextruder", {row.id for row in result.dependencies("printer")})

    def test_missing_train(self):
        self.write("base", inherits="fdmprinter", metadata={"machine_extruder_trains": {"0": "absent"}})
        self.reject("missing_extruder")

    def test_train_must_be_extruder_file(self):
        self.write("base", inherits="fdmprinter", metadata={"machine_extruder_trains": {"0": "printer"}})
        self.reject("missing_extruder")

    def test_invalid_train_collection(self):
        self.write("base", inherits="fdmprinter", metadata={"machine_extruder_trains": []})
        self.reject("invalid_extruder_trains")

    def test_invalid_train_indices(self):
        for key in ["-1", "01", "../0", "1000", "one"]:
            with self.subTest(key=key):
                self.write("base", inherits="fdmprinter", metadata={"machine_extruder_trains": {key: "nozzle"}})
                self.reject("invalid_extruder_index")

    def test_extruder_cannot_own_trains(self):
        self.write("nozzle", kind="extruders", inherits="fdmextruder",
                   metadata={"machine_extruder_trains": {"0": "nozzle"}})
        self.reject("invalid_extruder_owner")

    def test_invalid_reference_id(self):
        for value in ["../fdmprinter", "/fdmprinter", r"folder\fdmprinter", ".", "bad.", [], None]:
            with self.subTest(value=value):
                self.write("printer", inherits=value)
                self.reject("invalid_definition_id")

    def test_schema_is_exact_integer(self):
        path = self.resources / "definitions/printer.def.json"
        for value in [True, 1, "2", 3]:
            with self.subTest(value=value):
                path.write_text(json.dumps({"version": value, "inherits": "fdmprinter"}))
                self.reject("unsupported_definition_schema")

    def test_metadata_type(self):
        self.write("printer", inherits="fdmprinter", metadata=[])
        self.reject("invalid_metadata")

    def test_settings_type(self):
        for field in ["settings", "overrides"]:
            with self.subTest(field=field):
                self.write("printer", inherits="fdmprinter", **{field: []})
                self.reject("invalid_settings")

    def test_json_duplicates_constants_and_parse_errors(self):
        path = self.resources / "definitions/printer.def.json"
        for data, code in [
            (b'{"version":2,"version":2}', "duplicate_json_key"),
            (b'{"version":2,"value":NaN}', "invalid_json_constant"),
            (b'{', "invalid_json"), (b'\xff', "invalid_json"),
            (b'[]', "invalid_definition"), (b'[' * 1200, "invalid_json"),
        ]:
            with self.subTest(code=code):
                path.write_bytes(data); self.reject(code)

    def test_expressions_are_never_evaluated(self):
        self.write("printer", inherits="fdmprinter",
                   overrides={"test": {"value": "__import__('os').system('never-run')"}})
        with patch("builtins.eval", side_effect=AssertionError("evaluation forbidden")):
            self.inspect()

    def test_duplicate_ids_across_directories_ignore_case(self):
        self.write("PRINTER", kind="extruders", inherits="fdmextruder")
        self.reject("duplicate_definition_id")

    def test_nested_directory_not_followed(self):
        (self.resources / "definitions/subfolder").mkdir()
        self.reject("unsafe_definition_file")

    def test_unexpected_file_rejected(self):
        (self.resources / "definitions/launcher.sh").write_text("never execute")
        self.reject("unexpected_definition_file")

    def test_file_count_bound(self):
        with patch.object(definitions, "MAX_FILES", 4):
            self.reject("definition_count_limit")

    def test_single_file_size_bound(self):
        with patch.object(definitions, "MAX_FILE_BYTES", 1):
            self.reject("definition_size_limit")

    def test_total_size_bound(self):
        with patch.object(definitions, "MAX_TOTAL_BYTES", 1):
            self.reject("definition_total_limit")

    def test_missing_resource_root(self):
        with self.assertRaisesRegex(definitions.DefinitionError, "unsafe_resource_root"):
            definitions.inspect_definitions(self.resources / "absent")

    def test_missing_directory(self):
        (self.resources / "extruders/nozzle.def.json").unlink()
        (self.resources / "extruders").rmdir()
        self.reject("unsafe_definition_directory")

    @unittest.skipIf(sys.platform == "win32", "Windows symlinks require extra privileges")
    def test_symlink_root(self):
        other = self.resources.with_name("linked")
        other.symlink_to(self.resources, target_is_directory=True)
        with self.assertRaisesRegex(definitions.DefinitionError, "unsafe_resource_root"):
            definitions.inspect_definitions(other)

    @unittest.skipIf(sys.platform == "win32", "Windows symlinks require extra privileges")
    def test_symlink_directory(self):
        path = self.resources / "definitions"
        target = self.resources / "saved"
        path.rename(target)
        path.symlink_to(target, target_is_directory=True)
        self.reject("unsafe_definition_directory")

    @unittest.skipIf(sys.platform == "win32", "Windows symlinks require extra privileges")
    def test_symlink_file(self):
        path = self.resources / "definitions/printer.def.json"
        path.unlink()
        path.symlink_to(self.resources / "definitions/base.def.json")
        self.reject("unsafe_definition_file")


if __name__ == "__main__":
    unittest.main()
