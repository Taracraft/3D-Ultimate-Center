"""Automatic Lovelace frontend resource registration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

from .const import (
    DOMAIN,
    FRONTEND_JS_FILENAME,
    FRONTEND_JS_PATH,
    FRONTEND_JS_URL,
    FRONTEND_LOGO_PATH,
    FRONTEND_URL_BASE,
)

_LOGGER = logging.getLogger(__name__)

_DATA_REGISTRAR = "_frontend_registrar"
_DATA_PATHS_REGISTERED = "_frontend_paths_registered"
_DATA_RESOURCE_REGISTERED = "_frontend_resource_registered"
_MAX_RETRIES = 48
_LEGACY_DOMAIN = "taracraft" "_3d_printer"
_LEGACY_FRONTEND_JS_PATHS = {
    f"/{_LEGACY_DOMAIN}/taracraft-3d-printer-cards.js",
}


class PrinterControlCenterFrontendRegistration:
    """Register bundled 3D-Printer Control Center cards as a Lovelace module."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.frontend_dir = Path(__file__).parent / "frontend"
        self._retry_count = 0

    async def async_register(self) -> None:
        await self._async_register_paths()
        await self._async_register_resource_when_ready()

    async def _async_register_paths(self) -> None:
        domain_data = self.hass.data.setdefault(DOMAIN, {})
        if domain_data.get(_DATA_PATHS_REGISTERED):
            return

        paths = [
            StaticPathConfig(
                FRONTEND_JS_PATH,
                str(self.frontend_dir / FRONTEND_JS_FILENAME),
                False,
            ),
            StaticPathConfig(
                FRONTEND_LOGO_PATH,
                str(self.frontend_dir / "logo-3d-printer-control-center.png"),
                True,
            ),
        ]

        for filename in (
            "default-offline.png",
            "default-idle.png",
            "default-preview.png",
        ):
            paths.append(
                StaticPathConfig(
                    f"{FRONTEND_URL_BASE}/{filename}",
                    str(self.frontend_dir / filename),
                    True,
                )
            )

        try:
            await self.hass.http.async_register_static_paths(paths)
        except RuntimeError:
            _LOGGER.debug("3D-Printer Control Center frontend paths were already registered")

        domain_data[_DATA_PATHS_REGISTERED] = True
        _LOGGER.info("3D-Printer Control Center frontend static paths registered")

    async def _async_register_resource_when_ready(self) -> None:
        lovelace = self.hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        mode = getattr(
            lovelace,
            "mode",
            getattr(lovelace, "resource_mode", "yaml"),
        )

        if lovelace is None or resources is None:
            await self._async_retry("Lovelace data is not ready")
            return

        if mode != "storage":
            add_extra_js_url(self.hass, FRONTEND_JS_URL)
            self.hass.data.setdefault(DOMAIN, {})[_DATA_RESOURCE_REGISTERED] = "extra_js_fallback"
            _LOGGER.warning(
                "Lovelace is not in storage mode; using extra-js fallback for %s",
                FRONTEND_JS_URL,
            )
            return

        if not resources.loaded:
            try:
                await resources.async_load()
                resources.loaded = True
            except Exception:
                _LOGGER.exception("Unable to load Lovelace resources before registration")
                await self._async_retry("Lovelace resources could not be loaded")
                return

        await self._async_create_or_update_resources(resources)

    async def _async_retry(self, reason: str) -> None:
        self._retry_count += 1
        if self._retry_count > _MAX_RETRIES:
            _LOGGER.error(
                "3D-Printer Control Center frontend resource registration stopped after %s retries: %s",
                _MAX_RETRIES,
                reason,
            )
            return

        async def _retry(_now: Any) -> None:
            await self._async_register_resource_when_ready()

        async_call_later(self.hass, 3, _retry)

    async def _async_create_or_update_resources(self, resources: Any) -> None:
        expected_url = FRONTEND_JS_URL
        expected_path = FRONTEND_JS_PATH

        for item in list(resources.async_items()):
            current_path = str(item.get("url", "")).split("?", 1)[0]
            if current_path not in _LEGACY_FRONTEND_JS_PATHS:
                continue
            try:
                await resources.async_delete_item(item["id"])
                _LOGGER.info("Removed legacy 3D-Printer Control Center resource: %s", item.get("url"))
            except Exception:
                _LOGGER.exception("Unable to remove legacy 3D-Printer Control Center resource")

        existing = [
            item
            for item in resources.async_items()
            if str(item.get("url", "")).split("?", 1)[0] == expected_path
        ]

        if not existing:
            await resources.async_create_item(
                {
                    "res_type": "module",
                    "url": expected_url,
                }
            )
            _LOGGER.info("Created 3D-Printer Control Center Lovelace resource: %s", expected_url)
        else:
            primary = existing[0]
            updates: dict[str, str] = {}

            if primary.get("url") != expected_url:
                updates["url"] = expected_url

            if primary.get("type") != "module":
                updates["res_type"] = "module"

            if updates:
                try:
                    await resources.async_delete_item(primary["id"])
                    await resources.async_create_item(
                        {
                            "res_type": "module",
                            "url": expected_url,
                        }
                    )
                    _LOGGER.info(
                        "Recreated stale 3D-Printer Control Center Lovelace resource: %s",
                        expected_url,
                    )
                except Exception:
                    _LOGGER.exception(
                        "Unable to recreate stale 3D-Printer Control Center Lovelace resource"
                    )
                    raise
            else:
                _LOGGER.info(
                    "3D-Printer Control Center Lovelace resource already current: %s",
                    expected_url,
                )

            for duplicate in existing[1:]:
                try:
                    await resources.async_delete_item(duplicate["id"])
                    _LOGGER.info(
                        "Removed duplicate 3D-Printer Control Center Lovelace resource: %s",
                        duplicate.get("url"),
                    )
                except Exception:
                    _LOGGER.exception(
                        "Unable to remove duplicate 3D-Printer Control Center Lovelace resource"
                    )

        current = [
            item
            for item in resources.async_items()
            if str(item.get("url", "")).split("?", 1)[0] == expected_path
        ]

        if not current or current[0].get("url") != expected_url:
            await self._async_retry(
                "3D-Printer Control Center Lovelace resource did not persist with expected URL"
            )
            return

        self._retry_count = 0
        self.hass.data.setdefault(DOMAIN, {})[_DATA_RESOURCE_REGISTERED] = expected_url


async def async_register_frontend(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    registrar = domain_data.get(_DATA_REGISTRAR)

    if registrar is None:
        registrar = PrinterControlCenterFrontendRegistration(hass)
        domain_data[_DATA_REGISTRAR] = registrar

    try:
        await registrar.async_register()
    except Exception:
        _LOGGER.exception(
            "3D-Printer Control Center frontend registration failed; continuing backend setup"
        )