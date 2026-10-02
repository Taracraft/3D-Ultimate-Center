"""Safe, persistent MakerWorld link catalog for Ultimate 3D Studio V6.

MakerWorld does not expose a documented public catalog API. This module therefore
handles only explicit user-provided MakerWorld model URLs, fetches their public
OpenGraph/JSON-LD metadata, and stores link cards. It never performs bulk scraping
or unauthenticated model downloads.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

STORE_VERSION = 1
STORE_KEY = "ultimate_3d_studio_v6.makerworld_catalog"
MAX_ITEMS = 200
MAX_HTML_BYTES = 2_000_000
ALLOWED_HOSTS = {"makerworld.com", "www.makerworld.com"}
MODEL_ID_PATTERN = re.compile(r"/models/(\d+)(?:[-/?#]|$)", re.IGNORECASE)


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.title_parts: list[str] = []
        self.json_ld_blocks: list[str] = []
        self._json_ld_parts: list[str] = []
        self._in_title = False
        self._in_json_ld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value or "" for key, value in attrs}
        lowered = tag.lower()
        if lowered == "meta":
            key = (attributes.get("property") or attributes.get("name") or "").strip().lower()
            content = attributes.get("content", "").strip()
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif lowered == "link" and "canonical" in attributes.get("rel", "").lower().split():
            self.canonical = attributes.get("href", "").strip()
        elif lowered == "title":
            self._in_title = True
        elif lowered == "script" and "ld+json" in attributes.get("type", "").lower():
            self._in_json_ld = True
            self._json_ld_parts = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._in_title = False
        elif lowered == "script" and self._in_json_ld:
            block = "".join(self._json_ld_parts).strip()
            if block:
                self.json_ld_blocks.append(block)
            self._json_ld_parts = []
            self._in_json_ld = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_json_ld:
            self._json_ld_parts.append(data)


def _trim(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _normalize_model_url(value: str) -> tuple[str, str]:
    raw = value.strip()
    if not raw:
        raise ValueError("MakerWorld-URL darf nicht leer sein")
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("MakerWorld-URL enthält einen ungültigen Port") from error
    if parsed.scheme.lower() != "https" or host not in ALLOWED_HOSTS:
        raise ValueError("Nur offizielle HTTPS-Modell-URLs von makerworld.com sind erlaubt")
    if parsed.username or parsed.password or port not in {None, 443}:
        raise ValueError("MakerWorld-URL enthält nicht erlaubte Zugangsdaten oder Ports")
    match = MODEL_ID_PATTERN.search(parsed.path)
    if match is None:
        raise ValueError("Die URL muss auf eine MakerWorld-Modellseite /models/<ID> zeigen")
    clean = parsed._replace(scheme="https", netloc="makerworld.com", query="", fragment="")
    return urlunparse(clean), match.group(1)


def _json_ld_objects(blocks: list[str]) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []

    def collect(item: Any) -> None:
        if isinstance(item, dict):
            objects.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                for entry in graph:
                    collect(entry)
        elif isinstance(item, list):
            for entry in item:
                collect(entry)

    for raw in blocks:
        try:
            collect(json.loads(raw))
        except (TypeError, ValueError):
            continue
    return objects


def _author_name(value: Any) -> str:
    if isinstance(value, str):
        return _trim(value, 160)
    if isinstance(value, dict):
        return _trim(value.get("name") or value.get("alternateName"), 160)
    if isinstance(value, list):
        names = [_author_name(item) for item in value]
        return ", ".join(name for name in names if name)[:160]
    return ""


def _image_url(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return str(value.get("url") or value.get("contentUrl") or "")
    if isinstance(value, list):
        for item in value:
            candidate = _image_url(item)
            if candidate:
                return candidate
    return ""


class MakerWorldCatalog:
    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, STORE_KEY)
        self._items: list[dict[str, Any]] = []
        self._loaded = False
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        async with self._lock:
            if self._loaded:
                return
            stored = await self._store.async_load() or {}
            items = stored.get("items", [])
            self._items = [item for item in items if isinstance(item, dict)][:MAX_ITEMS]
            self._loaded = True

    async def async_list(self) -> list[dict[str, Any]]:
        await self.async_load()
        return deepcopy(self._items)

    async def async_add(self, model_url: str) -> dict[str, Any]:
        await self.async_load()
        normalized_url, model_id = _normalize_model_url(model_url)
        metadata = await self._async_fetch_metadata(normalized_url, model_id)
        async with self._lock:
            self._items = [item for item in self._items if str(item.get("id")) != model_id]
            self._items.insert(0, metadata)
            del self._items[MAX_ITEMS:]
            await self._store.async_save({"items": self._items})
        return deepcopy(metadata)

    async def async_remove(self, model_id: str) -> dict[str, Any] | None:
        await self.async_load()
        async with self._lock:
            for index, item in enumerate(self._items):
                if str(item.get("id")) != str(model_id):
                    continue
                removed = self._items.pop(index)
                await self._store.async_save({"items": self._items})
                return deepcopy(removed)
        return None

    async def async_refresh(self, model_id: str) -> dict[str, Any] | None:
        await self.async_load()
        item = next((entry for entry in self._items if str(entry.get("id")) == str(model_id)), None)
        if item is None:
            return None
        return await self.async_add(str(item.get("model_url", "")))

    async def _async_fetch_metadata(self, model_url: str, model_id: str) -> dict[str, Any]:
        session = async_get_clientsession(self._hass)
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "Ultimate-3D-Studio-V6/6.0 (+Home Assistant; user-requested metadata)",
        }
        async with session.get(
            model_url,
            headers=headers,
            allow_redirects=True,
            timeout=20,
        ) as response:
            final_url, final_id = _normalize_model_url(str(response.url))
            if final_id != model_id:
                raise ValueError("MakerWorld-Weiterleitung zeigt auf ein anderes Modell")
            if response.status >= 400:
                raise ValueError(f"MakerWorld antwortete mit HTTP {response.status}")
            content_type = response.headers.get("Content-Type", "")
            if "html" not in content_type.lower():
                raise ValueError("MakerWorld lieferte keine Modellseite")
            payload = await response.content.read(MAX_HTML_BYTES + 1)
            if len(payload) > MAX_HTML_BYTES:
                raise ValueError("MakerWorld-Modellseite ist unerwartet groß")
            encoding = response.charset or "utf-8"
            html = payload.decode(encoding, errors="replace")

        parser = _MetadataParser()
        parser.feed(html)
        objects = _json_ld_objects(parser.json_ld_blocks)
        preferred = next(
            (
                item
                for item in objects
                if str(item.get("@type", "")).lower()
                in {"product", "creativework", "3dmodel", "thing", "article"}
            ),
            objects[0] if objects else {},
        )

        title = _trim(
            parser.meta.get("og:title")
            or preferred.get("name")
            or "".join(parser.title_parts)
            or f"MakerWorld Modell {model_id}",
            240,
        )
        description = _trim(
            parser.meta.get("og:description")
            or parser.meta.get("description")
            or preferred.get("description"),
            1200,
        )
        image = _image_url(
            parser.meta.get("og:image")
            or parser.meta.get("twitter:image")
            or preferred.get("image")
        )
        image = urljoin(final_url, image) if image else ""
        image_parsed = urlparse(image) if image else None
        if image_parsed and image_parsed.scheme not in {"https", "http"}:
            image = ""

        creator = _author_name(preferred.get("author") or preferred.get("creator"))
        canonical = parser.canonical or parser.meta.get("og:url") or preferred.get("url") or final_url
        try:
            canonical_url, canonical_id = _normalize_model_url(urljoin(final_url, str(canonical)))
            if canonical_id != model_id:
                canonical_url = final_url
        except ValueError:
            canonical_url = final_url

        now = datetime.now(UTC).isoformat()
        return {
            "id": model_id,
            "title": title,
            "description": description,
            "thumbnail_url": image or None,
            "model_url": canonical_url,
            "creator": creator or "MakerWorld",
            "added_at": now,
            "updated_at": now,
            "source": "makerworld_link",
            "download_available": False,
            "import_available": False,
        }
