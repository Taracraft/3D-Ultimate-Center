"""Authenticated MakerWorld browser and model-transfer runtime for Studio."""
from __future__ import annotations

from contextvars import ContextVar
from collections import OrderedDict
from hashlib import sha256
from copy import deepcopy
from dataclasses import dataclass
import logging
import json
import re
from typing import Any, Iterable
from urllib.parse import quote, urlparse

from aiohttp import ClientError, ClientResponse, ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_REGION,
    DOMAIN,
    REGION_CHINA,
    REGION_GLOBAL,
    VERSION,
)
from .makerworld_search_pager import MakerWorldSearchPager

_LOGGER = logging.getLogger(__name__)
_API_GLOBAL = "https://api.bambulab.com/v1"
_API_CHINA = "https://api.bambulab.cn/v1"
_WEB_API_GLOBAL = "https://makerworld.com/api/v1"
_MAX_DOWNLOAD_BYTES = 500_000_000
_MAX_JSON_BYTES = 15_000_000
_MODEL_ID = re.compile(r"^\d{1,30}$")
_INSTANCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,90}$")
_ALLOWED_SIGNED_HOSTS = {"makerworld.bblmw.com", "public-cdn.bblmw.com"}


class MakerWorldError(RuntimeError):
    """MakerWorld request or response error."""


