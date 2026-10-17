"""Read-only, backend-only authenticated connection test for the native slicer.

No printer commands, uploads, job creation, or secret-bearing redirects.
"""
from __future__ import annotations

import asyncio
import json
import re
import ssl

from aiohttp import ClientError, ClientTimeout

from .slicer_connection_settings import (
    SlicerConnectionSettingsError,
    normalize_slicer_base_url,
    validate_slicer_api_secret,
)

MAX_RESPONSE_BYTES = 16_384
VERSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,59}\Z")


class SlicerConnectionProbeError(ValueError):
    """Only stable error codes; never include a URL, credential or response body."""


async def async_probe_slicer_connection(
    session, server_url: object, api_secret: object,
) -> dict[str, object]:
    """Probe only the authenticated read-only /info.json endpoint."""
    try:
        endpoint = normalize_slicer_base_url(server_url)
        secret = validate_slicer_api_secret(api_secret)
    except SlicerConnectionSettingsError as exc:
        raise SlicerConnectionProbeError(str(exc)) from None

    try:
        async with session.get(
            endpoint + "/info.json",
            headers={"Authorization": "Bearer " + secret, "Accept": "application/json"},
            allow_redirects=False,
            ssl=True,
            timeout=ClientTimeout(total=8, connect=4, sock_read=4),
        ) as response:
            if response.status in (401, 403):
                raise SlicerConnectionProbeError("slicer_auth_required")
            if response.status in (404, 405, 410, 501):
                raise SlicerConnectionProbeError("slicer_incompatible")
            if 300 <= response.status < 400:
                raise SlicerConnectionProbeError("slicer_redirect_refused")
            if response.status != 200:
                raise SlicerConnectionProbeError("slicer_unavailable")
            raw = await response.content.read(MAX_RESPONSE_BYTES + 1)
    except SlicerConnectionProbeError:
        raise
    except (ssl.SSLError, ClientError) as error:
        if isinstance(error, ssl.SSLError) or "ssl" in type(error).__name__.casefold() or "certificate" in type(error).__name__.casefold():
            raise SlicerConnectionProbeError("slicer_certificate_error") from None
        raise SlicerConnectionProbeError("slicer_unavailable") from None
    except (asyncio.TimeoutError, TimeoutError, OSError):
        raise SlicerConnectionProbeError("slicer_unavailable") from None

    if len(raw) > MAX_RESPONSE_BYTES:
        raise SlicerConnectionProbeError("slicer_incompatible")
    try:
        info = json.loads(raw)
    except (UnicodeDecodeError, ValueError, TypeError):
        raise SlicerConnectionProbeError("slicer_incompatible") from None
    if not isinstance(info, dict):
        raise SlicerConnectionProbeError("slicer_incompatible")
    version = info.get("version")
    api = info.get("api_version")
    if (
        not isinstance(version, str)
        or not VERSION_PATTERN.fullmatch(version)
        or type(api) is not int
        or api < 2
        or not isinstance(info.get("capabilities"), dict)
    ):
        raise SlicerConnectionProbeError("slicer_incompatible")
    return {"status": "ready", "server_version": version, "api_protocol": api}
