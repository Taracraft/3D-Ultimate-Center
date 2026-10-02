"""Regression contracts for gallery project replacement and direct-print ownership."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio_v6"


def test_gallery_project_reset_happens_before_async_model_inspection() -> None:
    source = (FRONTEND / "studio-mega-workspace-v2.ts").read_text(encoding="utf-8-sig")
    reset_call = source.index("if (replaceWorkspace) this.#resetWorkspaceForProjectOpen")
    load_call = source.index("void this.#load(value, replaceWorkspace, galleryAssetId)")
    assert reset_call < load_call
    assert "jobActivityStore.dismissSlicerJob();" in source
    assert "this.#reconcilingJobs.clear();" in source
    assert "this.#plates = [newPlate(0" in source
    assert 'this.#mode = "prepare";' in source


def test_direct_print_strip_requires_the_active_plate_job_id() -> None:
    ui = (FRONTEND / "studio-mega-ui-v2.ts").read_text(encoding="utf-8-sig")
    strip = (FRONTEND / "studio-direct-print-strip.ts").read_text(encoding="utf-8-sig")
    workspace = (FRONTEND / "studio-mega-workspace-v2.ts").read_text(encoding="utf-8-sig")
    assert 'job-id="${esc(active?.jobId || "")}"' in ui
    assert 'return ["plate-id", "job-id", "has-model"]' in strip
    assert "candidate.id === expectedJobId" in strip
    assert "jobId: item.jobId" in workspace


def test_historical_failed_state_is_ready_only_after_error_checks() -> None:
    source = (BACKEND / "direct_print_views.py").read_text(encoding="utf-8-sig")
    assert '    "failed",' in source
    assert source.index("blocking_issue = _active_blocking_issue") < source.index("state = str(printer.printer_state")
    assert source.index('error_code = getattr(printer, "error_code"') < source.index("state = str(printer.printer_state")
