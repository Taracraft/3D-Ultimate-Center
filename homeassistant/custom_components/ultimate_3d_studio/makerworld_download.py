"""MakerWorld print-profile resolution through the Bambu cloud API."""
from __future__ import annotations

from io import BytesIO
import re
from typing import Any, Iterable
from urllib.parse import urlparse
import zipfile

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .makerworld_runtime import MakerWorldError, MakerWorldRuntime

_MAX_DOWNLOAD_BYTES = 500_000_000
_INSTANCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
_MODEL_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{5,100}$")


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            if isinstance(child, (dict, list)):
                yield from _walk(child)


def _text(value: Any, limit: int = 200) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _model_id_from_payload(payload: Any, design_id: str = "") -> str:
    # Only a selected design root owns a model ID; recommendations never do.
    if not design_id:
        return ""
    from .makerworld_detail import _raw_design
    try:
        raw = _raw_design(payload, design_id)
    except MakerWorldError:
        return ""
    values = {str(raw[key]).strip() for key in
              ("modelId", "model_id", "modelID", "modelIdentifier",
               "model_identifier", "designModelId", "design_model_id")
              if key in raw and isinstance(raw[key], str)}
    return next(iter(values)) if len(values) == 1 and _MODEL_ID.fullmatch(next(iter(values))) else ""


def _instance_id_from_mapping(mapping: dict[str, Any]) -> str:
    if not any(
        key in mapping
        for key in (
            "instanceId", "instance_id", "modelInstanceId", "model_instance_id",
            "profileId", "profile_id", "plates", "plateList", "isDefault",
            "profileName", "printerModel",
        )
    ):
        return ""
    for key in (
        "instanceId", "instance_id", "modelInstanceId", "model_instance_id",
        "profileId", "profile_id", "id",
    ):
        candidate = _text(mapping.get(key), 90)
        if _INSTANCE_ID.fullmatch(candidate):
            return candidate
    return ""


def remember_design_payload(payload: Any, design_id: str = "", *, runtime=None) -> int:
    """Store only selected-design bindings in the current runtime/account."""
    if not isinstance(runtime, MakerWorldRuntime):
        return 0
    runtime._account_scope()
    from .makerworld_detail import _raw_design, _instances
    # Revoke this design before parsing: failed refreshes cannot keep stale IDs.
    for key in list(runtime._profile_bindings):
        if key[0] == design_id:
            del runtime._profile_bindings[key]
    raw = _raw_design(payload, design_id)
    model_id = _model_id_from_payload(payload, design_id)
    if not model_id:
        return 0
    remembered = 0
    for item in _instances(payload, raw, design_id):
        instance_id, profile_id = item["id"], item["profile_id"]
        if _INSTANCE_ID.fullmatch(instance_id) and _INSTANCE_ID.fullmatch(profile_id):
            runtime._profile_bindings[(design_id, instance_id)] = (profile_id, model_id)
            remembered += 1
    while len(runtime._profile_bindings) > 512:
        runtime._profile_bindings.popitem(last=False)
    return remembered


def _allowed_host(hostname: str) -> bool:
    host = hostname.casefold().rstrip(".")
    return (
        host == "amazonaws.com"
        or host.endswith(".amazonaws.com")
        or host == "bblmw.com"
        or host.endswith(".bblmw.com")
        or host == "bambulab.com"
        or host.endswith(".bambulab.com")
        or host == "bambulab.cn"
        or host.endswith(".bambulab.cn")
    )


def _download_url_from_payload(payload: Any) -> str:
    preferred = (
        "url", "downloadUrl", "download_url", "fileUrl", "file_url",
        "signedUrl", "signed_url", "presignedUrl", "presigned_url",
    )
    candidates: list[str] = []
    for mapping in _walk(payload):
        for key in preferred:
            candidate = _text(mapping.get(key), 10_000)
            if candidate.startswith("https://"):
                candidates.append(candidate)
    for candidate in candidates:
        parsed = urlparse(candidate)
        if parsed.scheme == "https" and parsed.hostname and _allowed_host(parsed.hostname):
            return candidate
    return ""


async def _async_fetch_3mf(runtime: MakerWorldRuntime, signed_url: str) -> bytes:
    parsed = urlparse(signed_url)
    if parsed.scheme != "https" or not parsed.hostname or not _allowed_host(parsed.hostname):
        raise MakerWorldError("MakerWorld lieferte einen nicht freigegebenen Download-Host")
    session = async_get_clientsession(runtime.hass)
    payload = bytearray()
    async with session.get(
        URL(signed_url, encoded=True),
        headers={
            "Accept": "application/octet-stream,application/zip,*/*",
            "User-Agent": "Ultimate-3D-Studio/1.0",
        },
        allow_redirects=False,
        timeout=180,
    ) as response:
        if 300 <= response.status < 400:
            raise MakerWorldError("Signierter MakerWorld-Download wurde unerwartet umgeleitet")
        if response.status >= 400:
            raise MakerWorldError(
                f"Signierter MakerWorld-Download antwortete mit HTTP {response.status}"
            )
        async for chunk in response.content.iter_chunked(256 * 1024):
            payload.extend(chunk)
            if len(payload) > _MAX_DOWNLOAD_BYTES:
                raise MakerWorldError("MakerWorld-3MF überschreitet 500 MB")
    result = bytes(payload)
    if len(result) < 4 or not result.startswith(b"PK"):
        raise MakerWorldError("MakerWorld lieferte keine gültige 3MF-Datei")
    try:
        with zipfile.ZipFile(BytesIO(result)) as archive:
            if not archive.namelist():
                raise MakerWorldError("MakerWorld-3MF enthält keine Dateien")
    except zipfile.BadZipFile as exc:
        raise MakerWorldError("MakerWorld lieferte ein beschädigtes 3MF-Archiv") from exc
    return result


async def async_download_instance(runtime: MakerWorldRuntime, instance_id: str) -> bytes:
    """Use the same signed transfer contract for cached legacy view callers."""
    if not isinstance(instance_id, str) or not _INSTANCE_ID.fullmatch(instance_id):
        raise ValueError("Ungültige MakerWorld-Druckprofil-ID")
    runtime._account_scope()
    bindings = [(design, profile, model) for (design, instance), (profile, model)
                in runtime._profile_bindings.items() if instance == instance_id]
    if len(bindings) != 1:
        raise MakerWorldError(
            "MakerWorld-Druckprofil wurde nicht aus den Modelldetails aufgelöst. "
            "Modelldetails erneut öffnen und das gewünschte Profil auswählen."
        )
    design_id, profile_id, model_id = bindings[0]
    return await runtime.async_download_instance(
        instance_id, design_id=design_id, profile_id=profile_id, model_id=model_id,
    )
