from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

class SlicingServerEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)}, name="3D-Printer Slicing Server", manufacturer="Taracraft", model="Native Linux Worker", sw_version=coordinator.data.get("info", {}).get("version"))
