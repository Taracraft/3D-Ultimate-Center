from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _text(name: str) -> str:
    return (FRONTEND / name).read_text(encoding="utf-8-sig")


def test_visible_branding_uses_one_central_authority() -> None:
    branding = _text("branding.ts")
    assert 'productName: "3D Ultimate Studio"' in branding
    assert 'slicerName: "3D Ultimate Slicer"' in branding
    for name in (
        "merge-studio-workspace.ts",
        "mesh-export.ts",
        "slicer-workspace-v2.ts",
        "slicer-workspace-v3.ts",
        "studio-export-service.ts",
        "studio-mega-ui-v2.ts",
        "studio-mega-ui.ts",
        "studio-workspace-v2.ts",
        "studio-workspace-v3.ts",
        "three-mf-export-stream.ts",
        "three-mf-export.ts",
        "studio-entry.ts",
    ):
        assert 'from "./branding.js"' in _text(name)


def test_internal_studio_compatibility_identifiers_are_unchanged() -> None:
    entry = _text("studio-entry.ts")
    api = _text("slicing-api.ts")
    jobs = _text("global-job-popup-v3.ts")
    assert '"ultimate-3d-studio-card"' in entry
    assert 'customElements.define("ultimate-3d-studio-card"' in entry
    assert '"/api/ultimate_3d_studio/v1/slicer"' in api
    assert '"ultimate-3d-studio:job-popup-dismissed"' in jobs
