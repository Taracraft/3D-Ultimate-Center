"""Isolated, authenticated HTTPS handshake acceptance for the native slicer.

Certificate/key are supplied by a temporary external test harness; the test
does not generate, print or persist private key material in the repository.
Only the protected read-only info endpoint is requested. No jobs or printers.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from pathlib import Path
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
import time
import types
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

COMPONENT = (
    Path(__file__).resolve().parents[1] / "deploy" / "homeassistant"
    / "custom_components" / "ultimate_3d_studio"
)

def _load_ha_probe():
    """Load the actual HA backend probe without bootstrapping Home Assistant."""
    package = types.ModuleType("isolated_native_tls_contract")
    package.__path__ = [str(COMPONENT)]
    sys.modules[package.__name__] = package
    for leaf in ("slicer_connection_settings", "slicer_connection_probe"):
        fullname = package.__name__ + "." + leaf
        spec = importlib.util.spec_from_file_location(fullname, COMPONENT / (leaf + ".py"))
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[fullname] = module
        spec.loader.exec_module(module)
    return sys.modules[package.__name__ + ".slicer_connection_probe"]


def _load_actual_ha_transport(aiohttp_session):
    """Instantiate the real HA SlicerClient with narrow HA interface doubles."""
    package_name = "isolated_native_tls_contract"
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = object
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    client_support = types.ModuleType("homeassistant.helpers.aiohttp_client")
    client_support.async_get_clientsession = lambda _hass: aiohttp_session
    for name, module in (
        ("homeassistant", ha),
        ("homeassistant.core", core),
        ("homeassistant.helpers", helpers),
        ("homeassistant.helpers.aiohttp_client", client_support),
    ):
        sys.modules[name] = module

    constants = types.ModuleType(package_name + ".const")
    for key, value in {
        "DOMAIN": "ultimate_3d_studio",
        "CONF_SLICER_ENABLED": "slicer_enabled",
        "CONF_SLICER_BASE_URL": "slicer_base_url",
        "CONF_SLICER_API_SECRET": "slicer_api_secret",
    }.items():
        setattr(constants, key, value)
    sys.modules[constants.__name__] = constants

    for leaf in ("slicer_native_contract", "slicer_http_client"):
        name = package_name + "." + leaf
        spec = importlib.util.spec_from_file_location(name, COMPONENT / (leaf + ".py"))
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return (
        sys.modules[package_name + ".slicer_http_client"],
        sys.modules[package_name + ".slicer_native_contract"],
    )


async def _verify_actual_ha_probe(base: str, secret: str, context: ssl.SSLContext):
    """Exercise the actual HA-OptionsFlow HTTPS probe using real aiohttp."""
    import aiohttp

    probe = _load_ha_probe()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=context)) as client:
        ready = await probe.async_probe_slicer_connection(client, base, secret)
        assert ready["status"] == "ready"
        assert ready["api_protocol"] == 2
        assert ready["server_version"]
        print("ACTUAL_HA_HTTPS_CONNECTION_PROBE=PASS")
        transport, contracts = _load_actual_ha_transport(client)
        options = {
            "slicer_enabled": True,
            "slicer_base_url": base,
            "slicer_api_secret": secret,
        }
        entry = types.SimpleNamespace(data={}, options=options)
        hass = types.SimpleNamespace(
            config_entries=types.SimpleNamespace(
                async_entries=lambda domain: [entry]
                if domain == "ultimate_3d_studio" else []
            )
        )
        native_client = transport.AuthenticatedSlicerSession(hass)
        async with native_client.get(native_client.endpoint + "/info.json") as native_info:
            assert native_info.status == 200
            details = await native_info.json()
            assert details["api_version"] == 2
        print("ACTUAL_HA_BACKEND_SLICER_CLIENT=PASS")
        try:
            async with native_client.get(
                "https://unrelated.example.invalid/info.json"
            ):
                raise AssertionError("unrelated request unexpectedly sent")
        except contracts.SlicerServerConfigurationError:
            print("ACTUAL_HA_BACKEND_FOREIGN_ORIGIN=REJECTED")
        try:
            await probe.async_probe_slicer_connection(
                client, base, "wrong-synthetic-key-" + secrets.token_urlsafe(35)
            )
        except probe.SlicerConnectionProbeError as error:
            assert str(error) == "slicer_auth_required"
        else:
            raise AssertionError("HA probe accepted a wrong bearer credential")
        print("ACTUAL_HA_PROBE_WRONG_SECRET=REJECTED")
    async with aiohttp.ClientSession() as client:
        try:
            await probe.async_probe_slicer_connection(client, base, secret)
        except probe.SlicerConnectionProbeError as error:
            assert str(error) == "slicer_certificate_error", str(error)
        else:
            raise AssertionError("HA probe accepted an untrusted certificate")
        print("ACTUAL_HA_PROBE_UNTRUSTED_CA=REJECTED")


SERVER = (
    Path(__file__).resolve().parents[1] / "deploy" / "homeassistant"
    / "host" / "3d-printer-slicing-server" / "server.py"
)


def request_status(url: str, *, context: ssl.SSLContext, token: str | None):
    headers = {"Authorization": "Bearer " + token} if token is not None else {}
    try:
        with urlopen(Request(url, headers=headers), context=context, timeout=1.5) as result:
            return result.status, result.read(8192)
    except HTTPError as error:
        return error.code, error.read(8192)


def verify_handshake(cert_path: Path, key_path: Path) -> None:
    if not cert_path.is_file() or not key_path.is_file():
        raise RuntimeError("temporary local TLS certificate pair missing")
    if not SERVER.is_file():
        raise RuntimeError("native slicer source missing")
    authorized_secret = "synthetic-acceptance-" + secrets.token_urlsafe(40)
    with tempfile.TemporaryDirectory(prefix="studio-https-probe-") as scratch:
        working = Path(scratch)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        state = working / "state"
        configuration = working / "config.json"
        configuration.write_text(json.dumps({
            "host": "127.0.0.1", "port": port,
            "base_dir": str(state),
            "tls_certfile": str(cert_path), "tls_keyfile": str(key_path),
            "token": authorized_secret,
        }), encoding="utf-8")
        trusted = ssl.create_default_context(cafile=str(cert_path))
        base = f"https://localhost:{port}"
        proc = subprocess.Popen(
            [sys.executable, str(SERVER), str(configuration)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise AssertionError("native slicer exited before opening TLS listener")
                try:
                    status, info = request_status(
                        base + "/info.json", context=trusted, token=authorized_secret,
                    )
                    assert status == 200, "trusted TLS did not return authorized server info"
                    message = json.loads(info)
                    assert message.get("api_version") == 2
                    assert isinstance(message.get("capabilities"), dict)
                    assert message.get("version")
                    print("TRUSTED_HTTPS_INFO_ENDPOINT=PASS")
                    break
                except (ConnectionRefusedError, URLError):
                    time.sleep(0.1)
            else:
                raise AssertionError("native slicer did not become ready for TLS test")

            for label, supplied_token in (
                ("NO_BEARER_TOKEN", None),
                ("INVALID_BEARER_TOKEN", "invalid-synthetic-token"),
            ):
                denied, payload = request_status(
                    base + "/info.json", context=trusted, token=supplied_token,
                )
                assert denied == 401, label
                assert authorized_secret.encode() not in payload
                print(label + "=401")

            denied_tls = False
            try:
                request_status(
                    base + "/info.json",
                    context=ssl.create_default_context(),
                    token=authorized_secret,
                )
            except (ssl.SSLCertVerificationError, URLError) as error:
                reason = getattr(error, "reason", error)
                if isinstance(reason, ssl.SSLCertVerificationError):
                    denied_tls = True
                else:
                    raise
            assert denied_tls, "untrusted TLS certificate was accepted"
            print("UNTRUSTED_CERTIFICATE=REJECTED")
            asyncio.run(_verify_actual_ha_probe(base, authorized_secret, trusted))
            print("NO_SLICING_JOBS_OR_PRINTER_ACTIONS=true")
        finally:
            proc.terminate()
            try:
                _, stderr = proc.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                _, stderr = proc.communicate(timeout=4)
            if authorized_secret in stderr:
                raise AssertionError("native server logged an API credential")
            if proc.poll() is None:
                raise AssertionError("disposable native listener was not terminated")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cert", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    verify_handshake(args.cert, args.key)


if __name__ == "__main__":
    main()
