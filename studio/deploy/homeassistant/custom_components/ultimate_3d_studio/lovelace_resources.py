"""Conservatively register the packaged Studio Lovelace resource in storage mode.

No layout, dashboards, YAML resources, or existing resource entries are changed.
This module operates on the already initialized Lovelace data object so that
the small contract can be tested without a running Home Assistant instance.
"""
from __future__ import annotations

RESOURCE_URL = "/ultimate-3d-studio/assets/ultimate-3d-studio.js"
LEGACY_RESOURCE_URL = "/local/3d-studio/ultimate-3d-studio.js"


def _resource_path(item: object) -> str:
    if not isinstance(item, dict):
        return ""
    url = item.get("url")
    if not isinstance(url, str):
        return ""
    return url.split("?", 1)[0].split("#", 1)[0]


async def async_ensure_studio_lovelace_resource(lovelace_data: object | None) -> str:
    """Add one JS module only when HA uses the writable Lovelace storage mode."""
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

    for item in entries:
        if _resource_path(item) == RESOURCE_URL:
            return "already_registered" if item.get("type") == "module" else "type_conflict"
    for item in entries:
        if _resource_path(item) == LEGACY_RESOURCE_URL:
            # Preserve existing users' dashboards until the controlled live migration.
            return "legacy_resource_preserved"

    await resources.async_create_item({"url": RESOURCE_URL, "res_type": "module"})
    return "registered"
