"""Binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import SlicingServerEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([SlicingServerOnlineSensor(coordinator, entry.entry_id)])


class SlicingServerOnlineSensor(SlicingServerEntity, BinarySensorEntity):
    _attr_name = "Online"

    def __init__(self, coordinator, entry_id) -> None:
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{entry_id}_online"

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
