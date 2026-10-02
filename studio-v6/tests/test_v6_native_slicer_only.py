from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
CORE = ROOT / "core"
COMPONENT = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "custom_components"
    / "ultimate_3d_studio_v6"
)
HOST_SERVER = (
    ROOT
    / "deploy"
    / "homeassistant"
    / "host"
    / "3d-printer-slicing-server"
    / "server.py"
)


def _joined(paths: list[Path]) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8-sig")
        for path in paths
    )


def test_active_sources_have_no_remote_computer_slicing_path() -> None:
    frontend = _joined(sorted(FRONTEND.glob("*.ts")))
    backend = _joined(sorted(COMPONENT.rglob("*.py")))
    forbidden_frontend = [
        '"pc"',
        "PC-Worker",
        "PC-Slicer",
        "cancelSliceJob",
        "cancelActiveSlicerJob",
        "data-cancel-slicer",
        'data-backend="pc"',
        "Worker",
        "worker",
    ]
    forbidden_backend = [
        "BACKEND_PC",
        "PC_PREFIX",
        "pc__",
        ".slicer_worker_client import",
        "SlicerWorkerClient",
        "ultimate_3d_studio_v6_slicer_worker.json",
        "127.0.0.1:5000",
        "localhost:5000",
    ]
    for marker in forbidden_frontend:
        assert marker not in frontend, marker
    for marker in forbidden_backend:
        assert marker not in backend, marker


def test_router_is_fail_closed_to_fixed_native_server() -> None:
    router = (COMPONENT / "slicer_backend_router.py").read_text(
        encoding="utf-8-sig"
    )
    views = (COMPONENT / "slicer_views.py").read_text(
        encoding="utf-8-sig"
    )
    assert 'SERVER_ENDPOINT = "http://127.0.0.1:8099"' in router
    assert "Nur der native Linux-Slicing-Server ist zulässig." in router
    assert "server__-Präfix erforderlich" in router
    assert "async_cancel_job" not in router
    assert "SlicerJobCancelView" not in views
    assert '/jobs/{job_id}/cancel' not in views


def test_native_server_deletes_only_terminal_jobs() -> None:
    server = HOST_SERVER.read_text(encoding="utf-8-sig")
    assert "def do_DELETE(self) -> None:" in server
    assert 'status not in {"completed", "failed", "cancelled"}' in server
    assert '"error": "job_not_terminal"' in server
    assert "status = 409" not in server
    assert '"status": 409' in server
    assert "_upload_is_referenced(input_file)" in server
    assert 'RUN.glob(f"{job_id}-*")' in server


def test_retired_remote_clients_are_inert() -> None:
    retired = [
        "slicer_worker_client.py",
        "slicer_plate_archive.py",
        "slicer_plate_client.py",
        "slicer_plate_client_v2.py",
    ]
    for filename in retired:
        source = (COMPONENT / filename).read_text(encoding="utf-8-sig")
        assert len(source.splitlines()) == 1
        assert "native Linux server routing is authoritative" in source

RETIRED_MIGRATIONS = (
    "apply_job_backend_binding_fix.mjs",
    "apply_pc_process_base_reference_fix.mjs",
    "apply_pc_process_compatibility_fix.mjs",
    "apply_server_metrics_direct_print.mjs",
    "apply_slice_activity_popup_20260810.mjs",
    "apply_slice_activity_popup_fix_20260810.mjs",
    "apply_slicer_backend_labels.mjs",
    "apply_v6_native_slicer_telemetry_20260811.mjs",
)
RETIRED_MIGRATION_SOURCE = (
    'throw new Error("Retired migration: native Linux '
    'slicing-server sources are authoritative.");'
)


def test_retired_migration_scripts_are_fail_closed() -> None:
    for filename in RETIRED_MIGRATIONS:
        source = (ROOT / filename).read_text(
            encoding="utf-8-sig"
        ).strip()
        assert source == RETIRED_MIGRATION_SOURCE, filename


def test_local_cli_slicing_execution_is_retired() -> None:
    retired = [
        "local_slicer.py",
        "slicer_config.py",
        "managed_process_runner.py",
    ]
    for filename in retired:
        source = (CORE / filename).read_text(encoding="utf-8-sig")
        assert len(source.splitlines()) == 1
        assert "removed" in source


def test_retired_migrations_cannot_reintroduce_computer_slicing() -> None:
    migrations = [
        "apply_job_backend_binding_fix.mjs",
        "apply_pc_process_base_reference_fix.mjs",
        "apply_pc_process_compatibility_fix.mjs",
        "apply_server_metrics_direct_print.mjs",
        "apply_slice_activity_popup_20260810.mjs",
        "apply_slice_activity_popup_fix_20260810.mjs",
        "apply_slicer_backend_labels.mjs",
        "apply_v6_native_slicer_telemetry_20260811.mjs",
    ]
    for filename in migrations:
        source = (ROOT / filename).read_text(encoding="utf-8-sig")
        assert len(source.splitlines()) == 1
        assert source.startswith("throw new Error")
        assert "native Linux slicing-server sources are authoritative" in source


def test_architecture_has_no_runtime_selectable_slicing_host() -> None:
    architecture = (
        ROOT / "docs" / "architecture" / "SYSTEM_ARCHITECTURE.md"
    ).read_text(encoding="utf-8-sig")
    assert "127.0.0.1:8099" in architecture
    assert "no selectable local-computer" in architecture
    assert "Bambu LAN printer transfer remains a separate print path" in architecture
    for marker in ("local_bambu_cli", "local_orca_cli", "external_http"):
        assert marker not in architecture
