"""Robust MakerWorld detail normalization for Studio."""
from __future__ import annotations

import asyncio
import logging
import json
import re
from html import unescape
from typing import Any, Iterable
from urllib.parse import quote

from .makerworld_download import remember_design_payload
from .makerworld_runtime import MakerWorldError, MakerWorldRuntime

_LOGGER = logging.getLogger(__name__)

_COMMENTS_TIMEOUT = 8.0
_RECOMMENDATIONS_TIMEOUT = 3.0
_FALLBACK_TIMEOUT = 5.0

_IMAGE_URL_RE = re.compile(r"(?:(?:https:)?//[^\s\"'<>)]*\.(?:png|jpe?g|webp|gif)(?:\?[^\s\"'<>)]*)?)", re.IGNORECASE)
_IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", re.IGNORECASE)
_DESCRIPTION_IMAGE_KEYS = (
    "description",
    "designDescription",
    "design_description",
    "summary",
    "content",
    "introduction",
    "richText",
    "rich_text",
    "html",
    "body",
)


def _description_images(value: Any) -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        seen: set[str] = set()
        for key in _DESCRIPTION_IMAGE_KEYS:
            for candidate in _description_images(value.get(key)):
                if candidate not in seen:
                    seen.add(candidate)
                    result.append(candidate)
        return result
    if isinstance(value, list):
        result: list[str] = []
        seen: set[str] = set()
        for item in value:
            for candidate in _description_images(item):
                if candidate not in seen:
                    seen.add(candidate)
                    result.append(candidate)
        return result
    if not isinstance(value, str):
        return []
    text = unescape(value)
    result: list[str] = []
    seen: set[str] = set()
    for pattern in (_IMG_SRC_RE, _MD_IMAGE_RE, _IMAGE_URL_RE):
        for match in pattern.findall(text):
            candidate = match.strip()
            if candidate.startswith("//"):
                candidate = f"https:{candidate}"
            if candidate.startswith("https://") and candidate not in seen:
                seen.add(candidate)
                result.append(candidate)
    return result[:30]


def _text(value: Any, limit: int = 1000) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


def _first(mapping: dict[str, Any], names: tuple[str, ...], default: Any = None) -> Any:
    for name in names:
        value = mapping.get(name)
        if value not in (None, "", [], {}):
            return value
    return default


