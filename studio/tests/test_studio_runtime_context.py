"""Engine-inclusive image contexts, using synthetic archive/file fixtures only."""
from __future__ import annotations

from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
try:
    import prepare_runtime_context as bridge
    import runtime_image_check as image_check
    import container_engines
finally:
    sys.path.remove(str(ROOT / "Slicer-Server"))
spec = importlib.util.spec_from_file_location("runtime_distribution_fixtures",
                                            ROOT / "tests/test_studio_engine_distribution.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


class RuntimeContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.DistributionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.work = self.fixture.work
        # Include genuine source-reference metadata in one synthetic catalog row.
        row = next(r for r in self.fixture.data["releases"] if r["engine"] == "curaengine")
        artifact = row["artifacts"][0]
        package, version = "cura-engine", "1.0.0-1"
        origin = fixtures.catalog.DEBIAN_SOURCE_PACKAGES["curaengine"][package]
        artifact["source_components"] = [{"id": "synthetic", "package": package,
            "component_version": version, "license": "TEST-ONLY-NOT-AN-APPROVAL",
            "source_revision": "c" * 64,
            "archives": [{"kind": k, "url": origin + n, "sha256": h * 64, "size_bytes": 1}
                         for k, n, h in [("descriptor", package + "_" + version + ".dsc", "c"),
                                        ("upstream", package + "_1.0.0.orig.tar.xz", "d"),
                                        ("debian_patches", package + "_" + version + ".debian.tar.xz", "e")]],
            "files": [f["path"] for f in artifact["files"]], "notices": ["licenses/NOTICE.txt"]}]
        self.fixture.write_catalog()
        self.fixture.assemble()
        self.distribution = self.fixture.output
        self.source = self.work / "source-context"
        self.source.mkdir()
        dockerfile = (ROOT / "Slicer-Server/Dockerfile").read_bytes()
        files = {"payload/server.py": b"synthetic source; never imported\n",
                 "payload/progress-pipe-reader.py": b"synthetic helper\n",
                 "licenses/NOTICE.txt": b"Synthetic source license notice\n"}
        for line in dockerfile.decode("utf-8-sig").splitlines():
            if line.startswith("COPY --chown=65532:65532 "):
                for name in line.split()[2:-1]:
                    if not name.endswith("/") and name != "context-manifest.json":
                        files[name] = ("synthetic:" + name + "\n").encode()
        manifest = {"schema": 1, "container_stage": "source-preflight", "container_deploy_ready": False,
                    "engine_included": False, "version": "0.1.0-test", "api_protocol": 2,
                    "files": [{"path": n, "size_bytes": len(r), "sha256": fixtures.digest(r)}
                              for n, r in sorted(files.items())]}
        files.update({"context-manifest.json": bridge.dist.canonical(manifest),
                      "Dockerfile": dockerfile, ".dockerignore": b"**\n!payload/**\n"})
        for name, raw in files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.compose = self.work / "compose.json"
        self.compose_doc = json.loads((ROOT / "Slicer-Server/compose.candidate.yaml").read_bytes())
        self.compose_doc["services"]["maintenance-clear"]["profiles"] = ["maintenance"]
        self.compose_doc["services"]["maintenance-clear"]["command"][2] = "${SLICER_BOOTSTRAP_REQUEST_ID:-}"
        self.write_compose()
        self.pins = [fixtures.digest((self.source / "context-manifest.json").read_bytes()),
                     fixtures.digest(dockerfile), self.fixture.catalog_hash, fixtures.digest(self.compose.read_bytes())]
        self.output = self.work / "runtime-context"
        self.input_before = {str(p): p.read_bytes() for root in (self.source, self.distribution)
                             for p in root.rglob("*") if p.is_file()}

    def write_compose(self):
        self.compose.write_bytes(bridge.dist.canonical(self.compose_doc))
        if hasattr(self, "pins"):
            self.pins[3] = fixtures.digest(self.compose.read_bytes())

    def prepare(self, **kwargs):
        return bridge.prepare(self.source, self.distribution, self.compose, self.output, *self.pins, **kwargs)

    def test_complete_context_and_metadata_are_verified_without_engine_or_build(self):
        with mock.patch.object(bridge.staging, "_download", side_effect=AssertionError("No network")), \
             mock.patch.object(bridge.activation, "activate_generation", side_effect=AssertionError("No activation")):
            result = self.prepare()
        self.assertTrue(result["runtime_context_verified"])
        self.assertTrue(result["engine_included"])
        for key in ("engine_executed", "image_built", "runtime_approved", "license_review_complete", "container_deploy_ready"):
            self.assertFalse(result[key])
        for name, payloads in self.fixture.payloads.items():
            for relative, raw in payloads.items():
                self.assertEqual((self.output / "engine" / name / relative).read_bytes(), raw)
        for name in (bridge.dist.CATALOG, bridge.dist.DESCRIPTION, bridge.dist.SOURCE_MANIFEST):
            self.assertEqual((self.output / "engine-distribution" / name).read_bytes(), (self.distribution / name).read_bytes())
        self.assertFalse((self.output / bridge.dist.ARCHIVE).exists())
        self.assertFalse((self.output / "engine-distribution" / bridge.dist.READY).exists())
        self.assertEqual(bridge.verify(self.output, *self.pins), result)
        self.assertEqual(self.input_before, {p: Path(p).read_bytes() for p in self.input_before})

    def test_compose_changes_only_the_two_engine_mounts_and_preserves_maintenance_profile(self):
        self.prepare()
        actual = json.loads((self.output / "compose.runtime.yaml").read_bytes())
        expected = copy.deepcopy(self.compose_doc)
        for name in ("api", "worker"):
            expected["services"][name]["volumes"] = [v for v in expected["services"][name]["volumes"] if v["target"] != "/engine"]
        self.assertEqual(actual, expected)
        self.assertEqual(actual["services"]["worker"]["network_mode"], "none")
        self.assertEqual(actual["services"]["worker"]["pid"], "service:api")
        self.assertEqual(actual["services"]["maintenance-clear"]["profiles"], ["maintenance"])

    def reconstruct_image(self):
        image = self.work / "synthetic-image"
        # Model COPY paths without invoking Docker or any source/engine code.
        shutil.copytree(self.output / "source", image / "opt/ultimate-slicer-server")
        for name in ("Dockerfile", ".dockerignore"):
            (image / "opt/ultimate-slicer-server" / name).unlink()
        shutil.copytree(self.output / "engine", image / "engine")
        destination = image / image_check.BASE
        destination.mkdir(parents=True)
        shutil.copytree(self.output / "engine-distribution", destination / "engine-distribution")
        for name in ("runtime_image_check.py", "image-manifest.json"):
            shutil.copyfile(self.output / name, destination / name)
        for row in json.loads((destination / "image-manifest.json").read_bytes())["files"]:
            (image / row["path"]).chmod(row["mode"])
        container_engines.prepare_image_layout(image)
        return image

    def test_reconstructed_image_paths_are_complete_and_default_check_is_read_only(self):
        self.prepare()
        image = self.reconstruct_image()
        self.assertEqual(container_engines.verify_image_layout(image)["image_resource_links"], "verified")
        before = {str(p): p.read_bytes() for p in image.rglob("*") if p.is_file() and not p.is_symlink()}
        result = image_check.verify(image)
        self.assertTrue(result["engine_included"])
        self.assertFalse(result["engine_executed"])
        self.assertFalse(result["runtime_approved"])
        self.assertEqual(before, {p: Path(p).read_bytes() for p in before})
        self.assertEqual(bridge.container_check.verify(image / "opt/ultimate-slicer-server")["source_integrity"], "verified")
        dockerfile = (self.output / "Dockerfile").read_text()
        self.assertIn("COPY --chown=65532:65532 engine/ /engine/", dockerfile)
        self.assertIn('ENTRYPOINT ["python3", "/' + image_check.BASE + '/runtime_image_check.py"]', dockerfile)
        self.assertLess(dockerfile.index("engine/ /engine/"), dockerfile.index("USER 65532:65532"))

    def test_changed_source_or_engine_cannot_be_authorized_by_rewriting_image_rows(self):
        self.prepare()
        image = self.reconstruct_image()
        manifest_path = image / image_check.BASE / "image-manifest.json"
        original_manifest = manifest_path.read_bytes()
        for name in ("engine/curaengine/bin/CuraEngine", "opt/ultimate-slicer-server/payload/server.py"):
            path = image / name
            before = path.read_bytes()
            path.write_bytes(b"forged-payload")
            manifest = json.loads(original_manifest)
            row = next(r for r in manifest["files"] if r["path"] == name)
            row.update(sha256=fixtures.digest(path.read_bytes()), size_bytes=path.stat().st_size)
            manifest_path.write_bytes(bridge.dist.canonical(manifest))
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "companion_binding"):
                image_check.verify(image)
            path.write_bytes(before)
            manifest_path.write_bytes(original_manifest)

    @unittest.skipIf(os.name == "nt", "POSIX mode normalization")
    def test_mode_normalization_validates_before_chmod(self):
        self.prepare()
        image = self.reconstruct_image()
        path = image / "engine/curaengine/bin/CuraEngine"
        path.chmod(0o644)
        self.assertTrue(image_check.normalize_modes(image)["engine_included"])
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)
        manifest_path = image / image_check.BASE / "image-manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        row = next(r for r in manifest["files"] if r["path"] == "engine/curaengine/bin/CuraEngine")
        row["mode"] = 0o777
        manifest_path.write_bytes(bridge.dist.canonical(manifest))
        with self.assertRaisesRegex(ValueError, "mode_rejected"):
            image_check.normalize_modes(image)
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    @unittest.skipIf(os.name == "nt", "POSIX mode normalization")
    def test_normalizer_never_uses_a_second_unvalidated_manifest_for_chmod(self):
        self.prepare()
        image = self.reconstruct_image()
        protected = image / "etc/protected"
        protected.parent.mkdir()
        protected.write_bytes(b"preserve mode")
        protected.chmod(0o644)
        manifest_path = image / image_check.BASE / "image-manifest.json"
        real = image_check.verify
        def replace_after_validation(*args, **kwargs):
            result = real(*args, **kwargs)
            if kwargs.get("check_modes") is False:
                manifest = json.loads(manifest_path.read_bytes())
                manifest["files"].append({"path": "etc/protected", "size_bytes": protected.stat().st_size,
                    "sha256": fixtures.digest(protected.read_bytes()), "mode": 0o777})
                manifest_path.write_bytes(bridge.dist.canonical(manifest))
            return result
        with mock.patch.object(image_check, "verify", side_effect=replace_after_validation), self.assertRaises(ValueError):
            image_check.normalize_modes(image)
        self.assertEqual(protected.stat().st_mode & 0o777, 0o644)

    def test_each_external_pin_is_required_before_output(self):
        for index in range(4):
            pins = self.pins[:]
            pins[index] = "f" * 64
            with self.subTest(pin=index), self.assertRaises(ValueError):
                bridge.prepare(self.source, self.distribution, self.compose, self.output, *pins)
            self.assertFalse(self.output.exists())

    def test_corrupt_last_engine_and_rewritten_self_receipt_do_not_pass(self):
        self.prepare()
        path = self.output / "engine/curaengine/bin/CuraEngine"
        path.write_bytes(b"changed")
        receipt_path = self.output / bridge.RECEIPT
        receipt = json.loads(receipt_path.read_bytes())
        row = next(r for r in receipt["files"] if r["path"] == "engine/curaengine/bin/CuraEngine")
        row.update(size_bytes=path.stat().st_size, sha256=fixtures.digest(path.read_bytes()))
        receipt_path.write_bytes(bridge.dist.canonical(receipt))
        with self.assertRaises(ValueError):
            bridge.verify(self.output, *self.pins)

    def test_each_generated_artifact_is_bound_even_if_receipt_hash_is_rewritten(self):
        self.prepare()
        for name in ("Dockerfile", "compose.runtime.yaml", "image-manifest.json", "runtime_image_check.py", ".dockerignore",
                     "engine-distribution/SOURCE_MANIFEST.json"):
            path = self.output / name
            before = path.read_bytes()
            path.write_bytes(before + b"\n")
            with self.subTest(name=name), self.assertRaises(ValueError):
                bridge.verify(self.output, *self.pins)
            path.write_bytes(before)

    def test_extra_file_and_empty_directory_are_rejected(self):
        self.prepare()
        for name in ("foreign-file", "foreign-dir"):
            path = self.output / name
            if name.endswith("dir"):
                path.mkdir()
            else:
                path.write_text("do not ship")
            with self.assertRaises(ValueError):
                bridge.verify(self.output, *self.pins)
            path.rmdir() if path.is_dir() else path.unlink()

    def test_unexpected_mount_or_weakened_isolation_fails_before_output(self):
        original = copy.deepcopy(self.compose_doc)
        for change in ("extra_mount", "network", "pid", "engine_writable", "maintenance_default"):
            self.compose_doc = copy.deepcopy(original)
            worker = self.compose_doc["services"]["worker"]
            if change == "extra_mount":
                worker["volumes"].append({"type": "bind", "source": "/secret", "target": "/run/secrets/foreign"})
            elif change == "network":
                worker["network_mode"] = "host"
            elif change == "pid":
                worker["pid"] = "host"
            elif change == "maintenance_default":
                self.compose_doc["services"]["maintenance-clear"].pop("profiles")
            else:
                next(v for v in worker["volumes"] if v["target"] == "/engine")["read_only"] = False
            self.write_compose()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse(self.output.exists())

    def test_copy_failure_or_cancellation_cleans_only_new_output(self):
        sentinel = self.work / "old-store"
        sentinel.write_bytes(b"keep")
        real = bridge.dist.regular
        def changed(path):
            if Path(path).as_posix().endswith("engine/curaengine/bin/CuraEngine") and list(self.work.glob(".runtime-context-*")):
                raise ValueError("synthetic_copy_failure")
            return real(path)
        with mock.patch.object(bridge.dist, "regular", side_effect=changed), self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.work.glob(".runtime-context-*")), [])
        with self.assertRaises(ValueError):
            self.prepare(cancelled=lambda: True)
        self.assertFalse(self.output.exists())
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_final_directory_appears_only_after_verification_and_never_replaces_a_racer(self):
        real = bridge._publish
        def competing_directory(stage, output):
            self.assertFalse(output.exists())
            self.assertTrue(bridge.verify(stage, *self.pins)["runtime_context_verified"])
            output.mkdir()
            (output / "foreign").write_bytes(b"preserve")
            real(stage, output)
        with mock.patch.object(bridge, "_publish", side_effect=competing_directory), self.assertRaises(OSError):
            self.prepare()
        self.assertEqual((self.output / "foreign").read_bytes(), b"preserve")
        self.assertEqual(list(self.work.glob(".runtime-context-*")), [])

    def test_existing_output_and_input_overlap_are_preserved(self):
        self.output.mkdir()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list(self.output.iterdir()), [])
        for target in (self.source / "inside", self.distribution / "inside"):
            with self.assertRaises(ValueError):
                bridge.prepare(self.source, self.distribution, self.compose, target, *self.pins)
            self.assertFalse(target.exists())

    @unittest.skipIf(os.name == "nt", "POSIX link and mode semantics")
    def test_linked_ancestor_hardlink_and_changed_modes_are_rejected(self):
        alias = self.work / "alias"
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            bridge.prepare(alias, self.distribution, self.compose, self.output, *self.pins)
        self.prepare()
        path = self.output / "engine/curaengine/bin/CuraEngine"
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            bridge.verify(self.output, *self.pins)
        path.chmod(0o755)
        link = self.work / "hardlink"
        os.link(path, link)
        with self.assertRaises(ValueError):
            bridge.verify(self.output, *self.pins)

    def test_cli_verify_matches_and_diagnostics_do_not_echo_paths(self):
        result = self.prepare()
        options = sum((["--expected-" + n + "-sha256", p] for n, p in
                      zip(("source-manifest", "source-dockerfile", "catalog", "compose"), self.pins)), [])
        out = io.StringIO()
        with redirect_stdout(out):
            code = bridge.main(["--verify", str(self.output), *options])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue()), result)
        out = io.StringIO()
        with redirect_stdout(out):
            code = bridge.main(["--verify", str(self.work / "do-not-echo-private-path"), *options])
        self.assertEqual(code, 2)
        self.assertNotIn(str(self.work), out.getvalue())


if __name__ == "__main__":
    unittest.main()
