"""Integration-owned Studio dashboard using HA's native Lovelace panel API.

Never overwrites or adopts a user's dashboard at the same URL.
"""
from pathlib import Path

URL_PATH = 'ultimate-3d-studio'
OWNER = 'setup_dashboard_owner'

async def async_setup_dashboard(hass, enabled=True):
    from homeassistant.components import frontend
    from homeassistant.components.lovelace.dashboard import LovelaceYAML
    from .const import DOMAIN
    domain = hass.data.setdefault(DOMAIN, {})
    data = hass.data.get('lovelace')
    if data is None:
        return 'lovelace_not_loaded'
    owned = domain.get(OWNER)
    if not enabled:
        if owned is not None and data.dashboards.get(URL_PATH) is owned:
            frontend.async_remove_panel(hass, URL_PATH)
            data.dashboards.pop(URL_PATH)
            domain.pop(OWNER, None)
        return 'disabled'
    if owned is not None and data.dashboards.get(URL_PATH) is owned:
        return 'already_registered'
    if URL_PATH in data.dashboards or frontend.async_panel_exists(hass, URL_PATH):
        return 'existing_dashboard_preserved'
    config = {'id': 'ultimate_3d_studio', 'url_path': URL_PATH,
              'title': 'Ultimate 3D Studio', 'icon': 'mdi:printer-3d',
              'show_in_sidebar': True, 'require_admin': False,
              'mode': 'yaml', 'filename': str(Path(__file__).with_name('studio_dashboard.json'))}
    panel = LovelaceYAML(hass, URL_PATH, config)
    # Validate the shipped dashboard before exposing it in navigation.
    await panel.async_load(False)
    data.dashboards[URL_PATH] = panel
    try:
        frontend.async_register_built_in_panel(
            hass, 'lovelace', frontend_url_path=URL_PATH,
            sidebar_title=config['title'], sidebar_icon=config['icon'],
            show_in_sidebar=True, require_admin=False, config={'mode': 'yaml'})
    except Exception:
        if data.dashboards.get(URL_PATH) is panel:
            data.dashboards.pop(URL_PATH)
        raise
    domain[OWNER] = panel
    return 'registered'
