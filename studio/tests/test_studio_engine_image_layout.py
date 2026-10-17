"""Fixed image resource wiring; synthetic data only, no engine or Docker execution."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio_engine_image_layout", ROOT / "Slicer-Server/container_engines.py")
engines = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engines)


class ImageSourceTests(unittest.TestCase):
    def test_reviewed_prusa_resources_and_plugin_have_fixed_image_targets(self):
        links = engines.image_link_plan()
        self.assertEqual(len(links), 12)
        for name in ("data", "icons", "localization", "profiles", "shaders", "shapes", "web"):
            self.assertEqual(links["usr/share/PrusaSlicer/" + name], "engine/prusaslicer/resources/" + name)
        self.assertEqual(links["usr/lib/x86_64-linux-gnu/PrusaSlicer/OCCTWrapper.so"],
                         "engine/prusaslicer/lib/PrusaSlicer/OCCTWrapper.so")
        self.assertEqual(links["usr/share/cura/resources"], "engine/curaengine/resources")

    def test_font_dependencies_are_system_references_not_bundled_font_bytes(self):
        links = engines.image_link_plan()
        self.assertEqual(links["usr/share/PrusaSlicer/fonts/NotoSans-Regular.ttf"],
                         "usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
        self.assertEqual(links["usr/share/PrusaSlicer/fonts/NotoSansCJK-Regular.ttc"],
                         "usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
        docker = (ROOT / "Slicer-Server/Dockerfile").read_text(encoding="utf-8-sig")
        self.assertRegex(docker, r"(?m)^\s+fonts-noto-core\s+\\$")
        self.assertRegex(docker, r"(?m)^\s+fonts-noto-cjk\s+\\$")

    def test_no_engine_executables_are_added_to_path(self):
        links = engines.image_link_plan()
        self.assertTrue(all(not name.startswith(("usr/bin/", "bin/", "usr/local/bin/")) for name in links))
        self.assertFalse(any("bambu-studio" in p for p in links))
        self.assertTrue(all(not p.startswith("/") and ".." not in p.split("/") for pair in links.items() for p in pair))

    def test_plan_is_detached_and_has_no_generation_or_machine_specific_paths(self):
        plan = engines.image_link_plan()
        plan["usr/share/cura/resources"] = "elsewhere"
        self.assertEqual(engines.image_link_plan()["usr/share/cura/resources"], "engine/curaengine/resources")
        self.assertNotIn("generations", json.dumps(engines.image_link_plan()))
        self.assertNotIn("homeassist", json.dumps(engines.image_link_plan()))

    def test_docker_build_prepares_and_checks_layout_before_unprivileged_user(self):
        docker = (ROOT / "Slicer-Server/Dockerfile").read_text(encoding="utf-8-sig")
        for token in ("container_engines.py prepare-image", "container_engines.py verify-image"):
            self.assertIn(token, docker)
            self.assertLess(docker.index(token), docker.index("USER 65532:65532"))
        self.assertLess(docker.index("COPY --chown=65532:65532"), docker.index("container_engines.py prepare-image"))

    def test_cura_search_path_is_fixed_in_image_without_ambient_suffix(self):
        docker = (ROOT / "Slicer-Server/Dockerfile").read_text(encoding="utf-8-sig")
        wanted = "ENV CURA_ENGINE_SEARCH_PATH=/engine/curaengine/resources/definitions:/engine/curaengine/resources/extruders"
        self.assertIn(wanted, docker.splitlines())
        self.assertNotIn("${CURA_ENGINE_SEARCH_PATH}", docker)

    def test_sbom_reference_matches_dockerfile_and_all_declared_packages(self):
        raw = (ROOT / "Slicer-Server/Dockerfile").read_bytes()
        reference = json.loads((ROOT / "Slicer-Server/TARGET_IMAGE_REFERENCE.json").read_bytes())
        self.assertEqual(reference["dockerfile_sha256"], hashlib.sha256(raw).hexdigest())
        block = raw.decode("utf-8-sig").split("apt-get install -y --no-install-recommends \\", 1)[1].split("&& mkdir", 1)[0]
        packages = sorted(set(re.findall(r"(?m)^\s+([a-z][a-z0-9+.-]*)\s+\\$", block)))
        self.assertEqual(reference["required_packages"], packages)
        self.assertEqual(reference["required_package_count"], 49)
        self.assertFalse(reference["production_approved"])
        self.assertFalse(reference["target_image_verified"])

    def test_existing_pending_catalog_not_changed_by_layout(self):
        catalog = json.loads((ROOT / "Slicer-Server/engine_catalog.json").read_bytes())
        self.assertEqual(catalog["releases"], [])
        self.assertEqual(set(catalog["pending"]), set(engines.ENGINES))


class ImageFilesystemTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory(prefix="studio-image-layout-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "image"
        self.root.mkdir()
        probe = self.root / "probe-link"
        try:
            probe.symlink_to("missing-probe")
            probe.unlink()
        except OSError:
            self.skipTest("symlink creation privilege unavailable")

    def install(self):
        return engines.prepare_image_layout(self.root)

    def test_fresh_layout_contains_exact_links_without_any_engine_payload(self):
        result = self.install()
        self.assertEqual(result["links_verified"], 12)
        self.assertFalse(result["engine_executed"])
        self.assertFalse((self.root / "engine").exists())
        found = {p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_symlink()}
        self.assertEqual(found, set(engines.image_link_plan()))
        self.assertEqual(engines.verify_image_layout(self.root)["links_verified"], 12)

    def test_repeat_preserves_existing_link_identities(self):
        self.install()
        before = {p: (self.root / p).lstat().st_ino for p in engines.image_link_plan()}
        self.install()
        self.assertEqual(before, {p: (self.root / p).lstat().st_ino for p in engines.image_link_plan()})

    def test_existing_file_is_never_overwritten(self):
        target = self.root / "usr/share/PrusaSlicer/data"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"keep original")
        with self.assertRaises(engines.EnginePathError):
            self.install()
        self.assertEqual(target.read_bytes(), b"keep original")
        self.assertFalse((self.root / "usr/share/cura/resources").is_symlink())

    def test_wrong_existing_symlink_is_never_replaced(self):
        target = self.root / "usr/share/PrusaSlicer/data"
        target.parent.mkdir(parents=True)
        target.symlink_to("../../untrusted")
        with self.assertRaises(engines.EnginePathError):
            self.install()
        self.assertEqual(os.readlink(target), "../../untrusted")

    def test_existing_directory_at_link_location_is_rejected(self):
        target = self.root / "usr/share/PrusaSlicer/data"
        target.mkdir(parents=True)
        (target / "keep").write_bytes(b"keep")
        with self.assertRaises(engines.EnginePathError):
            self.install()
        self.assertTrue((target / "keep").is_file())

    def test_linked_image_parent_cannot_escape_root(self):
        outside = self.root.parent / "outside"; outside.mkdir()
        (self.root / "usr").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(engines.EnginePathError):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])

    def test_linked_root_is_rejected(self):
        alias = self.root.parent / "alias"; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(engines.EnginePathError):
            engines.prepare_image_layout(alias)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_verifier_rejects_missing_and_changed_links(self):
        self.install()
        target = self.root / "usr/share/cura/resources"; target.unlink()
        with self.assertRaises(engines.EnginePathError):
            engines.verify_image_layout(self.root)
        target.symlink_to("elsewhere")
        with self.assertRaises(engines.EnginePathError):
            engines.verify_image_layout(self.root)

    def test_relative_links_resolve_to_selected_generation_and_system_fonts(self):
        self.install()
        dirs = {"data", "icons", "localization", "profiles", "shaders", "shapes", "web"}
        for link, target in engines.image_link_plan().items():
            path = self.root / target
            if link.rsplit("/", 1)[-1] in dirs or link == "usr/share/cura/resources":
                path.mkdir(parents=True, exist_ok=True)
                (path / "synthetic.txt").write_bytes(b"resource")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic fixture; not a real font or plugin")
            self.assertEqual((self.root / link).resolve(strict=True), path.resolve(strict=True))

    def test_generation_switch_keeps_image_links_and_reads_new_payload(self):
        self.install()
        target = self.root / "engine/prusaslicer/lib/PrusaSlicer/OCCTWrapper.so"
        target.parent.mkdir(parents=True); target.write_bytes(b"generation one")
        link = self.root / "usr/lib/x86_64-linux-gnu/PrusaSlicer/OCCTWrapper.so"
        before = link.lstat().st_ino
        self.assertEqual(link.read_bytes(), b"generation one")
        target.write_bytes(b"generation two")
        self.assertEqual(link.read_bytes(), b"generation two")
        self.assertEqual(link.lstat().st_ino, before)

    def test_unrelated_image_files_remain_untouched(self):
        path = self.root / "usr/share/other-data/keep.txt"
        path.parent.mkdir(parents=True); path.write_bytes(b"keep")
        self.install()
        self.assertEqual(path.read_bytes(), b"keep")

    def test_relative_and_nonexistent_roots_rejected(self):
        for root in (Path("relative"), self.root / "missing"):
            with self.subTest(root=str(root)), self.assertRaises(engines.EnginePathError):
                engines.prepare_image_layout(root)


if __name__ == "__main__":
    unittest.main()
