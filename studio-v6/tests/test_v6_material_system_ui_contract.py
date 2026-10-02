from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


class MaterialSystemUiContractTests(unittest.TestCase):
    def source(self, name: str) -> str:
        return (FRONTEND / name).read_text(encoding="utf-8-sig")

    def test_navigation_uses_material_system_name(self) -> None:
        source = self.source("app-shell-view.ts")
        self.assertIn('["ams", "Materialsysteme", "◫"]', source)
        self.assertNotIn('["ams", "AMS", "◫"]', source)

    def test_all_supported_material_systems_are_visible(self) -> None:
        source = self.source("ams-workspace.ts")
        for label in (
            "AMS Lite",
            "AMS (Original / Gen 1)",
            "AMS 2 Pro",
            "AMS HT",
            "BMCU-370 / BCMU-370 (Drittanbieter)",
            "AMS-/BMCU-kompatibel (4 Slots erkannt)",
            "Externe Spule",
        ):
            self.assertIn(label, source)

    def test_official_a1_manufacturer_catalog_is_used(self) -> None:
        source = self.source("ams-workspace.ts")
        self.assertIn("status.filament_catalog?.items", source)
        self.assertIn("data-setting-vendor", source)
        self.assertIn("data-setting-filament", source)
        self.assertIn("offiziellen, für Bambu Lab A1 instanziierten Systemkatalog", source)

    def test_visual_feed_uses_only_real_active_slot(self) -> None:
        source = self.source("ams-workspace.ts")
        self.assertIn('slot.active ? "zur Düse geladen"', source)
        self.assertIn('this.#activePlate()?.materialSource === "external_spool"', source)
        self.assertIn("sendet keine Lade-, Entlade-", source)

    def test_bambu_filament_type_is_authoritative(self) -> None:
        profile_ui = self.source("studio-profile-ui.ts")
        studio = self.source("studio-mega-workspace-v2.ts")
        self.assertIn("text(profile.payload.filament_type)", profile_ui)
        self.assertIn("const material = filamentMaterial(profile);", studio)


if __name__ == "__main__":
    unittest.main()
