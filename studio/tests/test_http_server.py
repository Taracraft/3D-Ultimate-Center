from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient, TestServer

from api.http_server import create_http_application
from core.bootstrap import build_runtime
from core.paths import StudioPaths
from core.version import STUDIO_VERSION


@pytest.mark.asyncio
async def test_health_and_version_routes_report_ready_runtime(tmp_path) -> None:
    runtime = build_runtime(StudioPaths(tmp_path / "3D-Studio"))
    client = TestClient(TestServer(create_http_application(runtime)))
    await client.start_server()
    try:
        response = await client.get("/api/ultimate_3d_studio/v1/system/health")
        assert response.status == 200
        payload = await response.json()
        assert payload["error"] is None
        assert payload["data"]["status"] == "ready"
        assert payload["data"]["studio_version"] == STUDIO_VERSION
        assert payload["data"]["schema_version"] == 8
        assert payload["request_id"] == response.headers["X-Request-ID"]
        assert response.headers["X-Printer-Control-Center-Version"] == STUDIO_VERSION

        response = await client.get("/api/ultimate_3d_studio/v1/system/version")
        assert response.status == 200
        payload = await response.json()
        assert payload["data"] == {
            "studio_version": STUDIO_VERSION,
            "api_version": "v1",
            "api_base": "/api/ultimate_3d_studio/v1",
            "schema_version": 8,
        }
        assert payload["request_id"] == response.headers["X-Request-ID"]
    finally:
        await client.close()
        runtime.close()
