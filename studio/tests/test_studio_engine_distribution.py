"""Complete three-engine offline assembly with synthetic archives, never engine code.

Uses existing bundle/catalog fixtures and the real existing staging validator.
No real vendor archive, license approval, Docker build or live installation.
"""
from __future__ import annotations
from contextlib import redirect_stdout
from dataclasses import asdict
import copy
import hashlib
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
try:
    import prepare_engine_distribution as dist
    import engine_catalog as catalog
    import package_activation as activation
    import package_staging as staging
finally:
    sys.path.remove(str(ROOT / "Slicer-Server"))
fixture_spec = importlib.util.spec_from_file_location("distribution_catalog_fixtures",
    ROOT / "tests/test_studio_catalog_selection.py")
f = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(f)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def catalog_row(release):
    value = asdict(release)
    value["system"] = "linux"
    for artifact in value["artifacts"]:
        artifact["files"] = [dict(row) for row in artifact["files"]]
        for row in artifact["files"]:
            if row.get("archive_path") is None:
                row.pop("archive_path", None)
    value["artifacts"] = list(value["artifacts"])
    return value


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.cache = self.work / "cache"
        self.cache.mkdir()
        self.catalog_path = self.work / "catalog.json"
        self.output = self.work / "distribution"
        self.payloads = {}
        releases = []
        for engine in sorted(catalog.ENTRYPOINTS):
            manifest, payloads = f.fixture(engine)
            self.payloads[engine] = payloads
            path = self.cache / engine / "bundle.archive"
            path.parent.mkdir()
            f.make_archive(path, manifest, payloads)
            raw = f.bundle.canonical(manifest)
            release = f.selection.bind_release(raw, digest(raw), f.artifact(engine, path))
            releases.append(catalog_row(release))
        self.data = {"schema": 1, "releases": releases, "pending": []}
        self.write_catalog()
        self.input_hashes = {str(p): digest(p.read_bytes()) for p in self.cache.rglob("*") if p.is_file()}

    def write_catalog(self):
        self.catalog_path.write_bytes(dist.canonical(self.data))
        self.catalog_hash = digest(self.catalog_path.read_bytes())

    def assemble(self, output=None, **kwargs):
        return dist.assemble(self.catalog_path, self.catalog_hash, self.cache, output or self.output, **kwargs)

    def assert_inputs_unchanged(self):
        for path, wanted in self.input_hashes.items():
            self.assertEqual(digest(Path(path).read_bytes()), wanted)
        self.assertEqual(digest(self.catalog_path.read_bytes()), self.catalog_hash)

    def test_full_real_extraction_produces_three_exact_payloads_and_valid_generation(self):
        with mock.patch.object(staging, "_download", side_effect=AssertionError("Network forbidden")), \
             mock.patch.object(activation, "activate_generation", side_effect=AssertionError("Activation forbidden")):
            result = self.assemble()
        self.assertTrue(result["verified"])
        self.assertEqual(result["engine_count"], 3)
        for engine, payloads in self.payloads.items():
            actual = {p.relative_to(self.output / "engine" / engine).as_posix(): p.read_bytes()
                      for p in (self.output / "engine" / engine).rglob("*") if p.is_file()}
            self.assertEqual(actual, payloads)
        generation = json.loads((self.output / "engine/GENERATION.json").read_bytes())
        self.assertEqual(set(activation._generation_releases(generation)), set(catalog.ENTRYPOINTS))
        self.assertEqual(result["generation_id"], generation["generation_id"])
        self.assertFalse((self.output / "ACTIVE.json").exists())
        self.assertFalse(result["product_release_complete"])
        self.assertFalse(result["engine_executed"])
        self.assert_inputs_unchanged()

    def test_archive_is_reproducible_and_unix_permissions_are_explicit(self):
        first = self.assemble()
        second_root = self.work / "second"
        second = self.assemble(second_root)
        self.assertEqual(first, second)
        self.assertEqual((self.output / dist.ARCHIVE).read_bytes(), (second_root / dist.ARCHIVE).read_bytes())
        with tarfile.open(self.output / dist.ARCHIVE, "r:gz") as archive:
            files = archive.getmembers()
            self.assertEqual(len(files), first["archive_members"])
            self.assertEqual([x.name for x in files], sorted(x.name for x in files))
            for member in files:
                self.assertTrue(member.isfile())
                self.assertEqual(member.uid, 0)
                self.assertEqual(member.gid, 0)
                self.assertEqual(member.mtime, 0)
                self.assertEqual(member.uname, "")
                self.assertEqual(member.gname, "")
                executable = any(member.name == "engine/" + name + "/" + path
                                 for name, path in catalog.ENTRYPOINTS.items())
                self.assertEqual(member.mode, 0o755 if executable else 0o644)
                self.assertEqual(archive.extractfile(member).read(), (self.output / member.name).read_bytes())

    def test_existing_output_is_never_overwritten_even_when_empty(self):
        self.output.mkdir()
        with self.assertRaisesRegex(dist.DistributionError, "output_exists"):
            self.assemble()
        self.assertEqual(list(self.output.iterdir()), [])
        self.assert_inputs_unchanged()

    def test_repeated_command_does_not_replace_completed_distribution(self):
        self.assemble()
        before = (self.output / dist.ARCHIVE).read_bytes()
        with self.assertRaisesRegex(dist.DistributionError, "output_exists"):
            self.assemble()
        self.assertEqual(before, (self.output / dist.ARCHIVE).read_bytes())

    def test_current_pending_catalog_cannot_create_a_partial_engine_release(self):
        self.catalog_path.write_bytes((ROOT / "Slicer-Server/engine_catalog.json").read_bytes())
        self.catalog_hash = digest(self.catalog_path.read_bytes())
        with self.assertRaisesRegex(dist.DistributionError, "complete_engine_catalog_required"):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_each_missing_family_blocks_before_any_output(self):
        original = copy.deepcopy(self.data)
        for family in catalog.ENTRYPOINTS:
            with self.subTest(family=family):
                self.data = copy.deepcopy(original)
                self.data["releases"] = [r for r in self.data["releases"] if r["engine"] != family]
                self.data["pending"] = [family]
                self.write_catalog()
                with self.assertRaisesRegex(dist.DistributionError, "complete_engine_catalog_required"):
                    self.assemble()
                self.assertFalse(self.output.exists())

    def test_expected_catalog_digest_is_not_taken_from_its_own_declaration(self):
        for value in ("0" * 64, "f" * 64, "latest", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                dist.assemble(self.catalog_path, value, self.cache, self.output)
            self.assertFalse(self.output.exists())

    def test_missing_or_corrupt_last_archive_prevents_partial_output(self):
        path = self.cache / sorted(catalog.ENTRYPOINTS)[-1] / "bundle.archive"
        original = path.read_bytes()
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        with self.assertRaisesRegex(dist.DistributionError, "file_digest_mismatch"):
            self.assemble()
        self.assertFalse(self.output.exists())
        path.unlink()
        with self.assertRaises(OSError):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_no_download_fallback_for_missing_local_archives(self):
        shutil.rmtree(self.cache / "prusaslicer")
        with mock.patch.object(staging, "_download", side_effect=AssertionError("Never download")), \
             self.assertRaises(OSError):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_last_extraction_failure_removes_only_this_new_output(self):
        sentinel = self.work / "existing-engine-store"
        sentinel.mkdir(); (sentinel / "data.txt").write_text("preserve")
        real = staging.prepare_release
        def fail_last(release, *args, **kwargs):
            if release.engine == sorted(catalog.ENTRYPOINTS)[-1]:
                raise staging.StagingError("synthetic_last_engine_failure")
            return real(release, *args, **kwargs)
        with mock.patch.object(staging, "prepare_release", side_effect=fail_last), self.assertRaises(ValueError):
            self.assemble()
        self.assertFalse(self.output.exists())
        self.assertEqual((sentinel / "data.txt").read_text(), "preserve")
        self.assert_inputs_unchanged()

    def test_cancellation_before_start_and_after_first_stage(self):
        with self.assertRaises(staging.StagingError):
            self.assemble(cancelled=lambda: True)
        self.assertFalse(self.output.exists())
        flag = [False]
        real = staging.prepare_release
        def first_stage(*args, **kwargs):
            result = real(*args, **kwargs); flag[0] = True; return result
        with mock.patch.object(staging, "prepare_release", side_effect=first_stage), self.assertRaises(ValueError):
            self.assemble(cancelled=lambda: flag[0])
        self.assertFalse(self.output.exists())
        self.assert_inputs_unchanged()

    def test_zero_length_noncritical_payload_file_is_retained(self):
        engine = "curaengine"
        manifest, payloads = f.fixture(engine)
        payloads["resources/empty.txt"] = b""
        manifest["files"].append({"path": "resources/empty.txt", "bytes": 0,
            "sha256": digest(b""), "role": "resources", "executable": False})
        path = self.cache / engine / "bundle.archive"
        path.unlink(); f.make_archive(path, manifest, payloads)
        raw = f.bundle.canonical(manifest)
        release = f.selection.bind_release(raw, digest(raw), f.artifact(engine, path))
        self.data["releases"] = [catalog_row(release) if row["engine"] == engine else row
                                 for row in self.data["releases"]]
        self.write_catalog()
        self.assemble()
        self.assertEqual((self.output / "engine/curaengine/resources/empty.txt").read_bytes(), b"")

    def test_same_artifact_id_is_scoped_to_its_engine(self):
        self.assertTrue(all(r["artifacts"][0]["id"] == "bundle" for r in self.data["releases"]))
        result = self.assemble()
        self.assertEqual(result["engine_files"], sum(len(v) for v in self.payloads.values()))

    def test_input_catalog_changes_while_staging_are_rejected(self):
        real = staging.prepare_release
        def changed(*args, **kwargs):
            result = real(*args, **kwargs)
            self.catalog_path.write_bytes(self.catalog_path.read_bytes() + b" ")
            return result
        with mock.patch.object(staging, "prepare_release", side_effect=changed), self.assertRaises(ValueError):
            self.assemble()
        self.assertFalse(self.output.exists())
        self.assertTrue(self.catalog_path.read_bytes().endswith(b" "))

    def test_original_archive_changes_after_initial_checks_are_detected(self):
        real = staging.prepare_release
        altered = self.cache / "bambu_studio/bundle.archive"
        def changed(release, *args, **kwargs):
            result = real(release, *args, **kwargs)
            if release.engine == "bambu_studio":
                data = altered.read_bytes()
                altered.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
            return result
        with mock.patch.object(staging, "prepare_release", side_effect=changed), self.assertRaises(ValueError):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_modified_payload_cannot_pass_verify(self):
        self.assemble()
        path = self.output / "engine/curaengine/bin/CuraEngine"
        path.write_bytes(path.read_bytes()[:-1] + b"x")
        with self.assertRaises(ValueError):
            dist.verify(self.output, self.catalog_hash)

    def test_modifying_archive_and_its_declared_digest_still_does_not_pass(self):
        self.assemble()
        path = self.output / dist.ARCHIVE
        data = path.read_bytes(); path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
        ready = json.loads((self.output / dist.READY).read_bytes())
        ready["archive_sha256"] = digest(path.read_bytes())
        (self.output / dist.READY).write_bytes(dist.canonical(ready))
        with self.assertRaises(dist.DistributionError):
            dist.verify(self.output, self.catalog_hash)

    def test_readiness_and_generation_metadata_are_derived_not_trusted(self):
        self.assemble()
        path = self.output / "engine/GENERATION.json"
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with self.assertRaisesRegex(dist.DistributionError, "metadata_mismatch"):
            dist.verify(self.output, self.catalog_hash)
        path.write_bytes(original)
        ready = self.output / dist.READY
        data = json.loads(ready.read_bytes()); data["product_release_complete"] = True
        ready.write_bytes(dist.canonical(data))
        with self.assertRaisesRegex(dist.DistributionError, "receipt_mismatch"):
            dist.verify(self.output, self.catalog_hash)

    def test_unknown_files_or_empty_directories_are_not_silently_distributed(self):
        self.assemble()
        path = self.output / "untracked.txt"; path.write_text("not allowed")
        with self.assertRaisesRegex(dist.DistributionError, "output_member_mismatch"):
            dist.verify(self.output, self.catalog_hash)
        path.unlink(); path.mkdir()
        with self.assertRaisesRegex(dist.DistributionError, "output_member_mismatch"):
            dist.verify(self.output, self.catalog_hash)

    def test_incomplete_output_has_no_implicit_ready_status(self):
        self.assemble()
        (self.output / dist.READY).unlink()
        with self.assertRaises(ValueError):
            dist.verify(self.output, self.catalog_hash)

    def test_output_inside_source_or_archive_tree_is_rejected(self):
        for path in (ROOT / "forbidden_engine_distribution", self.cache / "new"):
            with self.subTest(path=str(path)), self.assertRaises(ValueError):
                self.assemble(path)
            self.assertFalse(path.exists())

    def test_hardlinked_input_archive_is_rejected_without_touching_it(self):
        path = self.cache / "bambu_studio/bundle.archive"
        duplicate = self.work / "hardlink"
        try:
            os.link(path, duplicate)
        except OSError as exc:
            self.skipTest(f"Hardlink unavailable: {type(exc).__name__}")
        with self.assertRaisesRegex(dist.DistributionError, "regular_unlinked_file_required"):
            self.assemble()
        self.assertFalse(self.output.exists())
        self.assertEqual(path.read_bytes(), duplicate.read_bytes())

    @unittest.skipIf(os.name == "nt", "POSIX symlink and permission contract")
    def test_linked_parent_and_world_writable_output_parent_rejected(self):
        linked = self.work / "cache-alias"
        linked.symlink_to(self.cache, target_is_directory=True)
        with self.assertRaisesRegex(dist.DistributionError, "linked_path"):
            dist.assemble(self.catalog_path, self.catalog_hash, linked, self.output)
        self.work.chmod(0o777)
        try:
            with self.assertRaises(staging.StagingError):
                self.assemble()
        finally:
            self.work.chmod(0o700)
        self.assertFalse(self.output.exists())

    def test_global_resource_limit_cannot_be_bypassed_with_three_individually_valid_engines(self):
        with mock.patch.object(catalog, "MAX_INSTALLED_BYTES", 64), self.assertRaises(ValueError):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_changed_metadata_types_duplicate_json_and_zero_hashes_rejected(self):
        self.data["schema"] = True; self.write_catalog()
        with self.assertRaises(ValueError):
            self.assemble()
        self.assertFalse(self.output.exists())
        self.catalog_path.write_bytes(b'{"schema":1,"schema":1,"releases":[],"pending":[]}')
        self.catalog_hash = digest(self.catalog_path.read_bytes())
        with self.assertRaises(ValueError):
            self.assemble()
        self.assertFalse(self.output.exists())

    def test_cli_failure_does_not_echo_sensitive_paths_or_upstream_contents(self):
        self.catalog_path.write_bytes(b'{"secret":"do-not-echo-this"}')
        self.catalog_hash = digest(self.catalog_path.read_bytes())
        out = io.StringIO()
        with redirect_stdout(out):
            code = dist.main(["--catalog", str(self.catalog_path), "--expected-catalog-sha256", self.catalog_hash,
                              "--archive-root", str(self.cache), "--output", str(self.output)])
        self.assertEqual(code, 2)
        self.assertNotIn("do-not-echo-this", out.getvalue())
        self.assertNotIn(str(self.work), out.getvalue())
        self.assertFalse(self.output.exists())

    def test_cli_build_and_independent_verify_modes_match(self):
        out = io.StringIO()
        with redirect_stdout(out):
            result = dist.main(["--catalog", str(self.catalog_path), "--expected-catalog-sha256", self.catalog_hash,
                                "--archive-root", str(self.cache), "--output", str(self.output)])
        self.assertEqual(result, 0)
        generated = json.loads(out.getvalue())
        out = io.StringIO()
        with redirect_stdout(out):
            result = dist.main(["--verify", str(self.output), "--expected-catalog-sha256", self.catalog_hash])
        self.assertEqual(result, 0)
        self.assertEqual(generated, json.loads(out.getvalue()))

    def test_valid_alternate_compression_is_checked_by_content_not_recompression(self):
        self.assemble()
        path = self.output / dist.ARCHIVE
        original = path.read_bytes()
        content = gzip.decompress(original)
        path.write_bytes(gzip.compress(content, compresslevel=1, mtime=0))
        self.assertNotEqual(path.read_bytes(), original)
        ready = json.loads((self.output / dist.READY).read_bytes())
        ready.update(archive_sha256=digest(path.read_bytes()), archive_bytes=path.stat().st_size)
        (self.output / dist.READY).write_bytes(dist.canonical(ready))
        self.assertTrue(dist.verify(self.output, self.catalog_hash)["verified"])

    def test_forged_archive_with_valid_gzip_and_updated_receipt_is_rejected(self):
        self.assemble()
        path = self.output / dist.ARCHIVE
        content = bytearray(gzip.decompress(path.read_bytes()))
        content[100] ^= 1
        path.write_bytes(gzip.compress(bytes(content), mtime=0))
        ready = json.loads((self.output / dist.READY).read_bytes())
        ready.update(archive_sha256=digest(path.read_bytes()), archive_bytes=path.stat().st_size)
        (self.output / dist.READY).write_bytes(dist.canonical(ready))
        with self.assertRaisesRegex(dist.DistributionError, "archive_content_mismatch"):
            dist.verify(self.output, self.catalog_hash)

    def test_appended_second_gzip_stream_is_rejected(self):
        self.assemble()
        path = self.output / dist.ARCHIVE
        path.write_bytes(path.read_bytes() + gzip.compress(b"unexpected", mtime=0))
        with self.assertRaisesRegex(dist.DistributionError, "trailing_archive_stream"):
            dist.verify(self.output, self.catalog_hash)

    def test_boundaries_and_original_catalog_unchanged(self):
        paths = [ROOT / "Slicer-Server" / name for name in
                 ("engine_catalog.json", "container_service.py", "compose.candidate.yaml")]
        before = {p: p.read_bytes() for p in paths}
        self.assemble()
        self.assertEqual(before, {p: p.read_bytes() for p in paths})
        self.assert_inputs_unchanged()


if __name__ == "__main__":
    unittest.main()
