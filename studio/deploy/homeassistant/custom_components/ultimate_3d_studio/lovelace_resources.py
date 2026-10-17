"""Keep the single owned Studio resource on the installed packaged build.

Only the exact packaged or former manual Studio URL is owned here. Dashboards,
YAML resources and all unrelated resources, including PCC, remain untouched.
"""
from __future__ import annotations

import json
from pathlib import Path

RESOURCE_URL = "/ultimate-3d-studio/assets/ultimate-3d-studio.js"
LEGACY_RESOURCE_URL = "/local/3d-studio/ultimate-3d-studio.js"
ASSET_ROOT = Path(__file__).resolve().parent / "assets"


def _packaged_resource_url() -> str | None:
    required = ("ultimate-3d-studio.js", "ultimate-3d-studio.css", "ultimate-3d-studio-build.json")
    if not all((ASSET_ROOT / name).is_file() for name in required):
        return None
    try:
        build = json.loads((ASSET_ROOT / required[2]).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    digest = build.get("sha256") if isinstance(build, dict) else None
    if (not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)):
        return None
    return f"{RESOURCE_URL}?v={digest}"


def _resource_path(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    url = item.get("url")
    if not isinstance(url, str):
        return ""
    return url.split("?", 1)[0].split("#", 1)[0]


async def async_ensure_studio_lovelace_resource(lovelace_data: object | None) -> str:
    """Register or update one owned JS module in writable Lovelace storage."""
    if lovelace_data is None:
        return "lovelace_not_loaded"
    if getattr(lovelace_data, "resource_mode", None) != "storage":
        return "non_storage_mode"

    resources = getattr(lovelace_data, "resources", None)
    if resources is None:
        return "resources_unavailable"
    # HA's ResourceStorageCollection loads lazily; this prepares async_items.
    await resources.async_get_info()
    entries = resources.async_items()
    if not isinstance(entries, list):
        return "resources_unavailable"

    owned = [item for item in entries if _resource_path(item) in {RESOURCE_URL, LEGACY_RESOURCE_URL}]
    if len(owned) > 1:
        return "studio_resource_conflict"
    if owned and owned[0].get("type") != "module":
        return "type_conflict"
    resource_url = _packaged_resource_url()
    if resource_url is None:
        return "frontend_build_unavailable"
    if owned:
        item = owned[0]
        if item.get("url") == resource_url:
            return "already_registered"
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            return "resource_identity_invalid"
        await resources.async_update_item(item_id, {"url": resource_url, "res_type": "module"})
        return "updated"

    await resources.async_create_item({"url": resource_url, "res_type": "module"})
    return "registered"
