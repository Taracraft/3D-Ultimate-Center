"""Source contracts for fast gallery loading and clean project handoff."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"


def test_gallery_uses_immediate_cache_and_lazy_previews() -> None:
    source = (FRONTEND / "gallery-library-pane.ts").read_text(encoding="utf-8-sig")
    assert "gallery-library-cache-v1" in source
    assert "IntersectionObserver" in source
    assert "#observePreview" in source


def test_gallery_3mf_handoff_stays_server_side_and_replaces_workspace() -> None:
    gallery = (FRONTEND / "gallery-library-pane.ts").read_text(encoding="utf-8-sig")
    shell = (FRONTEND / "app-shell-v4.ts").read_text(encoding="utf-8-sig")
    studio = (FRONTEND / "studio-mega-workspace-v2.ts").read_text(encoding="utf-8-sig")
    slicing = (FRONTEND / "slicing-api.ts").read_text(encoding="utf-8-sig")
    backend = (BACKEND / "slicer_plate_views.py").read_text(encoding="utf-8-sig")
    assert "assetId: item.asset_id" in gallery
    assert "replaceWorkspace: true" in gallery
    assert "openGalleryProject" in shell
    assert "project_workspace_replaced" in studio
    assert "inspectGallerySliceModel" in slicing
    assert "gallery_asset_id" in backend
    assert "gallery_repository(hass).download" in backend


def test_stale_hms_clear_contract_is_present() -> None:
    telemetry = (BACKEND / "telemetry.py").read_text(encoding="utf-8-sig")
    assert "error_was_explicitly_cleared" in telemetry
    assert "remove_keys(self.raw, _HMS_KEYS)" in telemetry
