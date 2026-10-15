from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
FRONTEND = ROOT / "frontend"


class FilamentSettingContractTests(unittest.TestCase):
    def source(self, path: Path) -> str:
        return path.read_text(encoding="utf-8-sig")

    def test_bambu_command_contract_and_external_address(self) -> None:
        commands = self.source(BACKEND / "network_plugin" / "commands.py")
        view = self.source(BACKEND / "filament_color_views.py")
        self.assertIn('"ams_filament_setting"', commands)
        self.assertIn('normalized_color += "FF"', commands)
        self.assertIn('ams_id = 255', view)
        self.assertIn('tray_id = 0', view)
        self.assertIn('confirmation_text") or "").strip() != "FARBE SETZEN"', view)

    def test_only_official_a1_system_filaments_are_offered(self) -> None:
        view = self.source(BACKEND / "filament_color_views.py")
        catalog = self.source(BACKEND / "a1_filament_catalog.py")
        ui = self.source(FRONTEND / "ams-workspace.ts")
        self.assertIn('CATALOG_VERSION = "02.08.00.06"', catalog)
        self.assertEqual(catalog.count('"setting_id":'), 84)
        for vendor in ("Bambu Lab", "Generic", "Polymaker", "Overture", "SUNLU", "eSUN"):
            self.assertIn(f'"vendor":"{vendor}"', catalog)
        for filament_id in ("GFL99", "GFG99", "GFU99", "GFS99", "GFU02", "GFSNL08"):
            self.assertIn(f'"id":"{filament_id}"', catalog)
        self.assertIn('filament_profile(requested_id)', view)
        self.assertIn('kind not in profile["targets"]', view)
        self.assertIn("data-setting-vendor", ui)
        self.assertIn("data-setting-filament", ui)

    def test_rfid_and_telemetry_guards_are_mandatory(self) -> None:
        view = self.source(BACKEND / "filament_color_views.py")
        self.assertIn('if item.get("rfid_detected"):', view)
        self.assertIn('"telemetry_changed"', view)
        self.assertIn('_PREVIEW_TTL_SECONDS = 120.0', view)
        self.assertIn('telemetry_confirmed', view)

    def test_frontend_uses_preview_then_confirmed_apply(self) -> None:
        api = self.source(FRONTEND / "direct-print-status-api.ts")
        ui = self.source(FRONTEND / "ams-workspace.ts")
        self.assertIn("previewFilamentSetting", api)
        self.assertIn("applyFilamentSetting", api)
        self.assertIn("globalThis.confirm(preview.confirmation_message)", ui)
        self.assertIn("RFID erkannt: Hersteller, Filamentart und Farbe", ui)

    def test_profile_selection_is_serialized_and_rolls_back(self) -> None:
        studio = self.source(FRONTEND / "studio-mega-workspace-v2.ts")
        profiles = self.source(FRONTEND / "studio-profile-ui.ts")
        self.assertIn("#filamentSelectionSaving", studio)
        self.assertIn("filament_profile_selection_failed", studio)
        self.assertIn("filament_profile_ids: previous", studio)
        self.assertIn("max-height:460px", profiles)
        self.assertNotIn('cloudSelected || cloudProfiles.length ? "open"', profiles)


if __name__ == "__main__":
    unittest.main()
