"""One bounded download path for the explicitly selected MakerWorld profile.

A rejected cloud login is never retried through a different download endpoint.
Signed storage URLs are used verbatim, without forwarding account credentials.
"""
from __future__ import annotations

import asyncio
from io import BytesIO
import json
from pathlib import PurePosixPath
import re
import stat
from urllib.parse import quote, urlsplit
import zipfile
import zlib
import lzma

from aiohttp import ClientError, ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .makerworld_runtime import MakerWorldError

MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 500_000_000
MAX_ARCHIVE_ENTRIES = 10_000
MAX_EXPANDED_BYTES = 2 * 1024**3
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,90}\Z")
MODEL_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{5,119}\Z")
SIGNED_HOSTS = frozenset({"makerworld.bblmw.com", "public-cdn.bblmw.com"})


class MakerWorldTransferError(MakerWorldError):
    """Sanitized, classified error; raw response bodies/URLs are never exposed."""

    def __init__(self, code: str, message: str, *, upstream_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.upstream_status = upstream_status


def check_status(status: int, *, storage: bool = False) -> None:
    if 200 <= status < 300:
        return
    if status == 401 and not storage:
        code = "makerworld_account_unauthorized"
        message = ("Die Bambu-Anmeldung wurde beim Druckprofil-Download nicht akzeptiert (HTTP 401). "
                   "Bitte den Bambu-Kontozugang in der Studio-Integration erneut verbinden und danach "
                   "das gewählte Profil nochmals importieren. Es wurde kein Ersatzprofil geladen.")
    elif status in {401, 403} and storage:
        code = "makerworld_signed_download_denied"
        message = (f"Der signierte 3MF-Download wurde abgewiesen (HTTP {status}); "
                   "die Freigabe kann abgelaufen sein. Bitte den Import erneut bewusst anstoßen.")
    elif status == 403:
        code = "makerworld_profile_forbidden"
        message = "Der Bambu-Kontozugang darf dieses Druckprofil nicht herunterladen (HTTP 403)."
    elif status == 404:
        code = "makerworld_profile_not_found"
        message = "Das gewählte MakerWorld-Druckprofil oder seine Datei ist nicht verfügbar (HTTP 404)."
    elif status == 429:
        code = "makerworld_rate_limited"
        message = "MakerWorld begrenzt derzeit die Anfragen (HTTP 429). Bitte später erneut versuchen."
    elif 300 <= status < 400:
        code = "makerworld_unexpected_redirect"
        message = "MakerWorld hat den Download unerwartet umgeleitet. Die Weiterleitung wurde nicht verfolgt."
    else:
        code = "makerworld_upstream_error"
        message = f"MakerWorld konnte das gewählte Druckprofil nicht liefern (HTTP {status})."
    raise MakerWorldTransferError(code, message, upstream_status=status)


async def read_bounded(response, limit: int) -> bytes:
    if response.content_length is not None and response.content_length > limit:
        raise MakerWorldTransferError("makerworld_response_too_large", "Die MakerWorld-Antwort überschreitet die zulässige Größe.")
    result = bytearray()
    async for chunk in response.content.iter_chunked(256 * 1024):
        if len(result) + len(chunk) > limit:
            raise MakerWorldTransferError("makerworld_response_too_large", "Die MakerWorld-Antwort überschreitet die zulässige Größe.")
        result.extend(chunk)
    return bytes(result)


def signed_url(payload: object, depth: int = 0) -> str:
    # Only explicit manifest/file fields own URLs; media is never a download.
    candidates: set[str] = set()
    nodes = 0
    def collect(value, level):
        nonlocal nodes
        nodes += 1
        if level > 6 or nodes > 64:
            raise MakerWorldTransferError("makerworld_manifest_invalid", "Das Druckprofilmanifest ist zu komplex.")
        if isinstance(value, str):
            if value.startswith("https://"):
                candidates.add(value)
            return
        if not isinstance(value, dict):
            return
        for key in ("url", "downloadUrl", "download_url", "signedUrl", "signed_url",
                    "fileUrl", "file_url", "presignedUrl", "presigned_url"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith("https://"):
                candidates.add(candidate)
        for key in ("data", "result", "profile", "file"):
            if key in value:
                collect(value[key], level + 1)
    collect(payload, depth)
    if len(candidates) > 1:
        raise MakerWorldTransferError("makerworld_manifest_ambiguous", "MakerWorld lieferte mehrere widerspruechliche Downloadadressen. Der Import wurde angehalten.")
    return next(iter(candidates)) if candidates else ""


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def validate_signed_url(value: str) -> URL:
    try:
        if not value or len(value) > 16_384 or any(ord(c) <= 32 or ord(c) == 127 for c in value):
            raise ValueError("invalid URL")
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        if (parsed.scheme != "https" or parsed.username is not None or parsed.password is not None
                or parsed.port not in {None, 443} or parsed.fragment or "\\" in value
                or not (host in SIGNED_HOSTS or host.endswith(".amazonaws.com"))):
            raise ValueError("unapproved URL")
        return URL(value, encoded=True)
    except (ValueError, TypeError) as exc:
        raise MakerWorldTransferError("makerworld_download_url_invalid", "MakerWorld lieferte keine freigegebene signierte Download-URL.") from exc


def validate_3mf(payload: bytes) -> bytes:
    """Validate the container before handoff; do not rewrite geometry or metadata."""
    try:
        if not isinstance(payload, bytes) or len(payload) > MAX_DOWNLOAD_BYTES or not payload.startswith(b"PK\x03\x04"):
            raise ValueError("not a ZIP file")
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ARCHIVE_ENTRIES:
                raise ValueError("entry limit")
            names: set[str] = set()
            expanded = 0
            model_present = False
            for entry in entries:
                name = entry.filename
                parts = PurePosixPath(name).parts
                if (not name or name.startswith("/") or "\\" in name or ":" in name
                        or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))
                        or any(ord(c) < 32 for c in name) or entry.flag_bits & 1
                        or entry.orig_filename != name or name.casefold() in names
                        or stat.S_ISLNK(entry.external_attr >> 16)):
                    raise ValueError("unsafe or duplicate archive member")
                names.add(name.casefold())
                expanded += entry.file_size
                if expanded > MAX_EXPANDED_BYTES:
                    raise ValueError("expanded size limit")
                if len(parts) >= 2 and parts[0].casefold() == "3d" and name.casefold().endswith(".model") and entry.file_size > 0:
                    model_present = True
            if "[content_types].xml" not in names or not model_present:
                raise ValueError("not a model 3MF")
            # Validate every member through a bounded stream. Reading to EOF
            # checks local headers, decompression and CRC, without extraction
            # or retaining another expanded archive in memory.
            actual_total = 0
            for entry in entries:
                actual_member = 0
                with archive.open(entry, "r") as member:
                    while True:
                        chunk = member.read(64 * 1024)
                        if not chunk:
                            break
                        actual_member += len(chunk)
                        actual_total += len(chunk)
                        if actual_member > entry.file_size or actual_total > MAX_EXPANDED_BYTES:
                            raise ValueError("actual expanded size limit")
                if actual_member != entry.file_size:
                    raise ValueError("archive member size mismatch")

    except (zipfile.BadZipFile, ValueError, OSError, EOFError, RuntimeError, NotImplementedError, zlib.error, lzma.LZMAError) as exc:
        raise MakerWorldTransferError("makerworld_invalid_3mf", "MakerWorld lieferte kein verwendbares 3MF-Modellarchiv. Das Projekt wurde nicht ersetzt.") from exc
    return payload


