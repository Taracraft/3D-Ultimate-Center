"""Fail-closed documentation contract for reviewed engine provenance.

No network, package installation, archive extraction, engine execution or service
operation occurs in this test.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "Slicer-Server" / "engine_catalog.json"
PROVENANCE = ROOT / "Slicer-Server" / "ENGINE_PROVENANCE.md"
NOTICES = ROOT / "Slicer-Server" / "THIRD_PARTY_NOTICES.md"

ENGINES = {"bambu_studio", "prusaslicer", "curaengine"}
TOKENS = {
    "0b0f7c53ea506001c7b56e83d4f1a2a72e73cd960886622462a1ffb5acb78379",
    "ac3650ec34a5a5023a33775b6b8ac9e9ee27aa783550fededa6db171e523cc99",
    "4ff3972a868621f48adee0e1d6848ce27ada765a2fdc1d0cb87e81026f6c5392",
    "1976698ffa7eb6efb9a8fd093238e4a81441bef859e80c456dd8180c0348101e",
    "8bd2336dfc66c4a7934ca77c39c2220a9658888d7df866ddd98e0094363d962a",
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
