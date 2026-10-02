from __future__ import annotations

from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PANEL_URL = "printer-slicing-server"
STATIC_URL = f"/{DOMAIN}_frontend"
REGISTERED_KEY = "_frontend_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(REGISTERED_KEY):
        return

    frontend_dir = Path(__file__).parent / "frontend"
    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig(
                f"{STATIC_URL}/panel.js",
                str(frontend_dir / "panel.js"),
                False,
            )
        ])
    except RuntimeError:
        pass

    frontend.async_register_built_in_panel(
        hass,
        component_name="custom",
        sidebar_title="Slicing Server",
        sidebar_icon="mdi:printer-3d",
        frontend_url_path=PANEL_URL,
        config={
            "_panel_custom": {
                "name": "printer-slicing-server-panel",
                "embed_iframe": True,
                "trust_external": False,
                "js_url": f"{STATIC_URL}/panel.js",
            }
        },
        require_admin=False,
        update=frontend.async_panel_exists(hass, PANEL_URL),
    )
    domain_data[REGISTERED_KEY] = True
