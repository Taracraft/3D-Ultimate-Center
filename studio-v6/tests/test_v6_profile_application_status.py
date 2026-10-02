from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)
HOST = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server"
FRONTEND = ROOT / "frontend"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def test_native_runtime_exposes_materializer_process_proof() -> None:
    server = _text(HOST / "server.py")
    materializer = _text(COMPONENT / "materialize-bambu-multimaterial.py")
    assert '"selected_process_profile": process_profile_proof' in materializer
    assert 'materials.get("selected_process_profile")' in server
    assert 'materials.get("process_settings")' in server


def test_backend_keeps_selected_applied_and_gcode_confirmed_distinct() -> None:
    router = _text(COMPONENT / "slicer_backend_router.py")
    assert '"selected": selected' in router
    assert '"applied": applied' in router
    assert '"gcode_confirmed": gcode_confirmed' in router
    assert 'process_proof.get("contract_sha256")' in router
    assert "extract_gcode_settings(" in router
    assert "_materials_confirmed(applied_filaments, analysis)" in router
    assert '"parsed_gcode_header_and_toolpath"' in router


def test_frontend_displays_all_three_profile_states() -> None:
    api = _text(FRONTEND / "slicing-api.ts")
    popup = _text(FRONTEND / "global-job-popup-v3.ts")
    studio = _text(FRONTEND / "studio-mega-workspace-v2.ts")
    helper = _text(FRONTEND / "profile-application-status.ts")
    slicer = _text(FRONTEND / "slicer-workspace-v3.ts")
    jobs = _text(FRONTEND / "jobs-workspaces-v9.ts")
    for field in ("selected", "applied", "gcode_confirmed"):
        assert f"{field}: boolean" in api
    assert "gewählt" in helper
    assert "profileApplicationSummary(visibleSlicer.profile_application)" in popup
    assert "parsed_gcode_header_and_toolpath" in helper
    assert "Im Slicer angewandt" in helper
    assert "Im Artefakt bestätigt" in helper
    assert "profileApplicationMarkup(this.#job.profile_application)" in slicer
    assert "profileApplicationSummary(job.profile_application)" in jobs
    assert '"profiles_selected"' in studio
    assert '"profiles_applied"' in studio
    assert '"profiles_gcode_confirmed"' in studio
    assert "reportJobState(job);" in studio
