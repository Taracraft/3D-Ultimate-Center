"""Regression contracts for gallery project replacement and direct-print ownership."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"


def test_gallery_project_replacement_commits_only_after_complete_preparation() -> None:
    source = (FRONTEND / "studio-mega-workspace-v2.ts").read_text(encoding="utf-8-sig")
    request = source[source.index("  #requestImport("):source.index("  connectedCallback()", source.index("  #requestImport("))]
    load = source[source.index("  async #load(file:"):source.index("  #collectExtruders(")]
    assert "#resetWorkspaceForProjectOpen" not in request
    assert load.index("await fetchScene(") < load.index("if (replaceWorkspace) this.#resetWorkspaceForProjectOpen")
    assert load.index("await buildMeshGeometryAsync(") < load.index("if (replaceWorkspace) this.#resetWorkspaceForProjectOpen")
    assert "if (generation !== this.#generation) return;" in load[load.index("} catch (error)"):]
    assert "if (committed) this.#schedulePersist(700)" in load
    assert "this.#reconcilingJobs.clear();" in source
    assert "!ACTIVE.has(activeJob.status)" in source
    shell = (FRONTEND / "app-shell-v4.ts").read_text(encoding="utf-8-sig")
    assert "clearStudioWorkspace" not in shell


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
