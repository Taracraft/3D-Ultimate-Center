"""Server-side settings validation for the independently installed native slicer.

This module has no Home Assistant dependency and never logs or serializes secrets.
"""
from __future__ import annotations

from ipaddress import ip_address
import re
from urllib.parse import urlsplit


class SlicerConnectionSettingsError(ValueError):
    """A URL or credential is not acceptable for a backend slicer connection."""


_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def normalize_slicer_base_url(value: object) -> str:
    """Accept HTTPS hosts or temporary loopback HTTP, never userinfo or URL data."""
    if not isinstance(value, str):
        raise SlicerConnectionSettingsError("invalid_slicer_url")
    if any(character in value for character in "\r\n\t\\"):
        raise SlicerConnectionSettingsError("invalid_slicer_url")
    raw = value.strip()
    if not raw or len(raw) > 2048:
        raise SlicerConnectionSettingsError("invalid_slicer_url")
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise SlicerConnectionSettingsError("invalid_slicer_url") from exc

    if (
        parsed.scheme not in {"http", "https"}
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or port == 0
    ):
        raise SlicerConnectionSettingsError("invalid_slicer_url")

    name = hostname.casefold().rstrip(".")
    try:
        numeric = ip_address(name)
    except ValueError:
        if not all(_HOST_LABEL.fullmatch(label) for label in name.split(".")):
            raise SlicerConnectionSettingsError("invalid_slicer_url") from None
        is_loopback = name == "localhost"
    else:
        if numeric.is_unspecified or numeric.is_multicast or numeric.is_link_local:
            raise SlicerConnectionSettingsError("invalid_slicer_url")
        is_loopback = numeric.is_loopback

    if parsed.scheme == "http" and not is_loopback:
        raise SlicerConnectionSettingsError("slicer_https_required")

    formatted_host = f"[{name}]" if ":" in name else name
    port_fragment = f":{port}" if port is not None else ""
    return f"{parsed.scheme}://{formatted_host}{port_fragment}"


def validate_slicer_api_secret(value: object) -> str:
    """Require printable, high-entropy-length header data without exposing its value."""
    if (
        not isinstance(value, str)
        or not 32 <= len(value) <= 256
        or any(ord(character) < 33 or ord(character) > 126 for character in value)
    ):
        raise SlicerConnectionSettingsError("invalid_slicer_secret")
    return value
