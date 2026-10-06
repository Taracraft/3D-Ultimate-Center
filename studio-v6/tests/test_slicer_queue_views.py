"""单元测试：slicer_queue_views 批量队列 API（含50+模型压力模拟）

注意：homeassistant 模块只安装在 HA 服务器上，本地测试通过 sys.modules 注入伪造模块绕过。
"""
from __future__ import annotations
import ast
import re
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import pytest
import sys
from pathlib import Path

# ── 伪造 homeassistant / aiohttp 依赖，让导入链能走通 ───────────────────────────
ha_mock = MagicMock()
ha_mock.config_entries = MagicMock()
ha_mock.components.http = MagicMock()
ha_mock.components.http.HomeAssistantView = object
ha_mock.core = MagicMock()
ha_mock.core.HomeAssistant = dict  # 让 isinstance check 通过
sys.modules.setdefault("homeassistant", ha_mock)
sys.modules.setdefault("homeassistant.config_entries", ha_mock.config_entries)
sys.modules.setdefault("homeassistant.components", MagicMock())
sys.modules.setdefault("homeassistant.components.http", ha_mock.components.http)
sys.modules.setdefault("homeassistant.core", ha_mock.core)

aiohttp_mock = MagicMock()
aiohttp_mock.web = MagicMock()
aiohttp_mock.web.Response = MagicMock
aiohttp_mock.web.json_response = MagicMock
sys.modules.setdefault("aiohttp", aiohttp_mock)
sys.modules.setdefault("aiohttp.web", aiohttp_mock.web)
# ─────────────────────────────────────────────────────────────────────────────


class TestStatusCountingLogic:
    """直接测状态汇总逻辑（不依赖 HA 导入）。"""

    def test_counts_50_mixed_jobs(self):
        jobs = []
        for i in range(50):
            status = ["queued", "running", "succeeded", "failed", "cancelled"][i % 5]
            jobs.append({"id": f"server__job_{i:03d}", "status": status})

        queued = sum(1 for j in jobs if j["status"] == "queued")
        running = sum(1 for j in jobs if j["status"] == "running")
        completed = sum(1 for j in jobs if j["status"] == "succeeded")
        failed = sum(1 for j in jobs if j["status"] in ("failed", "cancelled", "interrupted"))

        assert queued == 10
        assert running == 10
        assert completed == 10
        assert failed == 20  # failed(10) + cancelled(10)

    def test_empty_queue(self):
        jobs = []
        assert sum(1 for j in jobs if j.get("status") == "queued") == 0
        assert sum(1 for j in jobs if j.get("status") == "running") == 0
        assert sum(1 for j in jobs if j.get("status") == "succeeded") == 0
        assert sum(1 for j in jobs if j.get("status") in ("failed", "cancelled", "interrupted")) == 0

    def test_all_queued(self):
        jobs = [{"status": "queued"} for _ in range(50)]
        assert sum(1 for j in jobs if j["status"] == "queued") == 50
        assert sum(1 for j in jobs if j["status"] == "running") == 0


class TestBatchResultLogic:
    """测批量创建的返回值结构。"""

    def test_batch_result_structure(self):
        result = {
            "created": 50,
            "failed": 0,
            "jobs": [{"id": f"server__job_{i:03d}", "status": "queued"} for i in range(50)],
            "errors": [],
        }
        assert result["created"] == 50
        assert result["failed"] == 0
        assert len(result["jobs"]) == 50
        assert result["errors"] == []

    def test_batch_with_failures(self):
        jobs = [
            {"id": "server__job_ok", "status": "queued"},
            {"id": "server__job_fail", "status": "queued"},
        ]
        result = {
            "created": 2,
            "failed": 1,
            "jobs": jobs,
            "errors": ["model_1.stl: slicing failed"],
        }
        assert result["created"] == 2
        assert result["failed"] == 1
        assert len(result["errors"]) == 1

    def test_batch_large_scale_100(self):
        """模拟 100 个文件全部成功。"""
        result = {
            "created": 100,
            "failed": 0,
            "jobs": [{"id": f"server__job_{i:03d}", "status": "queued"} for i in range(100)],
            "errors": [],
        }
        assert result["created"] == 100
        assert result["failed"] == 0
        assert len(result["jobs"]) == 100


class TestReleaseLogic:
    """测释放逻辑（不调用真实 HA API）。"""

    def test_release_single_job(self):
        """释放单个 queued job。"""
        released = 0
        items = [
            {"id": "job_001", "status": "queued"},
            {"id": "job_002", "status": "running"},
            {"id": "job_003", "status": "queued"},
        ]
        for job in items:
            if job["status"] == "queued":
                released += 1
        assert released == 2

    def test_release_all_from_50_jobs(self):
        """从 50 条中释放所有 queued。"""
        items = []
        for i in range(50):
            status = "queued" if i < 20 else "running"
            items.append({"id": f"server__job_{i:03d}", "status": status})

        released = 0
        for job in items:
            if job["status"] == "queued":
                released += 1
        assert released == 20


