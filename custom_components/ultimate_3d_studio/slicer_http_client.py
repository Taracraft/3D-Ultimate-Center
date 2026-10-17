"""Authenticated, redirect-resistant backend transport to the independent slicer.

The API secret is loaded from Home Assistant ConfigEntry options at request time.
Only the backend sees it. The browser never contacts the slicer directly.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from math import isfinite
import json
import hmac
from secrets import token_bytes
from typing import Any
from urllib.parse import urlsplit

from aiohttp import ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_SLICER_API_SECRET,
    CONF_SLICER_BASE_URL,
    CONF_SLICER_ENABLED,
    DOMAIN,
)
from .slicer_connection_settings import (
    SlicerConnectionSettingsError,
    normalize_slicer_base_url,
    validate_slicer_api_secret,
)
from .slicer_native_contract import (
    SlicerServerConfigurationError,
    SlicerServerError,
)

# Jobs are submitted with a 1 MiB body and the server lists at most 100 jobs.
# Leave room for result/progress metadata without allowing an unbounded response.
_CACHE_SCOPE_KEY = token_bytes(32)

MAX_JSON_RESPONSE_BYTES = 128 * 1024 * 1024
MAX_TEXT_RESPONSE_BYTES = 64 * 1024
# Match the existing Bambu artifact acceptance limit, before allocating its body.
MAX_ARTIFACT_RESPONSE_BYTES = 600_000_000


class BoundedSlicerResponse:
    """The response operations used by the router, with streaming size limits."""

    def __init__(self, response: Any) -> None:
        self._response = response
        self._body: bytes | None = None
        self._rejected = False

    @property
    def status(self) -> int:
        return self._response.status

    def _reject_size(self) -> None:
        self._rejected = True
        self._response.close()
        raise SlicerServerError("Slicer-Serverantwort ueberschreitet die zulaessige Groesse")

    async def _read(self, limit: int) -> bytes:
        if self._rejected:
            self._reject_size()
        if self._body is not None:
            if len(self._body) > limit:
                self._reject_size()
            return self._body
        declared = self._response.content_length
        if declared is not None and declared > limit:
            self._reject_size()
        body = bytearray()
        while True:
            # Read at most one excess byte, even with missing/false Content-Length.
            # aiohttp supplies decompressed bytes, so this also bounds gzip bodies.
            chunk = await self._response.content.read(min(64 * 1024, limit + 1 - len(body)))
            if not chunk:
                break
            if len(body) + len(chunk) > limit:
                self._reject_size()
            body.extend(chunk)
        self._body = bytes(body)
        return self._body

    async def read(self) -> bytes:
        return await self._read(MAX_ARTIFACT_RESPONSE_BYTES)

    async def text(self) -> str:
        return (await self._read(MAX_TEXT_RESPONSE_BYTES)).decode("utf-8", errors="replace")

    async def json(self, *, content_type: str | None = None) -> Any:
        # Existing router calls explicitly accept JSON regardless of MIME type.
        raw = await self._read(MAX_JSON_RESPONSE_BYTES)
        try:
            return json.loads(raw)
        except (ValueError, UnicodeError, RecursionError):
            raise SlicerServerError("Slicer-Server lieferte keine gueltige JSON-Antwort") from None


class AuthenticatedSlicerSession:
    """A restricted aiohttp-compatible session for the configured slicer only."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._session = async_get_clientsession(hass)

    def _connection(self) -> tuple[str, str]:
        entries = self._hass.config_entries.async_entries(DOMAIN)
        if len(entries) != 1:
            raise SlicerServerConfigurationError(
                "Slicer-Verbindung muss in der Studio-Integration konfiguriert werden"
            )
        entry = entries[0]
        settings = {**entry.data, **entry.options}
        if not bool(settings.get(CONF_SLICER_ENABLED, False)):
            raise SlicerServerConfigurationError(
                "Slicer-Server ist in den Studio-Einstellungen nicht aktiviert"
            )
        try:
            base_url = normalize_slicer_base_url(
                settings.get(CONF_SLICER_BASE_URL, "")
            )
            secret = validate_slicer_api_secret(
                settings.get(CONF_SLICER_API_SECRET, "")
            )
        except SlicerConnectionSettingsError as error:
            # Error messages contain only stable validation codes, never values.
            raise SlicerServerConfigurationError(str(error)) from None
        return base_url, secret

    @property
    def cache_scope(self) -> bytes:
        """Validate current settings and identify this HA connection without raw secrets."""
        base_url, secret = self._connection()
        identity = f"{id(self._hass)}\0{base_url}\0{secret}".encode("utf-8")
        return hmac.digest(_CACHE_SCOPE_KEY, identity, "sha256")

    @property
    def endpoint(self) -> str:
        return self._connection()[0]

    @asynccontextmanager
    async def _request(self, method: str, url: str, **kwargs: Any):
        base_url, secret = self._connection()
        if not isinstance(url, str) or not url.startswith(base_url + "/"):
            raise SlicerServerConfigurationError("Slicer-Anfrage hat ein fremdes Ziel")
        resolved = urlsplit(url)
        origin = urlsplit(base_url)
        if (
            resolved.scheme != origin.scheme
            or resolved.netloc != origin.netloc
            or resolved.username is not None
            or resolved.password is not None
            or resolved.fragment
        ):
            raise SlicerServerConfigurationError("Slicer-Anfrage hat ein fremdes Ziel")

        incoming = kwargs.pop("headers", None)
        headers = dict(incoming or {})
        if any(
            str(name).lower() in {"authorization", "x-api-token"}
            for name in headers
        ):
            raise SlicerServerConfigurationError(
                "Slicer-Authentifizierungsheader dürfen nicht überschrieben werden"
            )
        if "ssl" in kwargs or "allow_redirects" in kwargs:
            raise SlicerServerConfigurationError(
                "Slicer-Transportoptionen dürfen nicht überschrieben werden"
            )
        timeout = kwargs.pop(
            "timeout", ClientTimeout(total=30, connect=10, sock_read=30)
        )
        total = timeout.total if isinstance(timeout, ClientTimeout) else timeout
        if (
            type(total) not in (int, float)
            or total <= 0
            or (isinstance(total, float) and not isfinite(total))
        ):
            raise SlicerServerConfigurationError(
                "Slicer-Anfragen erfordern ein endliches positives Zeitlimit"
            )
        # Preserve explicit per-operation budgets, especially large transfers.
        kwargs["timeout"] = (
            timeout if isinstance(timeout, ClientTimeout) else ClientTimeout(total=total)
        )
        headers["Authorization"] = "Bearer " + secret
        # Do not forward this bearer secret to a server-provided redirect.
        async with self._session.request(
            method,
            url,
            headers=headers,
            allow_redirects=False,
            ssl=True,
            **kwargs,
        ) as response:
            if 300 <= response.status < 400:
                raise SlicerServerError("Slicer-Serverredirect aus Sicherheitsgründen abgelehnt")
            yield BoundedSlicerResponse(response)

    def get(self, url: str, **kwargs: Any):
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any):
        return self._request("POST", url, **kwargs)

    def delete(self, url: str, **kwargs: Any):
        return self._request("DELETE", url, **kwargs)
