"""Ultimate 3D Studio V6 Home Assistant integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import async_register_http_views
from .audit_log import get_audit_log
from .audit_runtime import async_start_audit_runtime
from .audit_views import async_register_audit_views
from .bambu_cloud_profile_sync import async_start_cloud_profile_sync, async_stop_cloud_profile_sync
from .const import DATA_RUNTIMES, DOMAIN, PLATFORMS
from .direct_print_slot_views import async_register_direct_print_slot_views
from .direct_print_views import async_register_direct_print_views
from .filament_color_views import async_register_filament_color_views
from .gallery_duplicate_views import async_register_gallery_duplicate_views
from .gallery_management_views_v2 import async_register_gallery_management_views
from .job_history_maintenance_views import async_register_job_history_maintenance_views
from .makerworld_views import async_register_makerworld_views
from .printer_storage_lookup_views import async_register_printer_storage_lookup_views
from .printer_storage_views import async_register_printer_storage_views
from .profile_runtime_v2 import install_profile_runtime_v2
from .profile_views import async_register_profile_views
from .runtime import Ultimate3DStudioRuntime
from .slicer_job_delete_views import async_register_slicer_job_delete_views
from .slicer_queue_views import async_register_slicer_queue_views
from .slicer_job_list_views import async_register_slicer_job_list_views
from .slicer_plate_views_v2 import async_register_slicer_plate_views_v2
from .slicer_scene_views import async_register_slicer_scene_views
from .slicer_toolpath_views import async_register_slicer_toolpath_views
from .slicer_views import async_register_slicer_views
from .studio_project_views import async_register_studio_project_views

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault(DATA_RUNTIMES, {})
    install_profile_runtime_v2(hass)
    async_register_http_views(hass)
    async_register_audit_views(hass)
    async_register_gallery_management_views(hass)
    async_register_gallery_duplicate_views(hass)
    async_register_makerworld_views(hass)
    async_register_profile_views(hass)
    async_register_slicer_views(hass)
    async_register_studio_project_views(hass)
    async_register_slicer_plate_views_v2(hass)
    async_register_slicer_scene_views(hass)
    async_register_slicer_toolpath_views(hass)
    async_register_slicer_job_list_views(hass)
    async_register_slicer_job_delete_views(hass)
    async_register_slicer_queue_views(hass)
    async_register_direct_print_views(hass)
    async_register_direct_print_slot_views(hass)
    async_register_filament_color_views(hass)
    async_register_printer_storage_views(hass)
    async_register_printer_storage_lookup_views(hass)
    async_register_job_history_maintenance_views(hass)
    await async_start_audit_runtime(hass)
    await get_audit_log(hass).async_append(
        category="System",
        component=DOMAIN,
        event="integration_setup",
        status="success",
        source="backend",
        details={"registered_http_views": True, "profile_runtime": "v2_complete"},
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.setdefault(DOMAIN, {})
    install_profile_runtime_v2(hass)
    runtimes: dict[str, Ultimate3DStudioRuntime] = domain_data.setdefault(DATA_RUNTIMES, {})
    runtime = Ultimate3DStudioRuntime(hass, entry)
    try:
        await runtime.async_start()
        runtimes[entry.entry_id] = runtime
        entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        await async_start_cloud_profile_sync(hass, entry)
        await get_audit_log(hass).async_append(
            category="System",
            component="config_entry",
            event="entry_started",
            status="success",
            source="backend",
            details={"entry_id": entry.entry_id, "title": entry.title, "provider_count": runtime.provider_count},
        )
    except Exception as error:
        runtimes.pop(entry.entry_id, None)
        await runtime.async_stop()
        await async_stop_cloud_profile_sync(hass)
        await get_audit_log(hass).async_append(
            category="System",
            component="config_entry",
            event="entry_start_failed",
            status="error",
            source="backend",
            details={"entry_id": entry.entry_id, "title": entry.title, "error": str(error)},
        )
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unloaded:
        await get_audit_log(hass).async_append(
            category="System",
            component="config_entry",
            event="entry_unload_failed",
            status="warning",
            source="backend",
            details={"entry_id": entry.entry_id, "title": entry.title},
        )
        return False
    await async_stop_cloud_profile_sync(hass)
    runtime = hass.data[DOMAIN][DATA_RUNTIMES].pop(entry.entry_id, None)
    if runtime is not None:
        await runtime.async_stop()
    await get_audit_log(hass).async_append(
        category="System",
        component="config_entry",
        event="entry_stopped",
        status="success",
        source="backend",
        details={"entry_id": entry.entry_id, "title": entry.title},
    )
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await get_audit_log(hass).async_append(
        category="System",
        component="config_entry",
        event="entry_reload_requested",
        status="info",
        source="backend",
        details={"entry_id": entry.entry_id, "title": entry.title},
    )
    await hass.config_entries.async_reload(entry.entry_id)