class MakerWorldRequestError(MakerWorldError):
    """Classified account/data request error with no raw upstream content."""

    def __init__(self, code: str, message: str, upstream_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.upstream_status = upstream_status


@dataclass(frozen=True)
class _AccountContext:
    credential: str
    region: str
    entry_id: str = ""

    @property
    def api_base(self) -> str:
        return _API_CHINA if self.region == REGION_CHINA else _API_GLOBAL


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _string(value: Any, limit: int = 1000) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _integer(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, "", [], {}):
            return mapping[key]
    return default


def _nested_name(value: Any) -> str:
    if isinstance(value, str):
        return _string(value, 240)
    if not isinstance(value, dict):
        return ""
    return _string(
        _first(
            value,
            (
                "name",
                "nickname",
                "userName",
                "username",
                "displayName",
                "designerName",
                "creatorName",
                "title",
            ),
        ),
        240,
    )


def _image_from(value: Any) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate if candidate.startswith("https://") else ""
    if isinstance(value, list):
        for item in value:
            candidate = _image_from(item)
            if candidate:
                return candidate
        return ""
    if not isinstance(value, dict):
        return ""
    for key in (
        "url",
        "imageUrl",
        "image_url",
        "coverUrl",
        "cover_url",
        "thumbnailUrl",
        "thumbnail_url",
        "downloadUrl",
        "download_url",
        "source",
        "src",
    ):
        candidate = _image_from(value.get(key))
        if candidate:
            return candidate
    return ""


def _images(mapping: dict[str, Any]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for key in (
        "images",
        "pictures",
        "designPictures",
        "design_pictures",
        "covers",
        "imageList",
        "image_list",
        "thumbnails",
        "renderImages",
        "render_images",
    ):
        for item in _list(mapping.get(key)):
            candidate = _image_from(item)
            if candidate and candidate not in seen:
                seen.add(candidate)
                values.append(candidate)
    for key in (
        "cover",
        "coverUrl",
        "cover_url",
        "thumbnail",
        "thumbnailUrl",
        "thumbnail_url",
        "image",
        "imageUrl",
        "image_url",
        "designPicture",
        "design_picture",
    ):
        candidate = _image_from(mapping.get(key))
        if candidate and candidate not in seen:
            seen.add(candidate)
            values.insert(0, candidate)
    return values[:40]


def _tags(mapping: dict[str, Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    raw = _first(mapping, ("tags", "tagList", "tag_list", "categories"), [])
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    for item in _list(raw):
        value = _nested_name(item) if isinstance(item, dict) else _string(item, 80)
        if value and value.casefold() not in seen:
            seen.add(value.casefold())
            result.append(value)
    return result[:30]


def _design_id(mapping: dict[str, Any]) -> str:
    value = _first(mapping, ("designId", "design_id", "modelId", "model_id", "id"))
    candidate = _string(value, 30)
    return candidate if _MODEL_ID.fullmatch(candidate) else ""


def _title(mapping: dict[str, Any], fallback: str = "MakerWorld-Modell") -> str:
    return _string(
        _first(
            mapping,
            (
                "title",
                "name",
                "designName",
                "design_name",
                "modelName",
                "model_name",
                "instanceName",
                "instance_name",
            ),
        ),
        300,
    ) or fallback


def _creator(mapping: dict[str, Any]) -> str:
    for key in ("creator", "designer", "author", "user", "owner", "account"):
        name = _nested_name(mapping.get(key))
        if name:
            return name
    return _string(
        _first(
            mapping,
            (
                "creatorName",
                "creator_name",
                "designerName",
                "designer_name",
                "authorName",
                "author_name",
                "userName",
                "user_name",
            ),
        ),
        240,
    ) or "MakerWorld"


def _stats(mapping: dict[str, Any]) -> dict[str, int]:
    return {
        "likes": _integer(_first(mapping, ("likeCount", "like_count", "likes", "likedCount"))),
        "downloads": _integer(_first(mapping, ("downloadCount", "download_count", "downloads"))),
        "comments": _integer(_first(mapping, ("commentCount", "comment_count", "comments"))),
        "collects": _integer(
            _first(mapping, ("collectCount", "collect_count", "favoriteCount", "favorite_count"))
        ),
        "prints": _integer(_first(mapping, ("printCount", "print_count", "prints"))),
    }


def _looks_like_design(mapping: dict[str, Any]) -> bool:
    design_id = _design_id(mapping)
    if not design_id:
        return False
    has_title = bool(_first(mapping, ("title", "name", "designName", "design_name")))
    has_signal = any(
        key in mapping
        for key in (
            "designId",
            "design_id",
            "designPictures",
            "design_pictures",
            "creator",
            "downloadCount",
            "likeCount",
            "instances",
            "modelInstances",
        )
    )
    return has_title and has_signal


def _iter_mappings(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _iter_mappings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_mappings(child)


def _normalize_design(mapping: dict[str, Any]) -> dict[str, Any] | None:
    design_id = _design_id(mapping)
    if not design_id:
        return None
    images = _images(mapping)
    return {
        "id": design_id,
        "title": _title(mapping, f"MakerWorld Modell {design_id}"),
        "description": _string(
            _first(
                mapping,
                (
                    "description",
                    "summary",
                    "designDescription",
                    "design_description",
                    "content",
                    "introduction",
                ),
            ),
            6000,
        ),
        "creator": _creator(mapping),
        "thumbnail_url": images[0] if images else None,
        "images": images,
        "tags": _tags(mapping),
        "stats": _stats(mapping),
        "model_url": f"https://makerworld.com/de/models/{design_id}",
        "license": _string(_first(mapping, ("license", "licenseName", "license_name")), 200),
        "published_at": _string(
            _first(
                mapping,
                ("publishTime", "publish_time", "createdAt", "created_at", "createTime", "create_time"),
            ),
            100,
        ),
    }


def _designs_from_payload(payload: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for mapping in _iter_mappings(payload):
        if not _looks_like_design(mapping):
            continue
        normalized = _normalize_design(mapping)
        if normalized is None or normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        result.append(normalized)
    return result


def _safe_terms(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        term = _string(raw, 120).strip()
        folded = term.casefold()
        if term and folded not in seen:
            seen.add(folded)
            result.append(term)
    return result[:12]


def _signed_url(payload: Any) -> str:
    if isinstance(payload, str):
        return payload.strip() if payload.strip().startswith("https://") else ""
    if isinstance(payload, list):
        for item in payload:
            candidate = _signed_url(item)
            if candidate:
                return candidate
        return ""
    if isinstance(payload, dict):
        for key in ("url", "downloadUrl", "download_url", "signedUrl", "signed_url"):
            candidate = _signed_url(payload.get(key))
            if candidate:
                return candidate
        for key in ("data", "result", "profile", "file"):
            candidate = _signed_url(payload.get(key))
            if candidate:
                return candidate
    return ""


def _instance_id(mapping: dict[str, Any]) -> str:
    """Compatibility helper retained for established tests and callers."""
    candidate = _string(
        _first(
            mapping,
            (
                "instanceId",
                "instance_id",
                "modelInstanceId",
                "model_instance_id",
                "profileId",
                "profile_id",
                "id",
            ),
        ),
        90,
    )
    return candidate if _INSTANCE_ID.fullmatch(candidate) else ""


def _find_design_payload(payload: Any, design_id: str) -> dict[str, Any]:
    """Compatibility bridge to the dedicated detail normalizer."""
    from .makerworld_detail import _raw_design

    return _raw_design(payload, design_id)



def _instances_from_design(raw: dict[str, Any], design_id: str) -> list[dict[str, Any]]:
    """Compatibility bridge to the dedicated instance normalizer."""
    from .makerworld_detail import _instances

    return _instances(raw, raw, design_id)


def _pagination_has_more(payload: Any, offset: int, limit: int, count: int) -> bool:
    totals: list[int] = []
    explicit: list[bool] = []
    for mapping in _iter_mappings(payload):
        for key in ("total", "totalCount", "total_count", "hitCount", "hit_count", "resultCount", "result_count"):
            if key in mapping:
                value = _integer(mapping.get(key))
                if value > 0:
                    totals.append(value)
        for key in ("hasMore", "has_more", "more"):
            if key in mapping:
                explicit.append(_boolean(mapping.get(key)))
    if totals:
        return offset + count < max(totals)
    if explicit:
        return any(explicit)
    return count >= limit


class MakerWorldRuntime:
    """Browse MakerWorld and fetch downloadable print profiles."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._search_pager = MakerWorldSearchPager()
        self._cache_scope = ""
        self._request_account: ContextVar[_AccountContext | None] = ContextVar("makerworld_request_account", default=None)
        self._profile_bindings: OrderedDict[tuple[str, str], tuple[str, str]] = OrderedDict()

    def _clear_account_cache(self) -> None:
        self._search_pager = MakerWorldSearchPager()
        self._profile_bindings.clear()
        self._cache_scope = ""

    def _account_scope(self) -> _AccountContext:
        try:
            account = self._account()
        except MakerWorldError:
            self._clear_account_cache()
            raise
        fingerprint = sha256((account.entry_id + "\0" + account.region + "\0" + account.credential).encode()).hexdigest()
        if fingerprint != self._cache_scope:
            self._clear_account_cache()
            self._cache_scope = fingerprint
        return account

    def _check_account(self, expected: _AccountContext) -> None:
        try:
            current = self._account_scope()
        except MakerWorldError:
            current = None
        if current != expected:
            raise MakerWorldRequestError("makerworld_account_changed", "Der Kontozugang hat sich waehrend der Anfrage geaendert. Bitte erneut anfragen.")

    def _account(self) -> _AccountContext:
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            config = {**entry.data, **entry.options}
            credential = _string(config.get(CONF_CLOUD_ACCESS_TOKEN), 10000)
            if not credential:
                continue
            region = _string(config.get(CONF_CLOUD_REGION), 40) or REGION_GLOBAL
            if region not in {REGION_GLOBAL, REGION_CHINA}:
                raise MakerWorldRequestError(
                    "makerworld_region_invalid",
                    "Die konfigurierte Bambu-Kontoregion ist ungültig. Bitte die Studio-Konfiguration prüfen.",
                )
            return _AccountContext(credential=credential, region=region, entry_id=str(getattr(entry, "entry_id", "")))
        raise MakerWorldError(
            "Kein Bambu-Kontozugang in Studio verfügbar. Profil-Synchronisierung zuerst verbinden."
        )

    def _headers(self, account: _AccountContext, accept: str = "application/json") -> dict[str, str]:
        return {
            "Authorization": f"Bearer {account.credential}",
            "Accept": accept,
            "X-BBL-Client-Name": "Ultimate3DStudio",
            "X-BBL-Client-Type": "integration",
            "User-Agent": (
                f"Ultimate-3D-Studio/{VERSION} "
                "(+https://github.com/Taracraft/3D-Printer-Control-Center)"
            ),
        }

    async def _json(self, path: str, params: dict[str, Any]) -> Any:
        account = self._request_account.get() or self._account_scope()
        self._check_account(account)
        session = async_get_clientsession(self.hass)
        url = f"{account.api_base}/{path.lstrip('/')}"
        try:
            async with session.get(
                url,
                params=params,
                headers=self._headers(account),
                allow_redirects=False,
                timeout=ClientTimeout(total=35),
            ) as response:
                status = response.status
                if not 200 <= status < 300:
                    if status == 401:
                        code = "makerworld_account_unauthorized"
                        message = "Die Bambu-Anmeldung wurde nicht akzeptiert (HTTP 401). Bitte den Kontozugang in der Studio-Integration erneut verbinden."
                    elif status == 403:
                        code = "makerworld_account_forbidden"
                        message = "Der Bambu-Kontozugang darf diese MakerWorld-Daten nicht abrufen (HTTP 403)."
                    elif status == 429:
                        code = "makerworld_rate_limited"
                        message = "MakerWorld begrenzt derzeit die Anfragen (HTTP 429). Bitte später erneut versuchen."
                    elif 300 <= status < 400:
                        code = "makerworld_unexpected_redirect"
                        message = "MakerWorld hat die Anfrage unerwartet umgeleitet. Die Weiterleitung wurde nicht verfolgt."
                    else:
                        code = "makerworld_upstream_error"
                        message = f"MakerWorld antwortete mit HTTP {status}."
                    raise MakerWorldRequestError(code, message, status)
                if response.content_length is not None and response.content_length > _MAX_JSON_BYTES:
                    raise MakerWorldRequestError("makerworld_response_too_large", "Die MakerWorld-Antwort überschreitet die zulässige Größe.")
                raw = bytearray()
                async for chunk in response.content.iter_chunked(256 * 1024):
                    if len(raw) + len(chunk) > _MAX_JSON_BYTES:
                        raise MakerWorldRequestError("makerworld_response_too_large", "Die MakerWorld-Antwort überschreitet die zulässige Größe.")
                    raw.extend(chunk)
                try:
                    result = json.loads(raw)
                    self._check_account(account)
                    return result
                except (ValueError, UnicodeError, RecursionError) as exc:
                    raise MakerWorldRequestError("makerworld_json_invalid", "MakerWorld lieferte keine gültigen JSON-Daten.") from exc
        except TimeoutError as exc:
            raise MakerWorldRequestError("makerworld_request_timeout", "Die MakerWorld-Anfrage hat ihr Zeitlimit überschritten.") from exc
        except ClientError as exc:
            raise MakerWorldRequestError("makerworld_request_connection", "Die Verbindung zu MakerWorld wurde unterbrochen.") from exc

    async def _search_page(
        self,
        term: str,
        offset: int = 0,
        limit: int = 60,
    ) -> tuple[list[dict[str, Any]], str, bool]:
        safe_offset = max(0, int(offset))
        safe_limit = max(1, min(int(limit), 60))
        common = {"keyword": term, "offset": safe_offset, "limit": safe_limit}
        attempts = (
            ("search-service/searchlist", common),
            ("search-service/select/all", common),
            ("search-service/select/design2", {**common, "navKey": "Search"}),
        )
        errors: list[str] = []
        for path, params in attempts:
            try:
                payload = await self._json(path, params)
                items = _designs_from_payload(payload)
                if items:
                    return items, path, _pagination_has_more(
                        payload,
                        safe_offset,
                        safe_limit,
                        len(items),
                    )
                errors.append(f"{path}: keine Designs erkannt")
            except MakerWorldRequestError as exc:
                if exc.upstream_status not in {404, 405}:
                    raise
                errors.append(f"{path}: {exc}")
            except Exception as exc:
                errors.append(f"{path}: {exc}")
        if safe_offset > 0:
            return [], attempts[0][0], False
        raise MakerWorldError(
            f"MakerWorld-Suche für '{term}' lieferte keine verwertbaren Modelle. "
            + " | ".join(errors)
        )

    async def async_browse(
        self,
        query: str = "",
        nav_key: str = "Trending",
        offset: int = 0,
        limit: int = 24,
        terms: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        safe_offset = max(0, min(int(offset), 10_000))
        safe_limit = max(1, min(int(limit), 60))
        search_terms = _safe_terms([*(terms or []), query] if query else (terms or []))

        account = self._account_scope()
        if search_terms:
            pager = self._search_pager

            async def load_page(term, offset, limit):
                self._check_account(account)
                result = await self._search_page(term, offset, limit)
                self._check_account(account)
                return result

            page = await pager.page(
                search_terms,
                safe_offset,
                safe_limit,
                load_page,
            )
            self._check_account(account)
            return {
                "items": page.items,
                "query": " ".join(search_terms),
                "terms": search_terms,
                "nav_key": "Search",
                "offset": safe_offset,
                "limit": safe_limit,
                "source_endpoint": page.source_endpoint,
                "has_more": page.has_more,
                "known_count": page.known_count,
                "total_count": page.total_count,
            }

        key = _string(nav_key, 60) or "Trending"
        attempts = (
            (
                "search-service/select/design/nav",
                {"navKey": key, "offset": safe_offset, "limit": safe_limit},
            ),
            (
                "search-service/select/design2",
                {"navKey": key, "offset": safe_offset, "limit": safe_limit},
            ),
        )
        errors: list[str] = []
        for path, params in attempts:
            try:
                payload = await self._json(path, params)
                items = _designs_from_payload(payload)
                if items:
                    return {
                        "items": items[:safe_limit],
                        "query": "",
                        "terms": [],
                        "nav_key": key,
                        "offset": safe_offset,
                        "limit": safe_limit,
                        "source_endpoint": path,
                        "has_more": len(items) >= safe_limit,
                    }
                errors.append(f"{path}: keine Designs erkannt")
            except MakerWorldRequestError as exc:
                if exc.upstream_status not in {404, 405}:
                    raise
                errors.append(f"{path}: {exc}")
            except Exception as exc:
                errors.append(f"{path}: {exc}")
        raise MakerWorldError(
            "MakerWorld-Suche lieferte keine verwertbaren Modelle. " + " | ".join(errors)
        )

    async def async_detail(self, design_id: str) -> dict[str, Any]:
        """Compatibility bridge to the dedicated detail loader."""
        from .makerworld_detail import async_load_detail

        return await async_load_detail(self, design_id)

    async def _read_binary(self, response: ClientResponse, label: str) -> bytes:
        if response.status >= 400:
            detail = ""
            try:
                payload = await response.json(content_type=None)
                if isinstance(payload, dict):
                    detail = _string(_first(payload, ("message", "error", "msg")), 500)
            except Exception:
                detail = ""
            raise MakerWorldError(
                f"{label} antwortete mit HTTP {response.status}"
                + (f": {detail}" if detail else "")
            )
        payload = bytearray()
        async for chunk in response.content.iter_chunked(256 * 1024):
            payload.extend(chunk)
            if len(payload) > _MAX_DOWNLOAD_BYTES:
                raise MakerWorldError("MakerWorld-3MF überschreitet 500 MB")
        return bytes(payload)

    async def _resolve_model_id(self, design_id: str, supplied: str) -> str:
        candidate = _string(supplied, 120)
        if candidate:
            return candidate
        normalized = _string(design_id, 30)
        if not _MODEL_ID.fullmatch(normalized):
            raise MakerWorldError("Für den signierten Download fehlt eine gültige Modell-ID")
        payload = await self._json(
            f"design-service/design/{quote(normalized, safe='')}",
            {"trafficSource": "browse", "visitHistory": "false"},
        )
        from .makerworld_download import _model_id_from_payload
        value = _model_id_from_payload(payload, normalized)
        if value:
            return value
        raise MakerWorldError("MakerWorld-Detailantwort enthaelt keine eindeutige modelId")

    async def _signed_download(
        self,
        account: _AccountContext,
        design_id: str,
        profile_id: str,
        model_id: str,
    ) -> bytes:
        from .makerworld_transfer import download_signed_profile

        return await download_signed_profile(self, account, design_id, profile_id, model_id)

    async def _legacy_download(self, account: _AccountContext, instance_id: str) -> bytes:
        if not _INSTANCE_ID.fullmatch(instance_id):
            raise MakerWorldError("Ungültige MakerWorld-Instanz-ID")
        session = async_get_clientsession(self.hass)
        errors: list[str] = []
        for base in (account.api_base, _WEB_API_GLOBAL):
            url = (
                f"{base}/design-service/instance/"
                f"{quote(instance_id, safe='')}/f3mf"
            )
            try:
                async with session.get(
                    url,
                    params={"type": "download"},
                    headers=self._headers(
                        account,
                        "application/octet-stream,application/zip,*/*",
                    ),
                    allow_redirects=True,
                    timeout=ClientTimeout(total=180),
                ) as response:
                    return await self._read_binary(response, "MakerWorld-3MF-Download")
            except Exception as exc:
                errors.append(f"{base}: {exc}")
        raise MakerWorldError(" | ".join(errors))

    async def async_download_instance(
        self,
        instance_id: str,
        *,
        design_id: str = "",
        profile_id: str = "",
        model_id: str = "",
    ) -> bytes:
        # Do not truncate or substitute identities: an explicit profile must stay
        # that profile even after denial, timeout or an invalid response.
        if not isinstance(instance_id, str) or not _INSTANCE_ID.fullmatch(instance_id):
            raise ValueError("Ungültige MakerWorld-Instanz-ID")
        if (not isinstance(profile_id, str) or not _INSTANCE_ID.fullmatch(profile_id)
                or not isinstance(design_id, str) or not isinstance(model_id, str)
                or not (design_id or model_id)):
            raise MakerWorldError(
                "Das gewählte MakerWorld-Druckprofil ist nicht vollständig zugeordnet. "
                "Bitte die Modelldetails erneut öffnen und das Profil auswählen."
            )
        account = self._account_scope()
        if not _MODEL_ID.fullmatch(design_id):
            raise MakerWorldError("Fuer den Import fehlt die eindeutige Design-ID. Bitte die Modelldetails erneut oeffnen.")
        key = (design_id, instance_id)
        binding = self._profile_bindings.get(key)
        if binding is None:
            if any(instance == instance_id for _, instance in self._profile_bindings):
                raise MakerWorldError("Das Druckprofil gehoert nicht zum ausgewaehlten Design.")
            from .makerworld_download import remember_design_payload
            payload = await self._json(f"design-service/design/{quote(design_id, safe='')}",
                                       {"trafficSource": "browse", "visitHistory": "false"})
            self._check_account(account)
            remember_design_payload(payload, design_id, runtime=self)
            binding = self._profile_bindings.get(key)
        if binding is None or binding[0] != profile_id or (model_id and binding[1] != model_id):
            raise MakerWorldError("Design, Modell und Druckprofil sind nicht eindeutig zugeordnet. Bitte die Modelldetails erneut oeffnen.")
        self._check_account(account)
        return await self._signed_download(account, design_id, profile_id, binding[1])


def get_makerworld_runtime(hass: HomeAssistant) -> MakerWorldRuntime:
    data = hass.data.setdefault(DOMAIN, {})
    key = "makerworld_runtime"
    runtime = data.get(key)
    if not isinstance(runtime, MakerWorldRuntime):
        runtime = MakerWorldRuntime(hass)
        data[key] = runtime
    return runtime