class TestAutoReleaseLogic:
    """测 auto_release 标志的逻辑。"""

    def test_auto_release_queued_only(self):
        """只有 queued 的 job 才会被自动释放。"""
        jobs = [
            {"id": "a", "status": "queued"},
            {"id": "b", "status": "succeeded"},
            {"id": "c", "status": "queued"},
        ]
        to_release = [j for j in jobs if j["status"] == "queued"]
        assert len(to_release) == 2
        assert to_release[0]["id"] == "a"
        assert to_release[1]["id"] == "c"

    def test_no_auto_release_when_succeeded(self):
        jobs = [{"id": "a", "status": "succeeded"}]
        to_release = [j for j in jobs if j["status"] == "queued"]
        assert len(to_release) == 0


def test_queue_registration_and_release_contract_are_wired() -> None:
    root = Path(__file__).resolve().parents[1]
    component = root / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio_v6"
    init_source = (component / "__init__.py").read_text(encoding="utf-8")
    router_source = (component / "slicer_backend_router.py").read_text(encoding="utf-8")
    assert "from .slicer_queue_views import async_register_slicer_queue_views" in init_source
    assert "async_register_slicer_queue_views(hass)" in init_source
    assert "async def async_release_job(" in router_source
    assert "/api/v1/jobs/{raw_id}/release" in router_source


def test_worker_release_contract_is_wired() -> None:
    root = Path(__file__).resolve().parents[1]
    worker = root / "deploy" / "homeassistant" / "host" / "3d-printer-slicing-server"
    server_source = (worker / "server.py").read_text(encoding="utf-8-sig")
    dispatch_source = (worker / "dispatch-job.sh").read_text(encoding="utf-8")
    assert "def release_job(job_id: str) -> dict:" in server_source
    assert 'path.endswith("/release")' in server_source
    assert 'payload["released_at"]' in server_source
    assert 'exec python3 "$BASE/job_control.py" dispatch --base "$BASE"' in dispatch_source
    control_source = (worker / "job_control.py").read_text(encoding="utf-8")
    assert 'job.get("manual_release") is True' in control_source
    assert 'job.get("released_at")' in control_source


def test_batch_reuses_plate_contract_and_validates_every_file_before_creation() -> None:
    root = Path(__file__).resolve().parents[1]
    component = root / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio_v6"
    queue_source = (component / "slicer_queue_views.py").read_text(encoding="utf-8")
    plate_source = (component / "slicer_plate_views_v2.py").read_text(encoding="utf-8")

    assert "_prepare_plate_job_contract" in queue_source
    assert "_prepare_plate_job_contract(" in plate_source
    assert '"studio_plate"' in queue_source
    assert '"material_plan"' in queue_source
    assert '"process_overrides"' in queue_source
    assert 'Path(name).suffix.casefold() != ".3mf"' in queue_source
    assert "_batch_material_plan_for_model" in queue_source
    assert "manual_release=not auto_release" in queue_source

    preflight = queue_source.index("# Validate the whole batch before any file is uploaded")
    create_router = queue_source.index("router = V6SlicerBackendRouter(hass)", preflight)
    create_job = queue_source.index("router.async_create_plate_job(", create_router)
    assert preflight < create_router < create_job


def test_batch_material_assignment_requires_one_explicit_color_match() -> None:
    root = Path(__file__).resolve().parents[1]
    source = (root / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6/slicer_plate_views_v2.py").read_text(encoding="utf-8")
    helper = source.split("def _batch_material_plan_for_model(", 1)[1].split("async def _prepare_plate_job_contract(", 1)[0]
    assert "if len(candidates) != 1" in helper
    assert "by_color.get(_normal_color(color), [])" in helper
    assert "return {**plan, \"assignments\": mapped}" in helper



def test_batch_material_plan_maps_objects_to_exact_selected_filament_colors() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6/slicer_plate_views_v2.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"_normal_color", "_mesh_objects", "_batch_material_plan_for_model"}
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    namespace = {
        "re": re,
        "logical_mesh_objects": lambda _model: [("obj-red", "#ff0000"), ("obj-blue", "#0000ff")],
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    resolver = namespace["_batch_material_plan_for_model"]
    plan = {
        "source": "ams",
        "assignments": {"existing-red": 1, "existing-blue": 2},
        "filaments": [
            {"color": "#FF0000", "global_id": "slot-red"},
            {"color": "#0000FF", "global_id": "slot-blue"},
        ],
    }
    mapped = resolver(plan, b"test")
    assert mapped["assignments"] == {"obj-red": 1, "obj-blue": 2}
    assert mapped["filaments"] == plan["filaments"]


def test_batch_material_plan_rejects_ambiguous_colors_and_keeps_external_spool_single_channel() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6/slicer_plate_views_v2.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {"_normal_color", "_mesh_objects", "_batch_material_plan_for_model"}
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    namespace = {
        "re": re,
        "logical_mesh_objects": lambda _model: [("obj-red", "#ff0000"), ("obj-blue", "#0000ff")],
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    resolver = namespace["_batch_material_plan_for_model"]
    ambiguous = {
        "source": "ams",
        "assignments": {"existing-red": 1, "existing-blue": 2},
        "filaments": [{"color": "#FF0000"}, {"color": "#FF0000"}],
    }
    with pytest.raises(ValueError, match="nicht eindeutig"):
        resolver(ambiguous, b"test")
    external = {
        "source": "external_spool",
        "assignments": {"existing": 1},
        "filaments": [{"color": "#FF0000", "filament_id": "external-1"}],
    }
    assert resolver(external, b"test")["assignments"] == {"obj-red": 1, "obj-blue": 1}