def validate_manifest_identity(payload, profile_id, model_id, depth=0, *, design_id="") -> None:
    if depth > 6:
        raise MakerWorldTransferError("makerworld_manifest_invalid", "Das Druckprofilmanifest ist zu tief verschachtelt.")
    if not isinstance(payload, dict):
        return
    identities = [(("profile_id", "profileId"), profile_id), (("model_id", "modelId"), model_id)]
    if design_id:
        identities.append((("design_id", "designId"), design_id))
    for keys, expected in identities:
        if any(key in payload and str(payload[key]) != expected for key in keys):
            raise MakerWorldTransferError("makerworld_profile_mismatch", "MakerWorld lieferte eine widerspruechliche Profilzuordnung. Der Import wurde angehalten.")
    for key in ("data", "result", "profile", "file"):
        if key in payload:
            validate_manifest_identity(payload[key], profile_id, model_id, depth + 1, design_id=design_id)


async def download_signed_profile(runtime, account, design_id: str, profile_id: str, model_id: str) -> bytes:
    if (not isinstance(profile_id, str) or not IDENTIFIER.fullmatch(profile_id)
            or not isinstance(design_id, str) or (design_id and not re.fullmatch(r"\d{1,30}", design_id))):
        raise MakerWorldTransferError("makerworld_profile_identity_invalid", "Ungültige MakerWorld-Druckprofilzuordnung.")
    try:
        resolved = await runtime._resolve_model_id(design_id, model_id)
        if not isinstance(resolved, str) or not MODEL_IDENTIFIER.fullmatch(resolved):
            raise MakerWorldTransferError("makerworld_model_identity_invalid", "Die interne MakerWorld-Modell-ID fehlt oder ist ungültig. Bitte die Modelldetails erneut öffnen.")
        session = async_get_clientsession(runtime.hass)
        async with session.get(
            f"{account.api_base}/iot-service/api/user/profile/{quote(profile_id, safe='')}",
            params={"model_id": resolved}, headers=runtime._headers(account),
            allow_redirects=False, timeout=ClientTimeout(total=45),
        ) as response:
            check_status(response.status)
            raw = await read_bounded(response, MAX_MANIFEST_BYTES)
        try:
            manifest = json.loads(raw, object_pairs_hook=_unique_json_object)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise MakerWorldTransferError("makerworld_manifest_invalid", "MakerWorld lieferte kein gültiges Druckprofilmanifest.") from exc
        validate_manifest_identity(manifest, profile_id, resolved, design_id=design_id)
        runtime._check_account(account)
        url = validate_signed_url(signed_url(manifest))
        async with session.get(
            url, headers={"Accept": "application/octet-stream,application/zip,*/*",
                          "User-Agent": runtime._headers(account)["User-Agent"]},
            allow_redirects=False, timeout=ClientTimeout(total=180),
        ) as response:
            check_status(response.status, storage=True)
            payload = await read_bounded(response, MAX_DOWNLOAD_BYTES)
        runtime._check_account(account)
        result = await runtime.hass.async_add_executor_job(validate_3mf, payload)
        runtime._check_account(account)
        return result
    except asyncio.CancelledError:
        raise
    except MakerWorldTransferError as exc:
        if exc.code == "makerworld_account_unauthorized":
            runtime._check_account(account)
            exc.config_entry_id = account.entry_id
        raise
    except TimeoutError as exc:
        raise MakerWorldTransferError("makerworld_download_timeout", "Der MakerWorld-Download hat sein Zeitlimit überschritten. Kein Ersatzprofil wurde geladen.") from exc
    except ClientError as exc:
        raise MakerWorldTransferError("makerworld_download_connection", "Die Verbindung zu MakerWorld wurde unterbrochen. Kein Ersatzprofil wurde geladen.") from exc
