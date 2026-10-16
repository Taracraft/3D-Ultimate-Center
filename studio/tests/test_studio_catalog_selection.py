"""Synthetic archive-to-catalog-to-staging integration; no engine or network calls."""
from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import asdict
import copy
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
try:
    import prepare_catalog_selection as selection
    import build_engine_bundle as bundle
    import engine_catalog as catalog
    import package_staging as staging
finally:
    sys.path.remove(str(ROOT / "Slicer-Server"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(engine):
    payloads = {catalog.ENTRYPOINTS[engine]: b"\x7fELFsynthetic-not-executed", "licenses/NOTICE.txt": b"Synthetic test data; no runtime or license approval."}
    roles = {catalog.ENTRYPOINTS[engine]: "engine", "licenses/NOTICE.txt": "license"}
    if engine == "bambu_studio":
        payloads.update({"resources/info.txt": b"resource", "resources/profiles/machine/test.json": b"{}"})
        roles.update({"resources/info.txt": "resources", "resources/profiles/machine/test.json": "profiles"})
    elif engine == "prusaslicer":
        payloads.update({"resources/info.txt": b"resource", "resources/profiles/test.ini": b"[print:test]\n", "lib/PrusaSlicer/OCCTWrapper.so": b"synthetic-plugin"})
        roles.update({"resources/info.txt": "resources", "resources/profiles/test.ini": "profiles", "lib/PrusaSlicer/OCCTWrapper.so": "runtime"})
    else:
        payloads.update({selection.CURA_BASE: b'{"version":2,"settings":{}}', "resources/definitions/test.def.json": b'{"inherits":"fdmprinter"}'})
        roles.update({selection.CURA_BASE: "profiles", "resources/definitions/test.def.json": "profiles"})
    manifest = {"schema": 1, "engine": engine, "version": "1.0.0", "system": "linux", "architecture": "amd64",
        "upstream_archives": [{"id": "fixture", "bytes": 1, "sha256": "a" * 64}],
        "files": [{"path": p, "bytes": len(raw), "sha256": sha(raw), "role": roles[p], "executable": roles[p] == "engine"} for p, raw in sorted(payloads.items())],
        **{key: False for key in selection.FLAGS}}
    return manifest, payloads


def make_archive(path, manifest, payloads):
    with path.open("xb") as stream:
        with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as archive:
                for name, raw in sorted({**payloads, bundle.MANIFEST_NAME: bundle.canonical(manifest)}.items()):
                    info = tarfile.TarInfo(name)
                    info.size = len(raw)
                    info.mode = 0o755 if name == catalog.ENTRYPOINTS[manifest["engine"]] else 0o644
                    archive.addfile(info, io.BytesIO(raw))


def artifact(engine, archive=None):
    return {"id": "bundle", "component_version": "1.0.0", "url": "https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/fixture-1/engine.tar.gz",
        "sha256": sha(archive.read_bytes()) if archive else "b" * 64, "size_bytes": archive.stat().st_size if archive else 1,
        "format": "tar.gz", "license": "TEST-ONLY-NOT-AN-APPROVAL", "source_url": catalog.UPSTREAMS[engine] + "tree/" + "a" * 40, "source_revision": "a" * 40}


class CatalogSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.manifest, self.payloads = fixture("curaengine")

    def project(self, value=None):
        raw = bundle.canonical(value if value is not None else self.manifest)
        return selection.project_manifest(raw, sha(raw))

    def reject(self, value):
        with self.assertRaises((ValueError, TypeError)):
            self.project(value)

    def test_cura_original_role_difference_is_reproduced(self):
        raw = bundle.canonical(self.manifest)
        naive = [{"path": f["path"], "size_bytes": f["bytes"], "sha256": f["sha256"], "role": f["role"], "executable": f["executable"]} for f in self.manifest["files"]]
        with self.assertRaisesRegex(catalog.CatalogError, "missing_resources"):
            catalog._release({"engine": "curaengine", "version": "1.0.0", "system": "linux", "architecture": "amd64", "artifacts": [{**artifact("curaengine"), "files": naive}]})
        self.assertEqual(selection.bind_release(raw, sha(raw), artifact("curaengine")).engine, "curaengine")

    def test_only_cura_base_role_changes_and_inputs_are_unchanged(self):
        before = copy.deepcopy(self.manifest)
        result = self.project()
        self.assertEqual(self.manifest, before)
        self.assertEqual(len(result["role_adjustments"]), 1)
        original = {row["path"]: row for row in before["files"]}
        for row in result["files"]:
            source = original[row["path"]]
            for key, oldkey in (("path", "path"), ("size_bytes", "bytes"), ("sha256", "sha256"), ("executable", "executable")):
                self.assertEqual(row[key], source[oldkey])
            self.assertEqual(row["role"], "resources" if row["path"] == selection.CURA_BASE else source["role"])
        self.assertEqual(result["file_count"], len(before["files"]))

    def test_three_engines_pass_existing_catalog_and_real_local_staging(self):
        for engine in catalog.ENTRYPOINTS:
            with self.subTest(engine=engine):
                manifest, payloads = fixture(engine)
                raw = bundle.canonical(manifest)
                archive = self.work / (engine + ".tar.gz")
                make_archive(archive, manifest, payloads)
                original_hash = sha(archive.read_bytes())
                self.assertTrue(bundle.verify(archive, manifest))
                release = selection.bind_release(raw, sha(raw), artifact(engine, archive))
                with mock.patch.object(staging, "_download", side_effect=AssertionError("network forbidden")):
                    prepared = staging.prepare_release(release, self.work, archives={"bundle": archive})
                root = prepared / "payload" / engine
                self.assertEqual({p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}, payloads)
                receipt = json.loads((prepared / "READY.json").read_bytes())
                self.assertFalse(receipt["activated"])
                self.assertFalse(receipt["engine_executed"])
                self.assertEqual(sha(archive.read_bytes()), original_hash)
                self.assertFalse((root / bundle.MANIFEST_NAME).exists())
                self.assertTrue(bundle.verify(archive, manifest))

    def test_bambu_and_prusa_roles_preserved(self):
        for engine in ("bambu_studio", "prusaslicer"):
            with self.subTest(engine=engine):
                manifest, _ = fixture(engine)
                result = self.project(manifest)
                self.assertEqual(result["role_adjustments"], [])
                self.assertEqual({r["path"]: r["role"] for r in result["files"]}, {r["path"]: r["role"] for r in manifest["files"]})

    def test_already_classified_base_needs_no_adjustment(self):
        for row in self.manifest["files"]:
            if row["path"] == selection.CURA_BASE:
                row["role"] = "resources"
        self.assertEqual(self.project()["role_adjustments"], [])

    def test_other_resource_does_not_replace_required_cura_base(self):
        for row in self.manifest["files"]:
            if row["path"] == selection.CURA_BASE:
                row["path"] = "resources/info.txt"
                row["role"] = "resources"
        self.reject(self.manifest)

    def test_cura_base_is_not_reclassified_from_unexpected_roles(self):
        original = copy.deepcopy(self.manifest)
        for role in ("license", "runtime", "engine", "source"):
            value = copy.deepcopy(original)
            next(r for r in value["files"] if r["path"] == selection.CURA_BASE)["role"] = role
            with self.subTest(role=role):
                self.reject(value)

    def test_cura_still_requires_a_profile_besides_the_base(self):
        self.manifest["files"] = [r for r in self.manifest["files"] if r["path"] != "resources/definitions/test.def.json"]
        self.reject(self.manifest)

    def test_missing_license_or_engine_rejected(self):
        for role in ("license", "engine"):
            value = copy.deepcopy(self.manifest)
            value["files"] = [r for r in value["files"] if r["role"] != role]
            with self.subTest(role=role):
                self.reject(value)

    def test_empty_or_executable_cura_base_rejected(self):
        for changes in ({"bytes": 0}, {"bytes": True}, {"executable": True}):
            value = copy.deepcopy(self.manifest)
            next(r for r in value["files"] if r["path"] == selection.CURA_BASE).update(changes)
            with self.subTest(changes=changes):
                self.reject(value)

    def test_missing_prusa_plugin_stays_rejected(self):
        manifest, _ = fixture("prusaslicer")
        manifest["files"] = [r for r in manifest["files"] if r["role"] != "runtime"]
        raw = bundle.canonical(manifest)
        with self.assertRaises(catalog.CatalogError):
            selection.bind_release(raw, sha(raw), artifact("prusaslicer"))

    def test_external_manifest_digest_is_required(self):
        raw = bundle.canonical(self.manifest)
        for expected in ("f" * 64, "0" * 64, "latest", None):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                selection.project_manifest(raw, expected)

    def test_duplicate_json_keys_and_non_integer_numbers_rejected(self):
        for raw in (b'{"schema":1,"schema":1}', b'{"schema":NaN}', b'{"schema":1.0}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                selection.project_manifest(raw, sha(raw))

    def test_manifest_unknown_fields_and_flags_rejected(self):
        for key, value in [("extra", 1), ("schema", True), ("system", "windows"), ("architecture", "arm64")]:
            with self.subTest(key=key):
                self.reject({**self.manifest, key: value})
        for flag in selection.FLAGS:
            with self.subTest(flag=flag):
                self.reject({**self.manifest, flag: True})

    def test_duplicate_case_colliding_and_parent_child_paths_rejected(self):
        for path in (selection.CURA_BASE, selection.CURA_BASE.upper(), "resources"):
            value = copy.deepcopy(self.manifest)
            row = copy.deepcopy(next(r for r in value["files"] if r["path"] == selection.CURA_BASE))
            row["path"] = path
            value["files"].append(row)
            with self.subTest(path=path):
                self.reject(value)

    def test_catalog_and_staging_path_guards_are_reused(self):
        for path in ("../escape", "resources/../escape", "resources/C:file", "resources/name?x", "resources/CON.txt", "resources/a*.txt"):
            value = copy.deepcopy(self.manifest)
            next(r for r in value["files"] if r["role"] == "license")["path"] = path
            with self.subTest(path=path):
                self.reject(value)

    def test_file_hash_size_and_execution_contracts(self):
        for changes in ({"sha256": "bad"}, {"bytes": -1}, {"bytes": True}, {"role": "source"}, {"executable": True}):
            value = copy.deepcopy(self.manifest)
            next(r for r in value["files"] if r["role"] == "license").update(changes)
            with self.subTest(changes=changes):
                self.reject(value)

    def test_zero_length_noncritical_file_is_preserved(self):
        self.manifest["files"].append({"path": "resources/empty.txt", "bytes": 0, "sha256": sha(b""), "role": "resources", "executable": False})
        self.assertEqual(next(r for r in self.project()["files"] if r["path"] == "resources/empty.txt")["size_bytes"], 0)

    def test_whole_selection_is_detached_and_deterministic(self):
        first = self.project()
        original = copy.deepcopy(self.manifest)
        first["files"][0]["path"] = "changed"
        first["upstream_archives"][0]["bytes"] = 99
        self.assertEqual(original, self.manifest)
        self.assertEqual(bundle.canonical(self.project()), bundle.canonical(self.project()))

    def test_861_synthetic_cura_profile_roles_become_860_plus_one(self):
        root = next(r for r in self.manifest["files"] if r["path"] == selection.CURA_BASE)
        other = next(r for r in self.manifest["files"] if r["path"] == "resources/definitions/test.def.json")
        self.manifest["files"] = [r for r in self.manifest["files"] if r["role"] != "profiles"] + [root]
        self.manifest["files"] += [{**other, "path": f"resources/definitions/fixture_{i:04d}.def.json"} for i in range(860)]
        result = self.project()
        self.assertEqual(result["role_counts"]["profiles"], 860)
        self.assertEqual(result["role_counts"]["resources"], 1)
        self.assertEqual(result["file_count"], 863)
        self.assertEqual(len(result["role_adjustments"]), 1)

    def test_artifact_descriptor_requires_exact_version_format_and_fields(self):
        raw = bundle.canonical(self.manifest)
        for changes in ({"component_version": "2.0.0"}, {"format": "zip"}, {"sha256": "0" * 64}, {"extra": 1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                selection.bind_release(raw, sha(raw), {**artifact("curaengine"), **changes})

    def test_artifact_origin_and_source_revision_guards_are_unchanged(self):
        raw = bundle.canonical(self.manifest)
        for changes in ({"url": "https://untrusted.example/archive.tar.gz"}, {"source_revision": "main"}, {"source_url": "https://github.com/other/repo/tree/" + "a" * 40}):
            with self.subTest(changes=changes), self.assertRaises(catalog.CatalogError):
                selection.bind_release(raw, sha(raw), {**artifact("curaengine"), **changes})

    def test_corrupt_archive_still_rejected_by_staging(self):
        raw = bundle.canonical(self.manifest)
        path = self.work / "archive.tar.gz"
        make_archive(path, self.manifest, self.payloads)
        release = selection.bind_release(raw, sha(raw), artifact("curaengine", path))
        path.write_bytes(path.read_bytes()[:-1] + b"x")
        with self.assertRaises(ValueError):
            staging.prepare_release(release, self.work, archives={"bundle": path})
        self.assertEqual(list(self.work.glob('.engine-stage-*')), [])

    def test_prepare_creates_only_new_external_proposal(self):
        raw = bundle.canonical(self.manifest)
        path = self.work / "bundle-manifest.json"
        path.write_bytes(raw)
        output = self.work / "proposal"
        result = selection.prepare(path, sha(raw), output)
        self.assertEqual({p.name for p in output.iterdir()}, {"file-selection.json"})
        self.assertEqual(sha((output / "file-selection.json").read_bytes()), result["selection_sha256"])
        self.assertEqual(path.read_bytes(), raw)
        self.assertFalse(result["catalog_updated"])
        self.assertFalse(result["archive_verified"])
        self.assertFalse(result["release_approved"])
        before = (output / "file-selection.json").read_bytes()
        with self.assertRaises(ValueError):
            selection.prepare(path, sha(raw), output)
        self.assertEqual((output / "file-selection.json").read_bytes(), before)

    def test_invalid_manifest_has_no_output_side_effect(self):
        path = self.work / "bundle-manifest.json"
        path.write_bytes(b"{}")
        output = self.work / "proposal"
        with self.assertRaises(ValueError):
            selection.prepare(path, sha(b"{}"), output)
        self.assertFalse(output.exists())

    def test_input_changes_before_output_are_rejected(self):
        raw = bundle.canonical(self.manifest)
        path = self.work / "bundle-manifest.json"
        path.write_bytes(raw)
        real = selection.snapshot
        calls = 0
        def changed(p, maximum):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_bytes(b"{}")
            return real(p, maximum)
        with mock.patch.object(selection, "snapshot", side_effect=changed), self.assertRaises(ValueError):
            selection.prepare(path, sha(raw), self.work / "proposal")
        self.assertFalse((self.work / "proposal").exists())

    def test_cli_failure_is_secret_free_and_nonzero(self):
        path = self.work / "bundle-manifest.json"
        path.write_text('{"sensitive":"never-echo-this-marker"}')
        output = io.StringIO()
        with redirect_stdout(output):
            code = selection.main(["--manifest", str(path), "--expected-manifest-sha256", sha(path.read_bytes()), "--output", str(self.work / "proposal")])
        self.assertEqual(code, 2)
        self.assertNotIn("never-echo-this-marker", output.getvalue())
        self.assertFalse((self.work / "proposal").exists())

    def test_shipped_catalog_and_validator_are_never_modified(self):
        paths = [ROOT / 'Slicer-Server/engine_catalog.py', ROOT / 'Slicer-Server/engine_catalog.json']
        before = {p: p.read_bytes() for p in paths}
        for engine in catalog.ENTRYPOINTS:
            manifest, _ = fixture(engine)
            raw = bundle.canonical(manifest)
            selection.bind_release(raw, sha(raw), artifact(engine))
        self.assertEqual(before, {p: p.read_bytes() for p in paths})

    def test_debian_epoch_version_preserved(self):
        self.manifest['version'] = '1:5.0.0-5'
        raw = bundle.canonical(self.manifest)
        descriptor = {**artifact('curaengine'), 'component_version': '1:5.0.0-5'}
        release = selection.bind_release(raw, sha(raw), descriptor)
        self.assertEqual(release.version, '1:5.0.0-5')
        self.assertEqual(release.artifacts[0].component_version, release.version)

    def test_proposal_cannot_be_written_into_product_source(self):
        raw = bundle.canonical(self.manifest)
        path = self.work / 'bundle-manifest.json'
        path.write_bytes(raw)
        target = ROOT / '_catalog_selection_forbidden_test_output'
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(selection.SelectionError, 'output_inside_source'):
            selection.prepare(path, sha(raw), target)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
