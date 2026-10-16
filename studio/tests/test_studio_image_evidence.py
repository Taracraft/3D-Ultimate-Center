"""Offline synthetic contracts; these tests never build/run an image or an engine."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SLICER = ROOT / "Slicer-Server"
sys.path.insert(0, str(SLICER))
try:
    spec = importlib.util.spec_from_file_location("studio_bound_image_evidence", SLICER / "verify_image_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
finally:
    sys.path.remove(str(SLICER))

COMMIT = "c" * 40
IMAGE = "sha256:" + "4" * 64
ARCHIVE, PACKAGE_MANIFEST = "a" * 64, "b" * 64


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def hashed(value):
    return hashlib.sha256(value).hexdigest()


class ImageEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.template = Path(cls.shared.name) / "template"
        cls.template.mkdir()
        payload, cls.context = module.prepare_context.collect(ROOT)
        names = {row["source"] for row in cls.context["files"]}
        names.update({"Slicer-Server/Dockerfile", "Slicer-Server/.dockerignore", "Slicer-Server/TARGET_BASE_REFERENCE.json", module.prepare_context.HOST + "/SHA256SUMS", module.prepare_context.HOST + "/DEPENDENCY-SHA256SUMS"})
        for name in names:
            out = cls.template / name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes((ROOT / name).read_bytes())
        cls.context_hash = hashed(payload["context-manifest.json"])

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / "source"
        shutil.copytree(self.template, self.source)
        self.evidence = self.work / "evidence"
        self.evidence.mkdir()
        self.repin_source()
        base = json.loads((self.source / "Slicer-Server/TARGET_BASE_REFERENCE.json").read_bytes())
        ref_raw = (self.source / "Slicer-Server/TARGET_IMAGE_REFERENCE.json").read_bytes()
        ref = json.loads(ref_raw)
        packages = [{"binary_package": name, "version": "1", "architecture": "amd64", "source_package": name, "source_version": "1", "copyright_path": "/usr/share/doc/" + name + "/copyright", "copyright_sha256": "d" * 64} for name in ref["required_packages"]]
        self.inventory = {"schema": 1, "kind": "ultimate-slicer-target-image-package-evidence", "base_image": base["base_image"], "image_id": IMAGE, "reference_sha256": hashed(ref_raw), "required_packages": ref["required_packages"], "package_count": len(packages), "packages": packages, "target_inventory_complete": True, "production_approved": False, "runtime_approved": False, "limitations": ["Synthetic test data; no image inspected."]}
        self.check = {"source_integrity": "verified", "verified_files": len(self.context["files"]), "version": self.context["version"], "api_protocol": self.context["api_protocol"], "container_deploy_ready": False, "engine_included": False, "installation_performed": False, "worker_started": False}
        self.layout = {"engine_executed": False, "engine_readiness_verified": False, "image_resource_links": "verified", "links_verified": 12}
        self.build = {"schema": 1, "source_commit": COMMIT, "run_id": "123", "image_id": IMAGE, "base_image": base["base_image"], "platform": "linux/amd64", "base_reference_sha256": hashed((self.source / "Slicer-Server/TARGET_BASE_REFERENCE.json").read_bytes()), "dockerfile_sha256": ref["dockerfile_sha256"], "source_manifest_sha256": self.manifest_hash, "context_manifest_sha256": self.context_hash, "image_build_passed": True, "target_inventory_complete": True, "package_count": len(packages), "required_package_count": len(ref["required_packages"]), "resource_links_verified": 12, "evidence_files": [], **{key: False for key in module.BUILD_FALSE}}
        self.save_evidence()

    def repin_source(self):
        rows = []
        for path in sorted(self.source.rglob("*")):
            if path.is_file() and path.name != "slicer-source-manifest.json":
                name = path.relative_to(self.source).as_posix()
                raw = path.read_bytes()
                rows.append({"path": name, "source_path": name, "bytes": len(raw), "sha256": hashed(raw), "mode": "100755" if name.endswith(".sh") else "100644"})
        value = {"schema": 1, "component": "ultimate-slicer-server", "scope": "Synthetic source fixture", "source_paths": len(rows), "payload_files": len(rows), "files": rows, **{key: False for key in module.MANIFEST_FALSE}}
        raw = encoded(value)
        (self.source / "slicer-source-manifest.json").write_bytes(raw)
        self.manifest_hash = hashed(raw)
        if hasattr(self, "build"):
            self.build["source_manifest_sha256"] = self.manifest_hash

    def save_evidence(self):
        for name, value in [("target-image-sbom.json", self.inventory), ("source-check.json", self.check), ("resource-layout.json", self.layout)]:
            (self.evidence / name).write_bytes(encoded(value))
        self.build["evidence_files"] = [{"path": name, "bytes": (self.evidence / name).stat().st_size, "sha256": hashed((self.evidence / name).read_bytes())} for name in sorted(module.NAMES - {"image-build-result.json"})]
        (self.evidence / "image-build-result.json").write_bytes(encoded(self.build))

    def call(self, **overrides):
        kwargs = {"source_root": self.source, "evidence_path": self.evidence, "expected_commit": COMMIT, "expected_manifest": self.manifest_hash}
        kwargs.update(overrides)
        return module.verify_bundle(**kwargs)

    def rejected(self, **overrides):
        with self.assertRaises((ValueError, OSError)):
            self.call(**overrides)

    def linux_document(self, passed=10, blocked=False, image=None):
        image = image or IMAGE[7:]
        value = {"schema": module.linux_test_evidence.SCHEMA, "run_sha256": "e" * 64, "package": {"archive_sha256": ARCHIVE, "manifest_sha256": PACKAGE_MANIFEST, "verified": True}, "host": {"host_fingerprint_sha256": "f" * 64, "os_id": "debian", "os_version": "13", "architecture": "x86_64", "supervisor_present": True}, "phases": [], "container_deploy_ready": False}
        for index, name in enumerate(module.linux_test_evidence.PHASES):
            checks = module.linux_test_evidence._defaults(name)
            for key, original in checks.items():
                if type(original) is bool:
                    checks[key] = key not in {"secret_in_argv_or_env", "private_key_exported"}
                elif type(original) is int:
                    checks[key] = 401 if key == "unauthenticated_status" else (200 if key == "authenticated_status" else 0)
                else:
                    checks[key] = ("8" * 64 if key == "new_image_sha256" else image) if "image" in key else "7" * 64
            value["phases"].append({"id": name, "status": "passed" if index < passed else ("blocked" if blocked and index == passed else "not_run"), "checks": checks, "previous_evidence_sha256": "", "evidence_sha256": ""})
        self.rechain(value)
        return value

    def rechain(self, value):
        previous = value["run_sha256"]
        for phase in value["phases"]:
            phase["previous_evidence_sha256"] = previous
            phase["evidence_sha256"] = module.linux_test_evidence.phase_digest(value["run_sha256"], value["package"], value["host"], previous, phase["id"], phase["status"], phase["checks"])
            previous = phase["evidence_sha256"]

    def with_linux(self, value):
        path = self.work / "linux.json"
        path.write_bytes(encoded(value))
        return {"linux_path": path, "expected_package_archive": ARCHIVE, "expected_package_manifest": PACKAGE_MANIFEST}

    def make_zip(self, extra=None):
        path = self.work / "evidence.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(module.NAMES):
                archive.writestr(name, (self.evidence / name).read_bytes())
            if extra:
                archive.writestr(extra, b"{}")
        return path

    def test_complete_image_without_installation_stays_not_run(self):
        before = {p: p.read_bytes() for p in self.source.rglob("*") if p.is_file()}
        result = self.call()
        self.assertTrue(result["image_source_binding_verified"])
        self.assertEqual(result["linux_evidence"]["status"], "not_run")
        for key in ("release_complete", "production_approved", "installation_performed", "engine_executed"):
            self.assertIs(result[key], False)
        self.assertEqual(before, {p: p.read_bytes() for p in self.source.rglob("*") if p.is_file()})

    def test_zip_and_directory_have_identical_results(self):
        self.assertEqual(self.call(), self.call(evidence_path=self.make_zip()))

    def test_full_linux_document_binds_initial_and_restored_images(self):
        result = self.call(**self.with_linux(self.linux_document()))
        self.assertEqual(result["linux_evidence"]["status"], "complete")
        self.assertEqual(result["linux_evidence"]["image_bound_phases"], ["compose", "runtime", "upgrade", "rollback"])
        self.assertFalse(result["release_complete"])

    def test_internally_valid_different_linux_image_rejected(self):
        value = self.linux_document(image="9" * 64)
        self.assertTrue(module.linux_test_evidence.validate_document(value, ARCHIVE, PACKAGE_MANIFEST)["testserver_acceptance_complete"])
        self.rejected(**self.with_linux(value))

    def test_partial_linux_and_blocked_linux_are_not_completed(self):
        for passed, blocked, expected in [(0, False, "partial"), (3, False, "partial"), (4, True, "blocked")]:
            with self.subTest(passed=passed, blocked=blocked):
                result = self.call(**self.with_linux(self.linux_document(passed, blocked)))
                self.assertEqual(result["linux_evidence"]["status"], expected)
                self.assertFalse(result["linux_evidence"]["evidence_contract_complete"])

    def test_partial_passed_compose_still_requires_same_image(self):
        self.rejected(**self.with_linux(self.linux_document(3, image="9" * 64)))

    def test_linux_expected_package_digests_are_external_inputs(self):
        args = self.with_linux(self.linux_document())
        for key in ("expected_package_archive", "expected_package_manifest"):
            with self.subTest(key=key):
                self.rejected(**{**args, key: "9" * 64})

    def test_linux_optional_arguments_must_be_complete(self):
        args = self.with_linux(self.linux_document())
        for name in args:
            with self.subTest(name=name):
                self.rejected(**{name: args[name]})
                self.rejected(**{k: v for k, v in args.items() if k != name})

    def test_linux_architecture_mismatch_rejected(self):
        value = self.linux_document()
        value["host"]["architecture"] = "aarch64"
        self.rechain(value)
        self.rejected(**self.with_linux(value))

    def test_linux_phase_hash_and_continuity_still_validated(self):
        value = self.linux_document()
        value["phases"][3]["checks"]["api_image_sha256"] = "9" * 64
        self.rejected(**self.with_linux(value))
        self.rechain(value)
        self.rejected(**self.with_linux(value))

    def test_wrong_commit_and_manifest_anchors_rejected(self):
        self.rejected(expected_commit="d" * 40)
        self.rejected(expected_manifest="d" * 64)
        self.rejected(expected_commit="main")
        self.rejected(expected_manifest="0" * 64)

    def test_manifest_byte_tampering_rejected(self):
        path = self.source / "slicer-source-manifest.json"
        path.write_bytes(path.read_bytes() + b" ")
        self.rejected()

    def test_source_tampering_rejected(self):
        path = self.source / "Slicer-Server/Dockerfile"
        path.write_bytes(path.read_bytes() + b"\n")
        self.rejected()

    def test_self_consistent_manifest_does_not_fix_stale_docker_reference(self):
        path = self.source / "Slicer-Server/Dockerfile"
        path.write_bytes(path.read_bytes() + b"\n")
        self.repin_source()
        self.build["dockerfile_sha256"] = hashed(path.read_bytes())
        self.save_evidence()
        self.rejected()

    def test_wrong_build_hashes_rejected(self):
        original = copy.deepcopy(self.build)
        for key in ("source_manifest_sha256", "dockerfile_sha256", "context_manifest_sha256", "base_reference_sha256"):
            with self.subTest(key=key):
                self.build = {**original, key: "9" * 64}
                self.save_evidence()
                self.rejected()
        self.build = original

    def test_wrong_base_and_image_identifiers_rejected(self):
        original = copy.deepcopy(self.build)
        for key, value in [("base_image", "python:latest"), ("image_id", "latest"), ("image_id", "sha256:" + "0" * 64), ("platform", "linux/arm64"), ("run_id", "0")]:
            with self.subTest(key=key, value=value):
                self.build = {**original, key: value}
                self.save_evidence()
                self.rejected()
        self.build = original

    def test_flags_cannot_smuggle_engine_or_deployment_approval(self):
        original = copy.deepcopy(self.build)
        for key in module.BUILD_FALSE:
            with self.subTest(key=key):
                self.build = {**original, key: True}
                self.save_evidence()
                self.rejected()
        self.build = original

    def test_boolean_counts_and_schema_are_not_integers(self):
        original = copy.deepcopy(self.build)
        for key in ("schema", "package_count", "required_package_count", "resource_links_verified"):
            with self.subTest(key=key):
                self.build = {**original, key: True}
                self.save_evidence()
                self.rejected()
        self.build = original

    def test_inventory_cannot_be_swapped_even_with_rehashed_member(self):
        self.inventory["image_id"] = "sha256:" + "9" * 64
        self.save_evidence()
        self.rejected()

    def test_missing_required_inventory_package_rejected(self):
        self.inventory["packages"].pop()
        self.inventory["package_count"] -= 1
        self.build["package_count"] -= 1
        self.save_evidence()
        self.rejected()

    def test_inventory_reference_and_copyright_digest_checked(self):
        old = self.inventory["reference_sha256"]
        self.inventory["reference_sha256"] = "8" * 64
        self.save_evidence()
        self.rejected()
        self.inventory["reference_sha256"] = old
        self.inventory["packages"][0]["copyright_sha256"] = "bad"
        self.save_evidence()
        self.rejected()

    def test_source_check_version_and_count_checked(self):
        original = copy.deepcopy(self.check)
        for key, value in [("version", "0.0.0"), ("verified_files", 1), ("api_protocol", True), ("worker_started", True)]:
            with self.subTest(key=key):
                self.check = {**original, key: value}
                self.save_evidence()
                self.rejected()
        self.check = original

    def test_layout_result_is_not_engine_readiness(self):
        self.layout["engine_readiness_verified"] = True
        self.save_evidence()
        self.rejected()

    def test_rehashed_context_mismatch_rejected(self):
        self.build["context_manifest_sha256"] = "9" * 64
        self.save_evidence()
        self.rejected()

    def test_duplicate_evidence_index_entry_rejected(self):
        self.build["evidence_files"][1] = self.build["evidence_files"][0]
        (self.evidence / "image-build-result.json").write_bytes(encoded(self.build))
        self.rejected()

    def test_evidence_member_tampering_and_unknown_fields_rejected(self):
        (self.evidence / "source-check.json").write_bytes(b"{}")
        self.rejected()
        self.save_evidence()
        self.build["unreviewed_field"] = "not-accepted"
        self.save_evidence()
        self.rejected()

    def test_extra_directory_or_zip_members_rejected(self):
        (self.evidence / "extra.json").write_bytes(b"{}")
        self.rejected()
        (self.evidence / "extra.json").unlink()
        self.rejected(evidence_path=self.make_zip("../escape.json"))
        self.assertFalse((self.work / "escape.json").exists())

    def test_duplicate_or_symlink_zip_member_rejected(self):
        path = self.make_zip()
        with zipfile.ZipFile(path, "a") as archive:
            with self.assertWarns(UserWarning):
                archive.writestr("source-check.json", b"{}")
        self.rejected(evidence_path=path)
        path = self.make_zip()
        values = {name: (self.evidence / name).read_bytes() for name in module.NAMES}
        with zipfile.ZipFile(path, "w") as archive:
            for name, raw in values.items():
                info = zipfile.ZipInfo(name)
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, raw)
        self.rejected(evidence_path=path)

    def test_json_duplicates_numbers_and_nonobject_rejected(self):
        for raw in (b'{"schema":1,"schema":1}', b'{"x":NaN}', b'{"x":1.0}', b'[]', b'{}\xff'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    module.document(raw)

    def test_source_path_escape_spellings_rejected(self):
        for name in ("../file", "/file", "a/../file", "a\\file", "C:file", "a\x00file", "a//b", "./file"):
            with self.subTest(name=repr(name)):
                with self.assertRaises(ValueError):
                    module.relative_name(name)

    def test_linked_file_rejected_where_supported(self):
        path = self.evidence / "source-check.json"
        target = self.work / "original.json"
        path.replace(target)
        try:
            path.symlink_to(target)
        except OSError:
            target.replace(path)
            self.skipTest("Symbolic-link creation is not available for this user")
        self.rejected()

    def test_supplied_python_sources_are_not_imported(self):
        path = self.source / "never_execute.py"
        path.write_text("raise RuntimeError('must not execute supplied source')\n")
        self.repin_source()
        self.save_evidence()
        self.assertTrue(self.call()["image_source_binding_verified"])

    def test_input_changes_during_verification_rejected(self):
        real = module.load_evidence
        calls = 0
        def changed(path):
            nonlocal calls
            calls += 1
            if calls == 2:
                (self.evidence / "source-check.json").write_bytes(b"{}")
            return real(path)
        with mock.patch.object(module, "load_evidence", side_effect=changed):
            self.rejected()

    def test_cli_exit_codes_distinguish_no_installation_partial_invalid(self):
        args = ["--source-root", str(self.source), "--evidence", str(self.evidence), "--expected-commit", COMMIT, "--expected-manifest-sha256", self.manifest_hash]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(args), 0)
        linux = self.with_linux(self.linux_document(3))
        args += ["--linux-evidence", str(linux["linux_path"]), "--expected-package-archive-sha256", ARCHIVE, "--expected-package-manifest-sha256", PACKAGE_MANIFEST]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(module.main(args), 2)
        self.build["unexpected"] = "private-sentinel-value"
        self.save_evidence()
        output = io.StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as result:
            module.main(args)
        self.assertEqual(result.exception.code, 1)
        self.assertNotIn("private-sentinel-value", output.getvalue())

    def test_context_inputs_cannot_be_omitted_from_source_manifest(self):
        path = self.source / 'slicer-source-manifest.json'
        value = json.loads(path.read_bytes())
        omitted = 'Slicer-Server/container_service.py'
        value['files'] = [row for row in value['files'] if row['path'] != omitted]
        value['payload_files'] -= 1
        value['source_paths'] -= 1
        raw = encoded(value)
        path.write_bytes(raw)
        self.manifest_hash = hashed(raw)
        self.build['source_manifest_sha256'] = self.manifest_hash
        self.save_evidence()
        self.rejected()

    def test_ci_binding_precedes_upload_with_explicit_anchors(self):
        text = (SLICER / 'slicer-source-contract.yml').read_text(encoding='utf-8-sig')
        self.assertLess(text.index('python Slicer-Server/verify_image_evidence.py'), text.index('actions/upload-artifact@'))
        self.assertIn('--expected-commit "$GITHUB_SHA"', text)
        self.assertIn('--expected-manifest-sha256 "${EXPECTED_MANIFEST%% *}"', text)
        self.assertIn('--evidence "$IMAGE_BUILD_ROOT/evidence"', text)
        self.assertIn('> "$IMAGE_BUILD_ROOT/image-evidence-verification.json"', text)

    def test_source_projection_includes_the_complete_binding_contract(self):
        text = (SLICER / 'build_repository.py').read_text(encoding='utf-8-sig')
        for name in ('Slicer-Server/verify_image_evidence.py', 'Slicer-Server/IMAGE_EVIDENCE.md', 'tests/test_studio_image_evidence.py'):
            with self.subTest(name=name):
                self.assertIn('"' + name + '"', text)



if __name__ == "__main__":
    unittest.main()
