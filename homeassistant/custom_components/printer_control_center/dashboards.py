"""Automatic Lovelace dashboards for 3D-Printer Control Center."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import frontend as ha_frontend
from homeassistant.components.lovelace import dashboard as lovelace_dashboard
from homeassistant.components.lovelace.const import (
    CONF_ICON,
    CONF_REQUIRE_ADMIN,
    CONF_SHOW_IN_SIDEBAR,
    CONF_TITLE,
    CONF_URL_PATH,
    LOVELACE_DATA,
    MODE_STORAGE,
    ConfigNotFound,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

_LOGGER = logging.getLogger(__name__)

_RETIRED_DASHBOARD_PATHS = ("3d-printer-control-center-queue",)

_DEFAULT_DASHBOARDS: tuple[dict[str, Any], ...] = (
    {
        "url_path": "3d-printer-control-center",
        "title": "3D-Druck",
        "icon": "mdi:printer-3d",
        "config": {
            "title": "3D-Druck",
            "views": [
                {
                    "title": "3D-Druck",
                    "path": "printer",
                    "icon": "mdi:printer-3d",
                    # Sections layout gives the printer card more horizontal room.
                    # This keeps the AMS and diagnostics compact instead of stretching downward.
                    "type": "sections",
                    "max_columns": 3,
                    "sections": [
                        {
                            "type": "grid",
                            "cards": [
                                {
                                    "type": "custom:printer-control-center-card",
                                    "card_size": "xl",
                                    "grid_options": {"columns": 16},
                                },
                            ],
                        },
                        {
                            "type": "grid",
                            "cards": [
                                {
                                    "type": "custom:printer-control-center-queue-card",
                                    "card_size": "xl",
                                    "grid_options": {"columns": 8},
                                },
                            ],
                        },

                    ],
                }
            ],
        },
    },
    {
        "url_path": "3d-printer-control-center-studio",
        "title": "3D-Studio / CAD-Vorschau",
        "icon": "mdi:cube-scan",
        "config": {
            "title": "3D-Studio / CAD-Vorschau",
            "views": [
                {
                    "title": "3D-Studio / CAD-Vorschau",
                    "path": "studio",
                    "icon": "mdi:cube-scan",
                    "type": "panel",
                    "cards": [
                        {
                            "type": "custom:printer-control-center-studio-card",
                            "title": "3D-Studio / CAD-Vorschau",
                            "card_size": "xl",
                        },
                    ],
                }
            ],
        },
    },    {
        "url_path": "3d-printer-control-center-gallery",
        "title": "3D-Drucker-Dateimanager/Galerie",
        "icon": "mdi:folder-multiple-image",
        "config": {
            "title": "3D-Drucker-Dateimanager/Galerie",
            "views": [
                {
                    "title": "3D-Drucker-Dateimanager/Galerie",
                    "path": "gallery",
                    "icon": "mdi:folder-multiple-image",
                    "type": "panel",
                    "cards": [
                        {
                            "type": "custom:printer-control-center-templates-card",
                            "card_size": "xl",
                        },
                    ],
                }
            ],
        },
    },
)


def _dashboard_item(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_URL_PATH: spec["url_path"],
        CONF_TITLE: spec["title"],
        CONF_ICON: spec["icon"],
        CONF_SHOW_IN_SIDEBAR: True,
        CONF_REQUIRE_ADMIN: False,
    }


def _register_panel(hass: HomeAssistant, item: dict[str, Any]) -> None:
    url_path = item[CONF_URL_PATH]
    ha_frontend.async_register_built_in_panel(
        hass,
        "lovelace",
        frontend_url_path=url_path,
        require_admin=item.get(CONF_REQUIRE_ADMIN, False),
        show_in_sidebar=item.get(CONF_SHOW_IN_SIDEBAR, True),
        sidebar_title=item[CONF_TITLE],
        sidebar_icon=item.get(CONF_ICON, "mdi:view-dashboard"),
        config={"mode": MODE_STORAGE},
        update=ha_frontend.async_panel_exists(hass, url_path),
    )


def _remove_panel(hass: HomeAssistant, url_path: str) -> None:
    remover = getattr(ha_frontend, "async_remove_panel", None)
    if remover is None:
        return
    try:
        remover(hass, url_path)
    except Exception:  # best-effort cleanup across HA frontend versions
        _LOGGER.debug("Unable to remove retired dashboard panel: %s", url_path, exc_info=True)


async def _async_remove_retired_dashboards(
    hass: HomeAssistant,
    collection: Any,
    lovelace_data: Any,
    by_path: dict[str, dict[str, Any]],
) -> list[str]:
    removed: list[str] = []
    for url_path in _RETIRED_DASHBOARD_PATHS:
        item = by_path.pop(url_path, None)
        if item is None:
            continue
        try:
            await collection.async_delete_item(item["id"])
            lovelace_data.dashboards.pop(url_path, None)
            _remove_panel(hass, url_path)
            removed.append(url_path)
            _LOGGER.info("Removed retired dashboard: %s", url_path)
        except Exception:
            _LOGGER.exception("Unable to remove retired dashboard: %s", url_path)
    return removed


async def async_ensure_default_dashboards(
    hass: HomeAssistant,
    *,
    force_config: bool = False,
) -> dict[str, list[str]]:
    """Create or repair the two integration-owned dashboards."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        _LOGGER.warning("Lovelace is not ready; default dashboards were not created")
        return {"created": [], "existing": [], "updated": [], "removed": []}

    collection = lovelace_dashboard.DashboardsCollection(hass)
    await collection.async_load()
    items = list(collection.async_items())
    by_path = {str(item.get(CONF_URL_PATH, "")): item for item in items}

    result: dict[str, list[str]] = {
        "created": [], "existing": [], "updated": [], "removed": []
    }
    result["removed"] = await _async_remove_retired_dashboards(
        hass, collection, lovelace_data, by_path
    )

    for spec in _DEFAULT_DASHBOARDS:
        url_path = spec["url_path"]
        item = by_path.get(url_path)
        created = False

        if item is None:
            item = await collection.async_create_item(_dashboard_item(spec))
            by_path[url_path] = item
            created = True
            result["created"].append(url_path)
            _LOGGER.info("Created default dashboard: %s", url_path)
        else:
            result["existing"].append(url_path)
            desired_item = _dashboard_item(spec)
            updates = {
                key: value
                for key, value in desired_item.items()
                if item.get(key) != value
            }
            if updates:
                item = await collection.async_update_item(item["id"], updates)
                by_path[url_path] = item
                if url_path not in result["updated"]:
                    result["updated"].append(url_path)
                _LOGGER.info("Updated managed dashboard metadata: %s", url_path)

        storage_dashboard = lovelace_data.dashboards.get(url_path)
        if storage_dashboard is None:
            storage_dashboard = lovelace_dashboard.LovelaceStorage(hass, item)
            lovelace_data.dashboards[url_path] = storage_dashboard

        _register_panel(hass, item)

        config_missing = False
        try:
            await storage_dashboard.async_load(False)
        except (ConfigNotFound, HomeAssistantError):
            config_missing = True

        if created or config_missing or force_config:
            await storage_dashboard.async_save(spec["config"])
            if not created and url_path not in result["updated"]:
                result["updated"].append(url_path)
            _LOGGER.info("Saved managed dashboard config: %s", url_path)

    return result