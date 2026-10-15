"""Standalone native HTTP/TLS bind policy tests; no print jobs or remote sockets."""
from __future__ import annotations

import ast
import ipaddress
import json
from pathlib import Path
import os
import ssl
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/server.py"
DEMO_SECRET = "test-only-secret-" + "L" * 48


def _listener(ssl_override=None):
    source = ast.parse(SERVER.read_text(encoding="utf-8"))
    listener = next(
        node for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "_listener_config"
    )
    ast.fix_missing_locations(listener)
    code = compile(ast.Module(body=[listener], type_ignores=[]), str(SERVER), "exec")
    scope = {"Path": Path, "ipaddress": ipaddress, "os": os, "ssl": ssl if ssl_override is None else ssl_override}
    exec(code, scope)
    return scope["_listener_config"]


@pytest.mark.parametrize("host", ["192.0.2.8", "0.0.0.0", "::", "example.invalid"])
def test_remote_listener_without_certificate_is_closed(host):
    with pytest.raises(SystemExit, match="Remote slicer listener requires TLS"):
        _listener()({"host": host, "port": 8099})


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_local_listener_remains_http_compatible(host):
    address, port, context = _listener()({"host": host, "port": 8099})
    assert address == host
    assert port == 8099
    assert context is None


@pytest.mark.parametrize("config", [
    {"host": "0.0.0.0", "tls_certfile": "/tmp/mock.crt"},
    {"host": "127.0.0.1", "tls_keyfile": "/tmp/mock.key"},
])
def test_half_configured_tls_is_rejected(config):
    with pytest.raises(SystemExit, match="certificate pair incomplete"):
        _listener()(config)


@pytest.mark.parametrize("invalid_host", ["", " localhost", "127.0.0.1\n", "a/b", "user@host"])
def test_invalid_bind_host_is_rejected(invalid_host):
    with pytest.raises(SystemExit, match="Invalid native slicer listener host"):
        _listener()({"host": invalid_host})


def test_invalid_tls_key_is_rejected_without_path_or_secret_in_error(tmp_path):
    fake_cert = tmp_path / "server.crt"
    fake_key = tmp_path / "secret-key.pem"
    fake_cert.write_text("not a certificate")
    fake_key.write_text("not a private key")
    with pytest.raises(SystemExit) as exc:
        _listener()({
            "host": "192.0.2.8", "port": 8099,
            "tls_certfile": str(fake_cert), "tls_keyfile": str(fake_key),
        })
    assert "certificate or key is invalid" in str(exc.value)
    assert str(fake_key) not in str(exc.value)


def test_actual_server_refuses_network_http_before_creating_state(tmp_path):
    config = tmp_path / "config.json"
    state = tmp_path / "state"
    config.write_text(json.dumps({
        "host": "192.0.2.8", "port": 8099,
        "base_dir": str(state), "token": DEMO_SECRET,
    }), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SERVER), str(config)],
        capture_output=True, text=True, timeout=8, check=False,
    )
    assert result.returncode != 0
    assert "Remote slicer listener requires TLS" in result.stdout + result.stderr
    assert not state.exists()
    assert DEMO_SECRET not in result.stdout + result.stderr


def test_tls_socket_wrapping_must_precede_any_server_traffic():
    server = SERVER.read_text(encoding="utf-8")
    assert "TLS_CONTEXT.wrap_socket(server.socket, server_side=True)" in server
    assert server.index("TLS_CONTEXT.wrap_socket") < server.rindex("server.serve_forever()")
    assert "context.minimum_version = ssl.TLSVersion.TLSv1_2" in server



def test_remote_listener_with_verified_tls_pair_builds_secure_context(tmp_path):
    certificate = tmp_path / "test.crt"
    private_key = tmp_path / "test.key"
    certificate.write_text("synthetic-certificate-only-for-unit-test")
    private_key.write_text("synthetic-private-key-only-for-unit-test")
    private_key.chmod(0o600)

    created = []

    class FakeContext:
        def __init__(self, protocol):
            self.protocol = protocol
            self.minimum_version = None
            self.loaded = None
            created.append(self)

        def load_cert_chain(self, *, certfile, keyfile):
            self.loaded = (certfile, keyfile)

    fake_ssl = SimpleNamespace(
        SSLContext=FakeContext,
        PROTOCOL_TLS_SERVER=123,
        TLSVersion=SimpleNamespace(TLSv1_2=456),
        SSLError=ssl.SSLError,
    )
    address, port, context = _listener(fake_ssl)({
        "host": "192.0.2.8", "port": 8443,
        "tls_certfile": str(certificate),
        "tls_keyfile": str(private_key),
    })
    assert (address, port) == ("192.0.2.8", 8443)
    assert context is created[0]
    assert context.protocol == 123
    assert context.minimum_version == 456
    assert context.loaded == (str(certificate), str(private_key))
