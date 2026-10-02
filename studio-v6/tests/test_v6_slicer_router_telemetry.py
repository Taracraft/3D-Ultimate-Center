from pathlib import Path


def test_completed_native_job_status_does_not_block_on_artifact_analysis():
    root = Path(__file__).resolve().parents[1]
    source = (root / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio_v6" / "slicer_backend_router.py").read_text(encoding="utf-8-sig")
    start = source.index("    async def async_get_job(")
    end = source.index("    async def _server_raw_artifact(", start)
    block = source[start:end]
    assert "await self._server_completed_artifact" not in block
    assert "metadata = _cached_metadata(raw_id)" in block
    assert "return _server_job(payload, metadata)" in block
    assert '"slicer_progress": progress' in source
    assert '"engine_result": engine_result' in source


def test_completed_artifact_keeps_analysis_metadata_without_retaining_many_archives():
    root = Path(__file__).resolve().parents[1]
    source = (root / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio_v6" / "slicer_backend_router.py").read_text(encoding="utf-8-sig")
    assert "_MAX_COMPLETED_ARTIFACT_CACHE = 1" in source
    assert "_MAX_COMPLETED_METADATA_CACHE = 100" in source
    assert "_COMPLETED_METADATA_CACHE[raw_id] = result[3]" in source
    assert "while len(_COMPLETED_METADATA_CACHE) > _MAX_COMPLETED_METADATA_CACHE:" in source


def test_artifact_path_keeps_full_validation_and_analysis():
    root = Path(__file__).resolve().parents[1]
    source = (root / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio_v6" / "slicer_backend_router.py").read_text(encoding="utf-8-sig")
    start = source.index("    async def async_artifact(")
    block = source[start:]
    assert "await self._server_completed_artifact(raw_id, payload)" in block
    assert "_prepare_server_artifact" in source
    assert "analyze_gcode(data)" in source
    assert "assert_prime_tower_inside(analysis)" in source


def test_native_server_terminal_timestamp_uses_terminal_artifacts():
    root = Path(__file__).resolve().parents[1]
    source = (root / "deploy" / "homeassistant" / "host" / "3d-printer-slicing-server" / "server.py").read_text(encoding="utf-8-sig")
    start = source.index("def job_state(job_id: str) -> dict:")
    end = source.index("\n\ndef list_jobs(", start)
    block = source[start:end]
    assert 'result_path = OUTPUT / f"{job_id}.result.json"' in block
    assert 'progress_path = OUTPUT / f"{job_id}.progress.json"' in block
    assert 'state in {"completed", "failed", "cancelled"}' in block
    assert "max(path.stat().st_mtime for path in state_timestamp_paths)" in block
