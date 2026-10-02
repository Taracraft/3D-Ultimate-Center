"""Binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SERIAL, DOMAIN
from .entity import PrinterControlCenterPrinterEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PrinterControlCenterOnlineSensor(coordinator, entry)])


class PrinterControlCenterOnlineSensor(PrinterControlCenterPrinterEntity, BinarySensorEntity):
    _attr_name = "Online"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_online"

    @property
    def is_on(self) -> bool:
        return self.coordinator.snapshot.online