from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
COMPONENT = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)
SERVER = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "host"
    / "3d-printer-slicing-server"
    / "server.py"
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def test_frontend_exposes_only_native_slicing_server() -> None:
    files = (
        FRONTEND / "slicing-api.ts",
        FRONTEND / "plate-slice-api.ts",
        FRONTEND / "studio-slicer-backend.ts",
        FRONTEND / "studio-process-options-panel.ts",
        FRONTEND / "studio-process-options-state.ts",
        FRONTEND / "studio-mega-workspace.ts",
        FRONTEND / "studio-mega-workspace-v2.ts",
        FRONTEND / "global-job-popup-v3.ts",
    )
    source = "\n".join(_text(path) for path in files)
    for forbidden in (
        '"pc"',
        "data-backend",
        "PC-Worker",
        "PC-Slicer",
        'SlicerBackend = "pc"',
    ):
        assert forbidden not in source, forbidden
    assert 'export type SlicerBackend = "server";' in source
    assert "Nativer Linux-Slicing-Server" in source


def test_backend_has_no_remote_slicer_client_or_alternate_job_ids() -> None:
    router = _text(COMPONENT / "slicer_backend_router.py")
    legacy_client = _text(COMPONENT / "slicer_worker_client.py")
    for forbidden in (
        "BACKEND_PC",
        "PC_PREFIX",
        "pc__",
        "SlicerWorkerClient",
        "ultimate_3d_studio_v6_slicer_worker.json",
        "urlparse",
    ):
        assert forbidden not in router + legacy_client, forbidden
    assert 'SERVER_ENDPOINT = "http://127.0.0.1:8099"' in router
    assert "native_job_id(job_id)" in router
    assert "async_list_jobs" in router
    assert "async_delete_job" in router


def test_native_server_deletes_only_terminal_jobs() -> None:
    source = _text(SERVER)
    assert "def do_DELETE(self)" in source
    assert 'status not in {"completed", "failed", "cancelled"}' in source
    assert '"active_job_cannot_be_deleted"' in source
    assert "delete_terminal_job(job_id)" in source