def _walk(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            if isinstance(child, (dict, list)):
                yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _design_id(mapping: dict[str, Any]) -> str:
    return _text(_first(mapping, ("designId", "design_id", "modelId", "model_id", "id")), 30)


def _instance_id(mapping: dict[str, Any]) -> str:
    return _text(_first(mapping, ("instanceId", "instance_id", "modelInstanceId", "model_instance_id", "profileId", "profile_id", "id")), 90)


def _name(value: Any) -> str:
    if isinstance(value, str):
        return _text(value, 240)
    if not isinstance(value, dict):
        return ""
    return _text(_first(value, ("name", "nickname", "userName", "username", "displayName", "display_name", "creatorName", "designerName", "title")), 240)


def _image(value: Any) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        return candidate if candidate.startswith("https://") else ""
    if isinstance(value, list):
        for item in value:
            candidate = _image(item)
            if candidate:
                return candidate
        return ""
    if isinstance(value, dict):
        for key in ("url", "imageUrl", "image_url", "coverUrl", "cover_url", "thumbnailUrl", "thumbnail_url", "downloadUrl", "download_url", "source", "src"):
            candidate = _image(value.get(key))
            if candidate:
                return candidate
    return ""


def _images(mapping: dict[str, Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for key in ("images", "pictures", "designPictures", "design_pictures", "designPictureList", "imageList", "modelImages", "thumbnails", "renderImages", "descriptionImages", "description_images", "media", "attachments"):
        values = mapping.get(key)
        if isinstance(values, list):
            for value in values:
                candidate = _image(value)
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    result.append(candidate)
    for key in ("cover", "coverUrl", "thumbnail", "thumbnailUrl", "thumbnail_url", "image", "imageUrl", "designPicture"):
        candidate = _image(mapping.get(key))
        if candidate and candidate not in seen:
            seen.add(candidate)
            result.insert(0, candidate)
    for candidate in _description_images(mapping):
        if candidate and candidate not in seen:
            seen.add(candidate)
            result.append(candidate)
    return result[:40]


def _int(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _richness(mapping: dict[str, Any]) -> tuple[int, int]:
    keys = ("title", "description", "designCreator", "creator", "images", "designPictures", "instances", "modelInstances", "tags", "license")
    return sum(1 for key in keys if mapping.get(key) not in (None, "", [], {})), len(mapping)


def _raw_design(payload: Any, design_id: str) -> dict[str, Any]:
    exact = [item for item in _walk(payload) if _design_id(item) == design_id]
    if exact:
        return max(exact, key=_richness)
    if isinstance(payload, dict):
        for key in ("data", "result", "design", "model", "detail", "designInfo", "design_info"):
            item = payload.get(key)
            if isinstance(item, dict) and _first(item, ("title", "name", "designName", "design_name")):
                enriched = dict(item)
                enriched.setdefault("designId", design_id)
                return enriched
        if _first(payload, ("title", "name", "designName", "design_name")):
            enriched = dict(payload)
            enriched.setdefault("designId", design_id)
            return enriched
    raise MakerWorldError("MakerWorld-Detailantwort enthält kein passendes Modell")


def _creator(mapping: dict[str, Any]) -> str:
    for key in ("designCreator", "design_creator", "creator", "designer", "author", "user", "owner", "account"):
        candidate = _name(mapping.get(key))
        if candidate:
            return candidate
    return _text(_first(mapping, ("creatorName", "creator_name", "designerName", "designer_name", "authorName", "author_name", "userName", "user_name")), 240) or "MakerWorld"


def _tags(mapping: dict[str, Any]) -> list[str]:
    raw = _first(mapping, ("tags", "tagList", "tag_list", "categories", "categoryList"), [])
    if isinstance(raw, str):
        raw = [part.strip() for part in raw.split(",")]
    result: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            value = _name(item) if isinstance(item, dict) else _text(item, 80)
            folded = value.casefold()
            if value and folded not in seen:
                seen.add(folded)
                result.append(value)
    return result[:30]


def _plate(mapping: dict[str, Any], fallback_index: int) -> dict[str, Any]:
    index = _int(_first(mapping, ("plateIndex", "plate_index", "index", "plateNo", "plate_no"), fallback_index))
    images = _images(mapping)
    filaments = _first(mapping, ("filaments", "filamentList", "filament_list", "materials"), [])
    return {
        "id": _text(_first(mapping, ("plateId", "plate_id", "id")), 90) or str(index),
        "index": index,
        "name": _text(_first(mapping, ("title", "name", "plateName", "plate_name")), 300) or f"Druckplatte {index + 1}",
        "thumbnail_url": images[0] if images else None,
        "print_time_seconds": _int(_first(mapping, ("printTime", "print_time", "printTimeSeconds", "print_time_seconds", "prediction"))),
        "weight_grams": _int(_first(mapping, ("weight", "weightGrams", "weight_grams", "filamentWeight", "filament_weight"))),
        "filaments": filaments if isinstance(filaments, list) else [],
    }


def _instance(mapping: dict[str, Any], design_id: str) -> dict[str, Any] | None:
    instance_id = _instance_id(mapping)
    if not instance_id:
        return None
    extension = mapping.get("extention", mapping.get("extension", {}))
    if isinstance(extension, str):
        try:
            extension = json.loads(extension)
        except (ValueError, TypeError):
            extension = {}
    extension = extension if isinstance(extension, dict) else {}
    info = extension.get("modelInfo", {})
    info = info if isinstance(info, dict) else {}
    compatibility = info.get("compatibility", {})
    compatibility = compatibility if isinstance(compatibility, dict) else {}
    plate_values = _first(mapping, ("plates", "plateList", "plate_list", "printPlates", "print_plates", "plateInfos", "plate_infos"), [])
    if not plate_values:
        plate_values = info.get("plates", [])
    plates = [_plate(item, index) for index, item in enumerate(plate_values) if isinstance(item, dict)] if isinstance(plate_values, list) else []
    images = _images(mapping)
    return {
        "id": instance_id,
        "design_id": design_id,
        "title": _text(_first(mapping, ("title", "name", "instanceName", "instance_name")), 300) or f"Druckprofil {instance_id}",
        "description": _text(_first(mapping, ("description", "summary", "content")), 3000),
        "thumbnail_url": images[0] if images else None,
        "images": images,
        "is_default": _bool(_first(mapping, ("isDefault", "is_default", "default", "defaultInstance"))),
        "printer_model": _text(_first(mapping, ("printerModel", "printer_model", "printer", "machineName", "machine_name", "printerType", "printer_type"), compatibility.get("devProductName", "")), 240),
        "nozzle_diameter": _text(_first(mapping, ("nozzleDiameter", "nozzle_diameter", "nozzle", "nozzleSize", "nozzle_size"), compatibility.get("nozzleDiameter", "")), 40),
        "profile_name": _text(_first(mapping, ("profileName", "profile_name", "processName", "process_name", "printProfileName")), 300),
        "plates": plates,
        "plate_count": len(plates),
        "download_available": True,
    }


def _instances(payload: Any, raw: dict[str, Any], design_id: str) -> list[dict[str, Any]]:
    keys = ("instances", "modelInstances", "model_instances", "designInstances", "design_instances", "instanceList", "instance_list", "profiles", "printProfiles", "print_profiles")
    candidates: list[dict[str, Any]] = []
    # Only the selected design and its response wrappers own these profiles.
    sources = [raw]
    if isinstance(payload, dict):
        sources.append(payload)
        for key in ("data", "result", "detail"):
            wrapper = payload.get(key)
            if isinstance(wrapper, dict) and not _first(wrapper, ("title", "name")):
                sources.append(wrapper)
    for source in sources:
        for key in keys:
            values = source.get(key)
            if isinstance(values, list):
                candidates.extend(item for item in values if isinstance(item, dict))
    expanded: list[dict[str, Any]] = []
    for item in candidates:
        owner = _text(_first(item, ("designId", "design_id")), 90)
        if owner and owner != design_id:
            continue
        expanded.append(item)
        extension = item.get("extention", item.get("extension", {}))
        if isinstance(extension, str):
            try:
                extension = json.loads(extension)
            except (ValueError, TypeError):
                extension = {}
        alternatives = extension.get("otherCompatibilityModelInfo", []) if isinstance(extension, dict) else []
        for alternative in alternatives if isinstance(alternatives, list) else []:
            if not isinstance(alternative, dict) or not alternative.get("profileId"):
                continue
            variant = dict(item)
            for key in ("instanceId", "instance_id", "modelInstanceId", "model_instance_id", "profile_id"):
                variant.pop(key, None)
            variant.update({"profileId": alternative["profileId"], "isDefault": False,
                            "printerModel": alternative.get("devProductName", ""),
                            "extention": {"modelInfo": alternative.get("modelInfo", {})}})
            # Per-printer plates must never be inherited from another variant.
            for key in ("plates", "plateList", "plate_list", "printPlates", "print_plates", "plateInfos", "plate_infos", "nozzleDiameter", "nozzle_diameter"):
                variant.pop(key, None)
            expanded.append(variant)
    candidates = expanded
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        normalized = _instance(item, design_id)
        if normalized is None or normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        result.append(normalized)
    result.sort(key=lambda item: (not item["is_default"], item["title"].casefold()))
    return result



def _author_avatar(value: Any) -> str:
    if isinstance(value, dict):
        return _image(_first(value, ("avatar", "avatarUrl", "avatar_url", "picture", "image", "imageUrl", "image_url")))
    return ""


def _author(mapping: dict[str, Any]) -> tuple[str, str]:
    for key in ("user", "author", "creator", "designer", "account", "owner"):
        value = mapping.get(key)
        name = _name(value)
        if name:
            return name, _author_avatar(value)
    return (
        _text(_first(mapping, ("userName", "user_name", "authorName", "author_name", "nickname", "name")), 160) or "MakerWorld",
        _image(_first(mapping, ("avatar", "avatarUrl", "avatar_url"))),
    )


def _content(mapping: dict[str, Any]) -> str:
    for key in (
        "content",
        "comment",
        "commentContent",
        "comment_content",
        "message",
        "text",
        "body",
        "review",
        "description",
        "translatedContent",
        "translated_content",
        "originalContent",
        "original_content",
    ):
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return _text(value, 5000)
        if isinstance(value, dict):
            nested = _text(_first(value, ("text", "content", "plain", "value", "html")), 5000)
            if nested:
                return nested
    return ""


def _created_at(mapping: dict[str, Any]) -> str:
    return _text(_first(mapping, ("createdAt", "created_at", "createTime", "create_time", "publishTime", "publish_time", "updatedAt", "updated_at")), 100)


def _comment_id(mapping: dict[str, Any], fallback: str) -> str:
    return _text(_first(mapping, ("commentId", "comment_id", "ratingId", "rating_id", "replyId", "reply_id", "id")), 90) or fallback


def _rating_value(mapping: dict[str, Any]) -> float:
    value = _first(mapping, ("rating", "score", "star", "stars", "rate", "rateScore", "rate_score"), 0)
    try:
        return max(0.0, min(5.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _comment(mapping: dict[str, Any], fallback: str, depth: int = 0) -> dict[str, Any] | None:
    content = _content(mapping)
    author, avatar = _author(mapping)
    replies_raw = _first(mapping, ("replies", "replyList", "reply_list", "children", "subComments", "sub_comments"), [])
    replies: list[dict[str, Any]] = []
    if depth < 2 and isinstance(replies_raw, list):
        for index, item in enumerate(replies_raw):
            if isinstance(item, dict):
                reply = _comment(item, f"{fallback}-r{index}", depth + 1)
                if reply is not None:
                    replies.append(reply)
    if not content and not replies:
        return None
    reply_count = _int(_first(mapping, ("replyCount", "reply_count", "answers", "answerCount"), len(replies)))
    return {
        "id": _comment_id(mapping, fallback),
        "author": author,
        "avatar_url": avatar or None,
        "content": content,
        "created_at": _created_at(mapping),
        "like_count": _int(_first(mapping, ("likeCount", "like_count", "likes", "likedCount"))),
        "reply_count": max(reply_count, len(replies)),
        "rating": _rating_value(mapping),
        "boosted": _bool(_first(mapping, ("boosted", "isBoosted", "is_boosted", "boost"))),
        "original_available": _bool(_first(mapping, ("translated", "isTranslated", "is_translated", "translation"))),
        "replies": replies[:20],
    }


def _comments(payload: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source in _walk(payload):
        for key in (
            "comments",
            "commentList",
            "comment_list",
            "ratings",
            "ratingList",
            "rating_list",
            "reviews",
            "reviewList",
            "review_list",
            "items",
            "list",
            "rows",
            "records",
            "data",
        ):
            values = source.get(key)
            if isinstance(values, list):
                for item in values:
                    if isinstance(item, dict):
                        candidates.append(item)
    if not candidates:
        candidates = [item for item in _walk(payload) if _content(item) and any(key in item for key in ("commentId", "comment_id", "ratingId", "rating_id", "replyCount", "reply_count", "likeCount", "like_count", "rating", "score"))]
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(candidates):
        normalized = _comment(item, f"comment-{index}")
        if normalized is None or normalized["id"] in seen:
            continue
        seen.add(normalized["id"])
        result.append(normalized)
    return result[:50]


def _recommendation_id(mapping: dict[str, Any]) -> str:
    # modelId can be an opaque download identifier; detail links need the
    # numeric public design ID, also when both identifiers are supplied.
    for key in ("designId", "design_id", "id", "modelId", "model_id"):
        value = _text(mapping.get(key), 30)
        if value.isascii() and value.isdigit() and len(value) <= 20:
            return value
    return ""


def _recommendations(payload: Any, exclude_id: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = {exclude_id}

    def collect(value: Any) -> None:
        if isinstance(value, list):
            for child in value:
                collect(child)
            return
        if not isinstance(value, dict):
            return
        design_id = _recommendation_id(value)
        images = _images(value)
        title = _text(_first(value, ("title", "designName", "design_name", "modelName", "model_name")), 300)
        if not title and images:
            title = _text(value.get("name"), 300)
        if design_id and (title or images):
            if design_id not in seen:
                seen.add(design_id)
                stats = value.get("stats")
                stats = stats if isinstance(stats, dict) else {}
                result.append({
                    "id": design_id,
                    "title": title or f"MakerWorld Modell {design_id}",
                    "creator": _creator(value),
                    "thumbnail_url": images[0] if images else None,
                    "stats": {
                        "likes": _int(_first(value, ("likeCount", "like_count", "likes", "likedCount"), stats.get("likes"))),
                        "downloads": _int(_first(value, ("downloadCount", "download_count", "downloads"), stats.get("downloads"))),
                        "comments": _int(_first(value, ("commentCount", "comment_count", "comments"), stats.get("comments"))),
                        "collects": _int(_first(value, ("collectCount", "collect_count", "favoriteCount", "favorite_count"), stats.get("collects"))),
                        "prints": _int(_first(value, ("printCount", "print_count", "prints"), stats.get("prints"))),
                    },
                })
            # Creator, plate and profile IDs inside a recognized model are
            # metadata, not additional recommendation cards.
            return
        for child in value.values():
            if isinstance(child, (dict, list)):
                collect(child)

    collect(payload)
    return result[:12]


def _embedded_recommendations(payload: Any, design_id: str) -> list[dict[str, Any]]:
    values = []
    for source in _walk(payload):
        for key in ("recommendations", "recommendedDesigns", "relatedDesigns", "recommendList", "recommendationList", "youLike"):
            candidate = source.get(key)
            if isinstance(candidate, (dict, list)):
                values.append(candidate)
    return _recommendations(values, design_id)


async def _optional_json(runtime: MakerWorldRuntime, path: str, params: dict[str, Any]) -> Any:
    try:
        return await runtime._json(path, params)
    except Exception as exc:
        _LOGGER.debug("Optional MakerWorld endpoint %s failed: %s", path, exc)
        return {}


async def _load_comments(runtime: MakerWorldRuntime, design_id: str) -> list[dict[str, Any]]:
    quoted = quote(design_id, safe="")
    common = {"designId": design_id, "modelId": design_id, "offset": 0, "limit": 50}
    attempts = (
        (f"comment-service/rating/{quoted}", {"offset": 0, "limit": 50}),
        (f"comment-service/comment/{quoted}", {"offset": 0, "limit": 50}),
        (f"comment-service/community/{quoted}", {"offset": 0, "limit": 50}),
        (f"comment-service/comment/design/{quoted}", {"offset": 0, "limit": 50}),
        (f"comment-service/comment/list/{quoted}", {"offset": 0, "limit": 50}),
        (f"comment-service/rating/list/{quoted}", {"offset": 0, "limit": 50}),
        ("comment-service/comment/list", common),
        ("comment-service/rating/list", common),
        ("comment-service/comment", common),
        ("comment-service/rating", common),
    )
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        async with asyncio.timeout(_COMMENTS_TIMEOUT):
            for path, params in attempts:
                payload = await _optional_json(runtime, path, params)
                for item in _comments(payload):
                    if item["id"] not in seen:
                        seen.add(item["id"])
                        merged.append(item)
    except TimeoutError:
        _LOGGER.debug("Optional MakerWorld enrichment budget exhausted")
    return merged[:50]


async def _load_recommendations(runtime: MakerWorldRuntime, design_id: str) -> list[dict[str, Any]]:
    attempts = (
        ("search-service/recommand/youlike", {"designId": design_id, "limit": 12}),
        ("search-service/recommend/youlike", {"designId": design_id, "limit": 12}),
        ("design-recommend-service/my/for-you", {"designId": design_id, "limit": 12}),
        (f"design-service/design/{quote(design_id, safe='')}/recommend", {"limit": 12}),
        ("search-service/recommend/related", {"designId": design_id, "limit": 12}),
    )
    merged: list[dict[str, Any]] = []
    seen: set[str] = {design_id}
    try:
        async with asyncio.timeout(_RECOMMENDATIONS_TIMEOUT):
            for path, params in attempts:
                payload = await _optional_json(runtime, path, params)
                for item in _recommendations(payload):
                    if item["id"] not in seen:
                        seen.add(item["id"])
                        merged.append(item)
    except TimeoutError:
        _LOGGER.debug("Optional MakerWorld enrichment budget exhausted")
    return merged[:12]


async def _fallback_recommendations(runtime: MakerWorldRuntime, detail: dict[str, Any]) -> list[dict[str, Any]]:
    design_id = str(detail.get("id") or "")
    search_terms = [str(item) for item in detail.get("tags", []) if item]
    title_words = [part for part in str(detail.get("title") or "").replace("/", " ").split() if len(part) >= 4]
    search_terms.extend(title_words[:3])
    merged: list[dict[str, Any]] = []
    seen: set[str] = {design_id}

    def collect(payload: Any) -> None:
        for item in _recommendations(payload):
            if item["id"] not in seen:
                seen.add(item["id"])
                merged.append(item)

    try:
        async with asyncio.timeout(_FALLBACK_TIMEOUT):
            for term in search_terms[:6]:
                if len(merged) >= 12:
                    break
                try:
                    page = await runtime.async_browse(query=term, limit=12)
                    collect({"items": page.get("items", [])})
                except Exception as exc:
                    _LOGGER.debug("MakerWorld recommendation search fallback for %s failed: %s", term, exc)
            if len(merged) < 6:
                for nav_key in ("Trending", "Popular", "Latest"):
                    if len(merged) >= 12:
                        break
                    try:
                        page = await runtime.async_browse(nav_key=nav_key, limit=12)
                        collect({"items": page.get("items", [])})
                    except Exception as exc:
                        _LOGGER.debug("MakerWorld recommendation nav fallback %s failed: %s", nav_key, exc)
    except TimeoutError:
        _LOGGER.debug("Optional MakerWorld enrichment budget exhausted")
    return merged[:12]


def _normalize(payload: Any, design_id: str) -> dict[str, Any]:
    raw = _raw_design(payload, design_id)
    images = _images(raw)
    description_images = _description_images(raw)
    instances = _instances(payload, raw, design_id)
    comments = _comments(payload)
    return {
        "id": design_id,
        "title": _text(_first(raw, ("title", "name", "designName", "design_name", "modelName", "model_name")), 300) or f"MakerWorld Modell {design_id}",
        "description": str(_first(raw, ("description", "summary", "designDescription", "design_description", "content", "introduction")) or "")[:30000],
        "creator": _creator(raw),
        "thumbnail_url": images[0] if images else None,
        "images": images,
        "description_images": description_images,
        "tags": _tags(raw),
        "stats": {
            "likes": _int(_first(raw, ("likeCount", "like_count", "likes", "likedCount"))),
            "downloads": _int(_first(raw, ("downloadCount", "download_count", "downloads"))),
            "comments": _int(_first(raw, ("commentCount", "comment_count", "comments"))),
            "collects": _int(_first(raw, ("collectCount", "collect_count", "favoriteCount", "favorite_count"))),
            "prints": _int(_first(raw, ("printCount", "print_count", "prints"))),
        },
        "model_url": f"https://makerworld.com/de/models/{design_id}",
        "license": _text(_first(raw, ("license", "licenseName", "license_name", "licenseType", "license_type")), 200),
        "published_at": _text(_first(raw, ("publishTime", "publish_time", "publishedAt", "published_at", "createdAt", "created_at", "createTime", "create_time")), 100),
        "instances": instances,
        "instance_count": len(instances),
        "comments": comments,
        "comment_count": len(comments),
        "recommendations": _embedded_recommendations(payload, design_id),
    }


async def _complete_recommendations(runtime: MakerWorldRuntime, detail: dict[str, Any]) -> list[dict[str, Any]]:
    merged = list(detail["recommendations"])
    seen = {str(detail["id"]), *(item["id"] for item in merged)}

    def collect(items: list[dict[str, Any]]) -> None:
        for item in items:
            if item["id"] not in seen:
                seen.add(item["id"])
                merged.append(item)

    if len(merged) < 12:
        collect(await _load_recommendations(runtime, str(detail["id"])))
    if len(merged) < 12:
        collect(await _fallback_recommendations(runtime, detail))
    return merged[:12]


async def _optional_enrichment(operation: Any) -> list[dict[str, Any]]:
    try:
        return await operation
    except Exception as exc:
        _LOGGER.debug("Optional MakerWorld detail enrichment failed: %s", exc)
        return []


async def async_load_detail(runtime: MakerWorldRuntime, design_id: str) -> dict[str, Any]:
    normalized = _text(design_id, 30)
    if not normalized.isdigit() or len(normalized) > 20:
        raise ValueError("Ungültige MakerWorld-Modell-ID")
    path = f"design-service/design/{quote(normalized, safe='')}"
    attempts = (
        {"trafficSource": "browse", "visitHistory": "true"},
        {"trafficSource": "browse", "visitHistory": "false"},
        {"trafficSource": "recommend", "visitHistory": "false"},
        {"trafficSource": "search", "visitHistory": "false"},
        {},
    )
    errors: list[str] = []
    for params in attempts:
        label = "ohne Parameter" if not params else ",".join(f"{key}={value}" for key, value in params.items())
        try:
            payload = await runtime._json(path, params)
            remember_design_payload(payload, normalized)
            detail = _normalize(payload, normalized)
            break
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    else:
        message = f"MakerWorld-Details für Modell {normalized} konnten nicht geladen werden. " + " | ".join(errors)
        _LOGGER.warning("%s", message)
        raise MakerWorldError(message)

    extra_comments, extra_recommendations = await asyncio.gather(
        _optional_enrichment(_load_comments(runtime, normalized)),
        _optional_enrichment(_complete_recommendations(runtime, detail)),
    )
    if extra_comments:
        # Preserve comments already included in the detail response.
        comments = {item["id"]: item for item in detail["comments"]}
        comments.update({item["id"]: item for item in extra_comments})
        detail["comments"] = list(comments.values())[:50]
        detail["comment_count"] = len(detail["comments"])
    if extra_recommendations:
        detail["recommendations"] = extra_recommendations
    return detail
