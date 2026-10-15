"""Standalone slicer connection settings tests; no HA runtime, network or printers."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


COMPONENT = (
    Path(__file__).resolve().parents[1]
    / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"
)
spec = importlib.util.spec_from_file_location(
    "slicer_connection_settings_contract", COMPONENT / "slicer_connection_settings.py",
)
assert spec is not None and spec.loader is not None
settings = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings)


@pytest.mark.parametrize(
    ("supplied", "expected"),
    [
        ("https://SLICER.example.org:8443/", "https://slicer.example.org:8443"),
        ("https://slicer.internal", "https://slicer.internal"),
        ("https://192.168.50.10:8443", "https://192.168.50.10:8443"),
        ("https://[::1]:8443/", "https://[::1]:8443"),
        ("http://localhost:8099", "http://localhost:8099"),
        ("http://127.0.0.1:8099/", "http://127.0.0.1:8099"),
    ],
)
def test_valid_slicer_server_url_is_normalized(supplied: str, expected: str) -> None:
    assert settings.normalize_slicer_base_url(supplied) == expected


@pytest.mark.parametrize(
    "supplied",
    [
        None, "", "slicer.example.org", "ftp://example.org",
        "http://slicer.internal:8099", "http://192.168.0.1:8099",
        "https://example.org/path", "https://example.org/?token=sensitive",
        "https://user:pass@example.org", "https://example.org/#password",
        "https://0.0.0.0:8443", "https://169.254.169.254",
        "https://[::]:8443", "https://example.org:0",
        "https://example.org:65536", "https://example.org\n",
        "https://bad_host.local", "https://example.org\\secret",
    ],
)
def test_malformed_or_insecure_slicer_url_is_rejected(supplied: object) -> None:
    with pytest.raises(settings.SlicerConnectionSettingsError):
        settings.normalize_slicer_base_url(supplied)


def test_valid_api_secret_retains_exact_bytes_in_backend_memory() -> None:
    secret = "example-private-key-" + "S" * 48
    assert settings.validate_slicer_api_secret(secret) == secret


@pytest.mark.parametrize("secret", [None, "", " ", "short", "a" * 31, "a" * 257, "a" * 50 + "\r", "ü" * 40])
def test_invalid_api_secret_is_rejected_without_echoing_it(secret: object) -> None:
    with pytest.raises(settings.SlicerConnectionSettingsError) as exc:
        settings.validate_slicer_api_secret(secret)
    if isinstance(secret, str) and len(secret.strip()) > 4:
        assert secret not in str(exc.value)
