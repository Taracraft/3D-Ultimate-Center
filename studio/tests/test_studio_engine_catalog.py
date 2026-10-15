"""Synthetic catalog/byte fixtures; no network, real engines or installation."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio_engine_catalog", ROOT / "Slicer-Server/engine_catalog.py")
catalog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = catalog
spec.loader.exec_module(catalog)

PAYLOAD = b"synthetic package bytes; not executable"
SHA = hashlib.sha256(PAYLOAD).hexdigest()


def file_spec(path, role, executable=False):
    return dict(path=path, sha256=SHA, size_bytes=len(PAYLOAD),
                role=role, executable=executable)


def document(engine="prusaslicer"):
    profiles = {
        "bambu_studio": "resources/profiles/machine/example.json",
        "prusaslicer": "resources/profiles/example.ini",
        "curaengine": "resources/definitions/example.def.json",
    }
    files = [
        file_spec(catalog.ENTRYPOINTS[engine], "engine", True),
        file_spec("resources/data.txt", "resources"),
        file_spec(profiles[engine], "profiles"),
        file_spec("licenses/NOTICE", "license"),
    ]
    if engine == "prusaslicer":
        files.append(file_spec("lib/OCCTWrapper.so", "runtime"))
    artifact = dict(
        id="engine_bundle", component_version="2.9.2",
        url="https://github.com/Taracraft/3D-Ultimate-Center/releases/download/test/bundle.tar.xz",
        sha256=SHA, size_bytes=len(PAYLOAD), format="tar.xz", license="Test-only",
        source_url=catalog.UPSTREAMS[engine] + "tree/" + "a"*40,
        source_revision="a"*40, files=files,
    )
    return dict(schema=1, releases=[dict(engine=engine, version="2.9.2",
                system="linux", architecture="amd64", artifacts=[artifact])],
                pending=[e for e in catalog.ENTRYPOINTS if e != engine])


def parse(value):
    return catalog.load_catalog_bytes(json.dumps(value).encode())


class CatalogTests(unittest.TestCase):
    def reject(self, value, code):
        with self.assertRaisesRegex(catalog.CatalogError, "^" + code + "$"):
            parse(value)

    def test_all_three_complete_contracts_and_totals(self):
        for engine in catalog.ENTRYPOINTS:
            with self.subTest(engine=engine):
                value = parse(document(engine)).select(engine, system="linux", architecture="amd64")
                self.assertEqual(value.download_bytes, len(PAYLOAD))
                self.assertGreater(value.installed_bytes, value.download_bytes)
                self.assertEqual(value.artifacts[0].files[0].path, catalog.ENTRYPOINTS[engine])

    def test_shipped_catalog_explicitly_blocks_unapproved_engines(self):
        value = catalog.load_catalog()
        self.assertEqual(value.releases, ())
        self.assertEqual(set(value.pending), set(catalog.ENTRYPOINTS))
        for engine in catalog.ENTRYPOINTS:
            with self.subTest(engine=engine), self.assertRaisesRegex(catalog.CatalogError, "engine_not_approved"):
                value.select(engine, system="linux", architecture="amd64")

    def test_unsupported_platform_and_unknown_engine(self):
        value = parse(document())
        for args in [("prusaslicer", "windows", "amd64"), ("prusaslicer", "linux", "arm64")]:
            with self.subTest(args=args), self.assertRaisesRegex(catalog.CatalogError, "unsupported_platform"):
                value.select(args[0], system=args[1], architecture=args[2])
        for engine in ["orca", "../prusaslicer", [], None]:
            with self.subTest(engine=engine), self.assertRaisesRegex(catalog.CatalogError, "unknown_engine"):
                value.select(engine, system="linux", architecture="amd64")

    def test_parsed_plan_is_immutable_and_detached(self):
        source = document()
        value = parse(source)
        source["releases"][0]["artifacts"][0]["url"] = "https://evil.invalid"
        with self.assertRaises(FrozenInstanceError):
            value.releases[0].version = "other"
        self.assertIn("github.com/Taracraft/", value.releases[0].artifacts[0].url)

    def test_duplicate_json_keys(self):
        with self.assertRaisesRegex(catalog.CatalogError, "duplicate_json_key"):
            catalog.load_catalog_bytes(b'{"schema":1,"schema":1,"releases":[],"pending":[]}')

    def test_invalid_json_and_size(self):
        for data in [b"\xff", b"{", b"[" * 1200]:
            with self.subTest(data=data[:10]), self.assertRaisesRegex(catalog.CatalogError, "invalid_json"):
                catalog.load_catalog_bytes(data)
        with self.assertRaisesRegex(catalog.CatalogError, "catalog_size"):
            catalog.load_catalog_bytes(b" " * (catalog.MAX_CATALOG_BYTES + 1))

    def test_schema_rejects_bool_and_unknown_fields(self):
        d = document(); d["schema"] = True
        self.reject(d, "unsupported_schema")
        d = document(); d["command"] = "ignored"
        self.reject(d, "invalid_fields")

    def test_catalog_requires_exactly_one_state_per_engine(self):
        for pending in [[], ["curaengine"], ["curaengine", "bambu_studio", "prusaslicer"],
                        ["curaengine", "curaengine", "bambu_studio"], [None], [[]]]:
            with self.subTest(pending=pending):
                d = document(); d["pending"] = pending
                self.reject(d, "incomplete_catalog")

    def test_duplicate_release(self):
        d = document(); d["releases"].append(deepcopy(d["releases"][0]))
        self.reject(d, "duplicate_release")

    def test_unfixed_version_and_source(self):
        for value in ["latest", "main", "nightly", "unknown", ""]:
            with self.subTest(value=value):
                d = document(); d["releases"][0]["version"] = value
                self.reject(d, "invalid_text" if not value else "unfixed_version")
        d = document(); d["releases"][0]["artifacts"][0]["source_revision"] = "main"
        self.reject(d, "unfixed_source")

    def test_untrusted_download_origins_and_redirect_like_urls(self):
        for url in ["http://deb.debian.org/debian/pool/file",
                    "https://github.com.evil.invalid/Taracraft/3D-Ultimate-Center/releases/download/a/b",
                    "https://user:secret@github.com/Taracraft/3D-Ultimate-Center/releases/download/a/b",
                    "https://github.com/Taracraft/3D-Ultimate-Center/releases/download/a/b?token=secret",
                    "https://github.com/Taracraft/3D-Ultimate-Center/releases/download/a/b#frag",
                    "https://github.com/Taracraft/3D-Ultimate-Center/releases/download/../b",
                    "https://github.com/Taracraft/3D-Ultimate-Center/releases/download/%2e%2e/b",
                    "https://github.com/Taracraft/3D-Ultimate-Center/releases/download/latest/b",
                    "https://127.0.0.1/test", "https://[invalid/", "file:///etc/passwd"]:
            with self.subTest(url=url):
                d = document(); d["releases"][0]["artifacts"][0]["url"] = url
                self.reject(d, "untrusted_url")

    def test_wrong_upstream(self):
        d = document(); d["releases"][0]["artifacts"][0]["source_url"] = catalog.UPSTREAMS["bambu_studio"] + "tree/" + "a"*40
        self.reject(d, "untrusted_url")

    def test_digest_mandatory_and_exact(self):
        for value in ["", "a"*63, "G"*64, "A"*64, None]:
            with self.subTest(value=value):
                d = document(); d["releases"][0]["artifacts"][0]["sha256"] = value
                self.reject(d, "invalid_digest")

    def test_size_bounds_and_bool(self):
        for value in [0, -1, True, "12", catalog.MAX_ARTIFACT_BYTES + 1]:
            with self.subTest(value=value):
                d = document(); d["releases"][0]["artifacts"][0]["size_bytes"] = value
                self.reject(d, "invalid_size")

    def test_archive_type_and_no_extra_commands(self):
        for value in ["appimage", "shell", [], None]:
            with self.subTest(value=value):
                d = document(); d["releases"][0]["artifacts"][0]["format"] = value
                self.reject(d, "unsupported_archive")
        d = document(); d["releases"][0]["artifacts"][0]["postinstall"] = "run"
        self.reject(d, "invalid_fields")

    def test_missing_notice_is_rejected(self):
        d = document(); files = d["releases"][0]["artifacts"][0]["files"]
        files[:] = [f for f in files if f["role"] != "license"]
        self.reject(d, "missing_license_file")

    def test_missing_resources_profiles_or_prusa_plugin(self):
        for role, error in [("resources", "missing_resources"), ("profiles", "missing_profile_contract"),
                            ("runtime", "missing_profile_contract")]:
            with self.subTest(role=role):
                d = document(); files = d["releases"][0]["artifacts"][0]["files"]
                files[:] = [f for f in files if f["role"] != role]
                self.reject(d, error)

    def test_bare_cura_binary_is_not_installable(self):
        d = document("curaengine")
        d["releases"][0]["artifacts"][0]["files"][2]["path"] = "resources/random.json"
        self.reject(d, "missing_profile_contract")

    def test_wrong_entrypoint_or_not_executable(self):
        d = document(); d["releases"][0]["artifacts"][0]["files"][0]["path"] = "usr/bin/prusa-slicer"
        self.reject(d, "invalid_entrypoint")
        d = document(); d["releases"][0]["artifacts"][0]["files"][0]["executable"] = False
        self.reject(d, "invalid_entrypoint")

    def test_paths_reject_traversal_absolute_and_aliases(self):
        for path in ["../escape", "/abs", "a/../b", "a//b", "a/./b", r"a\b", "C:/a",
                     "a/%2e", "a./b", "a /b", "a:stream"]:
            with self.subTest(path=path):
                d = document(); d["releases"][0]["artifacts"][0]["files"][1]["path"] = path
                self.reject(d, "unsafe_path")

    def test_cross_artifact_path_collision(self):
        d = document(); other = deepcopy(d["releases"][0]["artifacts"][0]); other["id"] = "profiles"
        d["releases"][0]["artifacts"].append(other)
        self.reject(d, "conflicting_paths")

    def test_file_directory_and_case_collisions(self):
        for path in ["resources", "RESOURCES/data.txt"]:
            with self.subTest(path=path):
                d = document(); d["releases"][0]["artifacts"][0]["files"].append(file_spec(path, "runtime"))
                self.reject(d, "conflicting_paths")

    def test_installed_size_limit(self):
        d = document(); d["releases"][0]["artifacts"][0]["files"][1]["size_bytes"] = catalog.MAX_INSTALLED_BYTES
        self.reject(d, "installed_limit")

    def test_roles_types_and_unexpected_executable(self):
        d = document(); d["releases"][0]["artifacts"][0]["files"][1]["role"] = []
        self.reject(d, "invalid_file_contract")
        d = document(); d["releases"][0]["artifacts"][0]["files"][1]["executable"] = True
        self.reject(d, "unexpected_executable")

    def test_stream_digest_success_without_execution(self):
        artifact = parse(document()).releases[0].artifacts[0]
        catalog.verify_artifact(io.BytesIO(PAYLOAD), artifact)

    def test_stream_short_long_and_digest_mismatch(self):
        artifact = parse(document()).releases[0].artifacts[0]
        for payload, code in [(PAYLOAD[:-1], "artifact_size_mismatch"),
                              (PAYLOAD + b"x", "artifact_size_mismatch"),
                              (b"x" * len(PAYLOAD), "artifact_digest_mismatch")]:
            with self.subTest(code=code), self.assertRaisesRegex(catalog.CatalogError, code):
                catalog.verify_artifact(io.BytesIO(payload), artifact)

    def test_chunked_stream_is_supported_and_read_is_bounded(self):
        class ShortReads(io.BytesIO):
            def read(self, size=-1):
                self_size.append(size)
                return super().read(min(size, 3))
        self_size = []
        artifact = parse(document()).releases[0].artifacts[0]
        catalog.verify_artifact(ShortReads(PAYLOAD), artifact)
        self.assertLessEqual(max(self_size), len(PAYLOAD))

    def test_stream_revalidates_declared_limits(self):
        artifact = parse(document()).releases[0].artifacts[0]
        with self.assertRaisesRegex(catalog.CatalogError, "invalid_size"):
            catalog.verify_artifact(io.BytesIO(PAYLOAD), replace(artifact, size_bytes=True))


if __name__ == "__main__":
    unittest.main()
