"""Fail-closed documentation contract for reviewed engine provenance.

No network, package installation, archive extraction, engine execution or service
operation occurs in this test.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "Slicer-Server" / "engine_catalog.json"
BUILD_REFERENCE = ROOT / "Slicer-Server" / "BAMBU_BUILD_REFERENCE.json"
PROVENANCE = ROOT / "Slicer-Server" / "ENGINE_PROVENANCE.md"
NOTICES = ROOT / "Slicer-Server" / "THIRD_PARTY_NOTICES.md"

ENGINES = {"bambu_studio", "prusaslicer", "curaengine"}
TOKENS = {
    "0b0f7c53ea506001c7b56e83d4f1a2a72e73cd960886622462a1ffb5acb78379",
    "ac3650ec34a5a5023a33775b6b8ac9e9ee27aa783550fededa6db171e523cc99",
    "4ff3972a868621f48adee0e1d6848ce27ada765a2fdc1d0cb87e81026f6c5392",
    "1976698ffa7eb6efb9a8fd093238e4a81441bef859e80c456dd8180c0348101e",
    "8bd2336dfc66c4a7934ca77c39c2220a9658888d7df866ddd98e0094363d962a",
    "fa98b608532dfbbbb2b0931483aac41e57fb19c175a2cc7bd7d528d5e0fbb287",
    "c1b3547ae00b03412e4ba8e7b053481167acdf6a",
    "42d319c6692fa8e64790fddf0cdaafd2a4254bcc",
}


class EngineProvenanceContractTests(unittest.TestCase):
    def test_shipped_catalog_keeps_every_engine_pending(self):
        value = json.loads(CATALOG.read_text(encoding="utf-8-sig"))
        self.assertEqual(value["releases"], [])
        self.assertEqual(set(value["pending"]), ENGINES)

    def test_reviewed_artifacts_are_pinned_without_approval(self):
        document = " ".join(PROVENANCE.read_text(encoding="utf-8-sig").split())
        for token in TOKENS:
            with self.subTest(token=token):
                self.assertIn(token, document)
        self.assertIn("1:5.0.0-5", document)
        self.assertIn("5.0.0-6", document)
        self.assertIn("2.9.2+dfsg-1", document)
        self.assertIn("keine Rechtsberatung", document)
        self.assertIn("keine Enginefreigabe", document)
        self.assertIn("Alle drei Familien bleiben", document)
        self.assertIn("container_deploy_ready=false", document)
        self.assertIn("v02.07.01.62", document)
        self.assertIn("449304146", document)
        self.assertIn("118 ausgewaehlte", document)
        self.assertIn("unsigniert", document)
        self.assertIn("beweist weder eine unabhaengige", document)

    def test_bambu_release_build_reference_fails_closed(self):
        value = json.loads(BUILD_REFERENCE.read_text(encoding="utf-8-sig"))
        self.assertEqual(value["schema"], 1)
        self.assertEqual(value["status"], "reference_only_non_reproducible")
        self.assertEqual(
            value["release"]["source_commit"],
            "42d319c6692fa8e64790fddf0cdaafd2a4254bcc",
        )
        self.assertEqual(value["release"]["asset_id"], 449304146)
        actions = value["github_actions"]
        self.assertEqual(actions["release_run_id"], 27620769802)
        self.assertEqual(actions["dependency_build_run_id"], 26758993674)
        self.assertEqual(
            actions["deps_tree_sha1_at_dependency_build"],
            actions["deps_tree_sha1_at_release"],
        )
        wx = value["wxwidgets"]
        self.assertEqual(
            wx["resolved_commit_at_dependency_build"],
            "a9d946902685b9946d8775f07d2a73a9b5bef394",
        )
        self.assertTrue(wx["commit_signature_verified_by_github"])
        self.assertTrue(wx["selection_is_inference"])
        recipe = value["build_recipe"]
        self.assertEqual(recipe["runner_label"], "ubuntu-24.04")
        self.assertFalse(recipe["package_versions_pinned"])
        self.assertFalse(recipe["compiler_version_known"])
        closure = value["closure"]
        self.assertTrue(closure["historical_wxwidgets_commit_inferred_from_official_history"])
        self.assertFalse(closure["manufacturer_binary_reproduced"])
        self.assertFalse(closure["complete_target_image_loader_plugin_resource_sbom"])
        self.assertFalse(closure["engine_release_approved"])
        self.assertFalse(closure["production_approved"])

    def test_upstream_license_boundaries_are_explicit(self):
        document = " ".join(PROVENANCE.read_text(encoding="utf-8-sig").split())
        notices = " ".join(NOTICES.read_text(encoding="utf-8-sig").split()).replace("**", "")
        for marker in (
            "github.com/bambulab/BambuStudio/blob/master/LICENSE",
            "github.com/prusa3d/PrusaSlicer/blob/master/LICENSE",
            "github.com/Ultimaker/CuraEngine",
        ):
            self.assertIn(marker, document)
        for marker in ("Bambu Studio", "PrusaSlicer", "CuraEngine", "pending"):
            self.assertIn(marker, notices)
        self.assertIn("keine Rechts-, Release- oder Laufzeitfreigabe", notices)
        self.assertNotIn("OrcaSlicer", document)


if __name__ == "__main__":
    unittest.main()
