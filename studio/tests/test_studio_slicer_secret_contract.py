"""Native slicing-server authentication regression tests; no printer or slicer jobs."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "deploy" / "homeassistant" / "host" / "3d-printer-slicing-server" / "server.py"
DEMO_SECRET = "test-only-secret-" + "A" * 48


def _configuration(tmp_path: Path, *, secret: object, port: int = 0) -> Path:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps({
            "base_dir": str(tmp_path / "data"),
            "host": "127.0.0.1",
            "port": port,
            "token": secret,
        }),
        encoding="utf-8",
    )
    return config


@pytest.mark.parametrize(
    "secret",
    [None, "", " ", "too-short", "A" * 31, "A" * 257, "A" * 40 + "\n", "é" * 40],
)
def test_server_rejects_missing_or_invalid_secret_before_initializing_state(
    tmp_path: Path,
    secret: object,
) -> None:
    config = _configuration(tmp_path, secret=secret)
    finished = subprocess.run(
        [sys.executable, str(SERVER), str(config)],
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    assert finished.returncode != 0
    assert "Slicer API secret missing or invalid; refusing to start" in (
        finished.stdout + finished.stderr
    )
    assert not (tmp_path / "data").exists(), "Invalid config must not initialize writable state"
    if isinstance(secret, str) and len(secret.strip()) >= 4:
        assert secret not in finished.stdout + finished.stderr


def _request_status(url: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
    try:
        with urlopen(Request(url, headers=headers or {}), timeout=1.5) as response:
            return response.status, response.read()
    except HTTPError as exc:
        return exc.code, exc.read()


def test_native_server_enforces_token_for_info_and_status_without_any_jobs(
    tmp_path: Path,
) -> None:
    # Test HTTP remains bound only to loopback, with a disposable temp state directory.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = _configuration(tmp_path, secret=DEMO_SECRET, port=port)
    process = subprocess.Popen(
        [sys.executable, str(SERVER), str(config)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise AssertionError("Test server exited before binding its local API")
            try:
                status, _ = _request_status(url + "/info.json")
                if status == 401:
                    break
                raise AssertionError(f"Unauthenticated info endpoint returned HTTP {status}")
            except URLError:
                time.sleep(0.05)
        else:
            raise AssertionError("Disposable test server did not bind to loopback")

        for endpoint in ("/info.json", "/status.json"):
            status, _ = _request_status(url + endpoint)
            assert status == 401, endpoint

            status, _ = _request_status(
                url + endpoint, {"Authorization": "Bearer " + "wrong" * 12},
            )
            assert status == 401, endpoint

            status, payload = _request_status(
                url + endpoint, {"Authorization": "Bearer " + DEMO_SECRET},
            )
            assert status == 200, endpoint
            assert isinstance(json.loads(payload), dict)

        status, _ = _request_status(
            url + "/info.json", {"X-API-Token": DEMO_SECRET},
        )
        assert status == 200

        # Health remains reachable without a token, but exposes no raw internals.
        (tmp_path / "data" / "api" / "health.json").write_text(
            json.dumps({
                "status": "ready",
                "internal_hostname": "private.example.invalid",
                "token": "test-only-health-secret",
                "details": {"path": "/private/runtime"},
            }),
            encoding="utf-8",
        )
        status, public_body = _request_status(url + "/health.json")
        assert status == 200
        public_health = json.loads(public_body)
        assert set(public_health) == {"status", "version", "api_version", "uptime_seconds"}
        assert public_health["status"] == "ready"
        assert "private.example.invalid" not in public_body.decode("utf-8")
        assert "test-only-health-secret" not in public_body.decode("utf-8")

        # Even the allowed status key must never become a nested data channel.
        health_path = tmp_path / "data" / "api" / "health.json"
        for internal_status, expected_public in (
            ("starting", "starting"),
            ("degraded", "degraded"),
            ({"secret": "nested-test-only-marker"}, "degraded"),
            ("token=synthetic-test-only-marker", "degraded"),
            (None, "degraded"),
        ):
            health_path.write_text(
                json.dumps({"status": internal_status}),
                encoding="utf-8",
            )
            for health_endpoint in ("/health.json", "/api/v1/health"):
                result, response = _request_status(url + health_endpoint)
                assert result == 200
                exposed = json.loads(response)
                assert set(exposed) == {
                    "status", "version", "api_version", "uptime_seconds"
                }
                assert exposed["status"] == expected_public
                assert "test-only-marker" not in response.decode("utf-8")

        assert not list((tmp_path / "data" / "data" / "jobs").glob("*.json"))
    finally:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
        assert DEMO_SECRET not in stdout + stderr
