from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"


def test_studio_project_repository_is_bounded_and_conflict_safe() -> None:
    source = (COMPONENT / "studio_project_repository.py").read_text(encoding="utf-8")
    assert "MAX_PROJECTS = 40" in source
    assert "MAX_REVISIONS = 30" in source
    assert "MAX_SNAPSHOT_BYTES = 12 * 1024 * 1024" in source
    assert "ProjectConflictError" in source
    assert "expected_revision" in source
    assert "allow_nan=False" in source
    assert "async_restore" in source


def test_studio_project_views_are_authenticated_and_registered() -> None:
    source = (COMPONENT / "studio_project_views.py").read_text(encoding="utf-8")
    init = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    assert source.count("requires_auth = True") == 4
    assert "admin_required" in source
    assert "revision_conflict" in source
    assert "async def post(self, request: web.Request, project_id: str)" in source
    assert "async def put(" not in source
    assert "/{project_id}/revisions" in source
    assert "/{project_id}/restore" in source
    assert "async_register_studio_project_views(hass)" in init
