"""Runtime lookup for provider-owned Studio printer storage."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_CODE,
    CONF_HOST,
    CONF_LAN_ENABLED,
    CONF_SERIAL,
    CONF_TLS_INSECURE,
    DATA_RUNTIMES,
    DEFAULT_TLS_INSECURE,
    DOMAIN,
)
from .printer_storage import BambuPrinterStorage, PrinterStorageError
from .runtime import Ultimate3DStudioRuntime


def _runtimes(hass: HomeAssistant) -> Iterable[Ultimate3DStudioRuntime]:
    value = hass.data.get(DOMAIN, {}).get(DATA_RUNTIMES, {})
    if not isinstance(value, dict):
        return ()
    return tuple(
        runtime
        for runtime in value.values()
        if isinstance(runtime, Ultimate3DStudioRuntime)
    )


async def async_storage_for_printer(
    hass: HomeAssistant,
    printer_id: str,
) -> BambuPrinterStorage:
    requested = str(printer_id or "").strip()
    if not requested:
        raise PrinterStorageError("Drucker-ID fehlt.")

    for runtime in _runtimes(hass):
        config = {**runtime.entry.data, **runtime.entry.options}
        if not bool(config.get(CONF_LAN_ENABLED, False)):
            continue
        serial = str(config.get(CONF_SERIAL, "")).strip()
        if serial != requested:
            continue
        printer = await runtime.async_printer(requested)
        if printer is None:
            raise PrinterStorageError("Der Drucker ist nicht verfügbar.")
        if printer.connection_state != "connected":
            raise PrinterStorageError("Der Drucker ist nicht verbunden.")
        host = str(config.get(CONF_HOST, "")).strip()
        access_code = str(config.get(CONF_ACCESS_CODE, "")).strip()
        if not host or not access_code:
            raise PrinterStorageError("Host oder Zugangscode des Druckers fehlt.")
        return BambuPrinterStorage(
            host=host,
            access_code=access_code,
            tls_insecure=bool(
                config.get(CONF_TLS_INSECURE, DEFAULT_TLS_INSECURE),
            ),
        )

    raise PrinterStorageError("Kein passender Studio-Bambu-Drucker wurde gefunden.")


async def async_printer_storage_summary(
    hass: HomeAssistant,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for runtime in _runtimes(hass):
        for printer in await runtime.async_printers():
            items.append({
                "printer_id": printer.printer_id,
                "printer_name": printer.name,
                "provider": printer.provider,
                "connection_state": printer.connection_state,
                "storage_supported": printer.provider == "bambu_lan",
            })
    return items
