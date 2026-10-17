"""Synthetic source bindings through existing catalog/stage/generation/member paths.

No archive builder, archive extraction, original vendor manifest, network,
engine, service, installation, or release approval is exercised here.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import asdict, FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
import engine_catalog as catalog
import prepare_catalog_selection as selection
import package_staging as staging
import package_activation as activation
import prepare_engine_distribution as distribution


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture():
    payloads = {
        "bin/CuraEngine": ("engine", True),
        "resources/definitions/fdmprinter.def.json": ("profiles", False),
        "resources/definitions/example.def.json": ("profiles", False),
        "licenses/cura-engine.txt": ("license", False),
        "licenses/cura.txt": ("license", False),
    }
    manifest = {"schema": 1, "engine": "curaengine", "version": "1:5.0.0-5", "system": "linux", "architecture": "amd64",
        "upstream_archives": [{"id": "synthetic", "bytes": 1, "sha256": "a" * 64}],
        "files": [{"path": path, "bytes": 1, "sha256": "b" * 64, "role": role, "executable": executable}
                  for path, (role, executable) in payloads.items()],
        **{name: False for name in selection.FLAGS}}
    artifact = {"id": "combined_cura", "component_version": manifest["version"],
        "url": "https://github.com/Taracraft/3D-Ultimate-Slicer-Server/releases/download/synthetic/combined.tar.gz",
        "sha256": "c" * 64, "size_bytes": 1, "format": "tar.gz", "license": "SYNTHETIC-NOT-AN-APPROVAL",
        "source_url": catalog.UPSTREAMS["curaengine"] + "CuraEngine/tree/" + "d" * 40, "source_revision": "d" * 40}
    def component(ident, package, version, files, notice):
        stem = package + "_" + ("5.0.0-5" if package == "cura-engine" else "5.0.0-6")
        origin = "https://deb.debian.org/debian/pool/main/c/" + package + "/"
        return {"id": ident, "package": package, "component_version": version,
            "license": "SYNTHETIC-NOTICE", "source_revision": "e" * 64,
            "archives": [
                {"kind": "descriptor", "url": origin + stem + ".dsc", "sha256": "e" * 64, "size_bytes": 1},
                {"kind": "upstream", "url": origin + package + "_5.0.0.orig.tar.gz", "sha256": "f" * 64, "size_bytes": 2},
                {"kind": "debian_patches", "url": origin + stem + ".debian.tar.xz", "sha256": "a" * 64, "size_bytes": 3}],
            "files": files, "notices": [notice]}
    artifact["source_components"] = [
        component("engine_source", "cura-engine", "1:5.0.0-5", ["bin/CuraEngine", "licenses/cura-engine.txt"], "licenses/cura-engine.txt"),
        component("resource_source", "cura", "5.0.0-6", [p for p in payloads if p.startswith("resources/")] + ["licenses/cura.txt"], "licenses/cura.txt")]
    return manifest, artifact


def bind(manifest, artifact):
    raw = selection.bundle.canonical(manifest)
    return selection.bind_release(raw, digest(raw), artifact)


class SourceComponentTests(unittest.TestCase):
    def test_two_distinct_source_packages_survive_actual_binding_stage_and_generation(self):
        manifest, artifact = fixture()
        before = deepcopy((manifest, artifact))
        release = bind(manifest, artifact)
        components = release.artifacts[0].source_components
        self.assertEqual([(c.package, c.component_version) for c in components],
                         [("cura-engine", "1:5.0.0-5"), ("cura", "5.0.0-6")])
        self.assertEqual([len(c.archives) for c in components], [3, 3])
        self.assertEqual(staging._checked_release(release), release)
        self.assertEqual(activation._release_from_receipt(catalog.release_document(release)), release)
        generation = activation._generation_document({"curaengine": release})
        self.assertEqual(activation._generation_releases(generation), {"curaengine": release})
        self.assertEqual((manifest, artifact), before)

    def test_existing_offline_member_plan_carries_exact_source_and_notice_bindings(self):
        manifest, artifact = fixture()
        release = bind(manifest, artifact)
        raw = b'{"synthetic_catalog":"not_a_release"}\n'
        metadata, rows = distribution.members({"curaengine": release}, raw)
        source = json.loads(metadata["SOURCE_MANIFEST.json"])
        self.assertEqual(source["catalog_sha256"], digest(raw))
        self.assertFalse(source["source_archive_bytes_included"])
        self.assertFalse(source["license_review_complete"])
        self.assertFalse(source["product_release_complete"])
        self.assertEqual(len(source["bindings"]), 2)
        self.assertEqual(sum(len(b["archives"]) for b in source["bindings"]), 6)
        for row in source["bindings"]:
            self.assertEqual(row["binary_artifact_sha256"], artifact["sha256"])
            self.assertTrue(row["files"])
            self.assertTrue(all(n["sha256"] == "b" * 64 and n["size_bytes"] == 1 for n in row["bindings_notices"]))
        self.assertEqual(rows["SOURCE_MANIFEST.json"],
            (len(metadata["SOURCE_MANIFEST.json"]), digest(metadata["SOURCE_MANIFEST.json"]), 0o644))

    def test_source_change_is_bound_into_generation_and_distribution_identity(self):
        manifest, artifact = fixture()
        first = bind(manifest, artifact)
        artifact["source_components"][1]["archives"][1]["sha256"] = "9" * 64
        second = bind(manifest, artifact)
        self.assertEqual(first.artifacts[0].sha256, second.artifacts[0].sha256)
        self.assertNotEqual(activation._generation_document({"curaengine": first})["generation_id"],
                            activation._generation_document({"curaengine": second})["generation_id"])
        self.assertNotEqual(distribution.members({"curaengine": first}, b"same")[1]["SOURCE_MANIFEST.json"],
                            distribution.members({"curaengine": second}, b"same")[1]["SOURCE_MANIFEST.json"])

    def test_legacy_catalog_serialization_and_generation_bytes_remain_unchanged(self):
        manifest, artifact = fixture()
        artifact.pop("source_components")
        release = bind(manifest, artifact)
        old = asdict(release)
        for item in old["artifacts"]:
            item.pop("source_components", None)
        expected = json.loads(json.dumps(old))
        self.assertEqual(catalog.release_document(release), expected)
        self.assertEqual(staging._checked_release(release), release)
        body = {"schema": 1, "releases": [expected]}
        generation = activation._generation_document({"curaengine": release})
        self.assertEqual(generation["generation_id"], "g-" + digest(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")))
        self.assertNotIn("SOURCE_MANIFEST.json", distribution.members({"curaengine": release}, b"legacy")[0])

    def test_every_binary_file_has_exactly_one_known_component(self):
        for mutation in ("missing", "duplicate", "unknown"):
            with self.subTest(mutation=mutation):
                manifest, artifact = fixture()
                components = artifact["source_components"]
                if mutation == "missing": components[0]["files"].remove("bin/CuraEngine")
                elif mutation == "duplicate": components[1]["files"].append("bin/CuraEngine")
                else: components[0]["files"].append("private/not-shipped")
                with self.assertRaisesRegex(catalog.CatalogError, "source_file_coverage"):
                    bind(manifest, artifact)

    def test_notice_must_bind_a_nonempty_selected_license_file(self):
        for notice in ([], ["missing.txt"], ["bin/CuraEngine"], ["licenses/cura-engine.txt", "licenses/cura-engine.txt"]):
            with self.subTest(notice=notice):
                manifest, artifact = fixture()
                artifact["source_components"][0]["notices"] = notice
                with self.assertRaises(catalog.CatalogError): bind(manifest, artifact)

    def test_debian_triplet_is_complete_and_descriptor_digest_is_the_revision(self):
        for mutation in ("missing", "duplicate", "zero", "revision"):
            with self.subTest(mutation=mutation):
                manifest, artifact = fixture()
                source = artifact["source_components"][0]
                if mutation == "missing": source["archives"].pop()
                elif mutation == "duplicate": source["archives"][1] = deepcopy(source["archives"][0])
                elif mutation == "zero": source["archives"][1]["sha256"] = "0" * 64
                else: source["source_revision"] = "9" * 64
                with self.assertRaises(catalog.CatalogError): bind(manifest, artifact)

    def test_source_archive_names_match_the_same_epoch_free_component_version(self):
        for mutation in ("version", "descriptor", "upstream", "debian_patches", "epoch"):
            with self.subTest(mutation=mutation):
                manifest, artifact = fixture()
                source = artifact["source_components"][1]
                if mutation == "version": source["component_version"] = "5.0.0-5"
                elif mutation == "epoch": source["component_version"] = "bad:5.0.0-6"
                else:
                    archive = next(a for a in source["archives"] if a["kind"] == mutation)
                    archive["url"] = archive["url"].replace("5.0.0", "5.0.1")
                with self.assertRaisesRegex(catalog.CatalogError, "source_archive_version_mismatch|invalid_source_version"):
                    bind(manifest, artifact)

    def test_epoch_and_dfsg_debian_names_are_supported_without_epoch_in_urls(self):
        manifest, artifact = fixture()
        source = artifact["source_components"][0]
        source.update(id="prusa_source", package="slic3r-prusa", component_version="2.9.2+dfsg-1")
        for archive in source["archives"]:
            name = "slic3r-prusa_2.9.2+dfsg" + {
                "descriptor": "-1.dsc", "upstream": ".orig.tar.xz",
                "debian_patches": "-1.debian.tar.xz"}[archive["kind"]]
            archive["url"] = "https://deb.debian.org/debian/pool/main/s/slic3r-prusa/" + name
        files = tuple(catalog._file({"path": p, "sha256": "b" * 64, "size_bytes": 1,
                                   "role": "license" if p.startswith("licenses/") else "engine",
                                   "executable": p == "bin/CuraEngine"}) for p in source["files"])
        parsed = catalog._source_components([source], "prusaslicer", files)
        self.assertEqual(parsed[0].component_version, "2.9.2+dfsg-1")
        self.assertEqual(bind(*fixture()).artifacts[0].source_components[0].component_version, "1:5.0.0-5")

    def test_source_urls_are_package_scoped_without_widening_existing_primary_source_policy(self):
        for url in ("https://deb.debian.org/debian/pool/main/x/other/cura_5.0.0-6.dsc",
                    "https://deb.debian.org.evil.invalid/debian/pool/main/c/cura/cura_5.0.0-6.dsc",
                    "https://deb.debian.org/debian/pool/main/c/cura/cura_5.0.0-6.dsc?secret=private",
                    "https://deb.debian.org/debian/pool/main/c/cura/unreviewed/cura_5.0.0-6.dsc",
                    "https://deb.debian.org/debian/pool/main/c/cura//cura_5.0.0-6.dsc"):
            with self.subTest(url=url):
                manifest, artifact = fixture()
                artifact["source_components"][1]["archives"][0]["url"] = url
                with self.assertRaises(catalog.CatalogError): bind(manifest, artifact)
        manifest, artifact = fixture()
        artifact["source_url"] = "https://deb.debian.org/debian/pool/main/c/cura/cura_5.0.0-6.dsc"
        with self.assertRaisesRegex(catalog.CatalogError, "untrusted_url"): bind(manifest, artifact)

    def test_duplicate_components_and_wrong_package_for_engine_are_rejected(self):
        for field, value in (("id", "engine_source"), ("package", "slic3r-prusa"), ("component_version", "latest")):
            with self.subTest(field=field):
                manifest, artifact = fixture()
                artifact["source_components"][1][field] = value
                with self.assertRaises(catalog.CatalogError): bind(manifest, artifact)

    def test_source_components_are_detached_immutable_and_do_not_claim_actual_sources(self):
        manifest, artifact = fixture()
        release = bind(manifest, artifact)
        artifact["source_components"][0]["archives"][0]["sha256"] = "9" * 64
        self.assertEqual(release.artifacts[0].source_components[0].archives[0].sha256, "e" * 64)
        with self.assertRaises(FrozenInstanceError):
            release.artifacts[0].source_components[0].component_version = "other"


if __name__ == "__main__": unittest.main()
