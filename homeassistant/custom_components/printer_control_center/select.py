"""Select entities."""
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import AMS_OPTIONS, AMS_OPTIONS_EN, CONF_AMS_TYPE, CONF_UI_LANGUAGE, DOMAIN
from .entity import PrinterControlCenterPrinterEntity


SPEEDS = {"silent": 1, "standard": 2, "sport": 3, "ludicrous": 4}
REVERSE = {value: key for key, value in SPEEDS.items()}


def _ams_labels(entry, hass) -> dict[str, str]:
    """Return AMS labels using the selected dashboard language."""
    current = {**entry.data, **entry.options}
    language = str(current.get(CONF_UI_LANGUAGE, "auto") or "auto").lower()
    if language == "auto":
        language = "de" if str(getattr(hass.config, "language", "en") or "en").lower().startswith("de") else "en"
    return AMS_OPTIONS if language == "de" else AMS_OPTIONS_EN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            PrinterControlCenterSpeedSelect(coordinator, entry),
            PrinterControlCenterAmsTypeSelect(coordinator, entry),
        ]
    )


class PrinterControlCenterSpeedSelect(PrinterControlCenterPrinterEntity, SelectEntity):
    _attr_name = "Printing speed"
    _attr_options = list(SPEEDS)

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_printing_speed"

    @property
    def current_option(self):
        raw = self.coordinator.snapshot.value("spd_lvl", default=2)
        try:
            return REVERSE.get(int(raw), "standard")
        except (TypeError, ValueError):
            return "standard"

    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(
            self.coordinator.publish,
            {"print": {"sequence_id": "0", "command": "print_speed", "param": str(SPEEDS[option])}},
        )


class PrinterControlCenterAmsTypeSelect(PrinterControlCenterPrinterEntity, SelectEntity):
    _attr_name = "AMS configuration"

    @property
    def options(self) -> list[str]:
        return list(_ams_labels(self.entry, self.hass).values())

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.serial}_ams")},
            name=f"{self.serial} AMS",
            manufacturer="Bambu Lab compatible",
            model="AMS configuration",
            via_device=(DOMAIN, self.serial),
            configuration_url="https://github.com/Taracraft/3D-Printer-Control-Center",
        )

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self.serial}_ams_configuration"

    @property
    def current_option(self):
        current = str({**self.entry.data, **self.entry.options}.get(CONF_AMS_TYPE, "auto"))
        labels = _ams_labels(self.entry, self.hass)
        return labels.get(current, labels["auto"])

    async def async_select_option(self, option: str) -> None:
        reverse = {label: key for key, label in _ams_labels(self.entry, self.hass).items()}
        selected = reverse[option]
        options = {**self.entry.options, CONF_AMS_TYPE: selected}
        self.hass.config_entries.async_update_entry(self.entry, options=options)