"""Provider-neutral V6 runtime."""
from __future__ import annotations

from datetime import UTC, datetime
from collections.abc import Callable
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .bambu_direct_print import UploadedPrintArtifact
from .commands import PrinterCommandResult
from .const import (
    CONF_ACCESS_CODE,
    CONF_HOST,
    CONF_LAN_ENABLED,
    CONF_PRINTER_NAME,
    CONF_SERIAL,
    CONF_TLS_INSECURE,
    DEFAULT_PRINTER_NAME,
    DEFAULT_TLS_INSECURE,
)
from .jarvis_events import JarvisEventBridge
from .job_history_v2 import JobHistoryV2
from .models import PrinterProvider, PrinterSnapshot


class Ultimate3DStudioRuntime:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.started_at: datetime | None = None
        self._providers: dict[str, PrinterProvider] = {}
        self.jobs = JobHistoryV2(hass, entry.entry_id)
        self.jarvis_events = JarvisEventBridge(hass)

    def _configure_providers(self) -> None:
        cfg = {**self.entry.data, **self.entry.options}
        if not bool(cfg.get(CONF_LAN_ENABLED, False)):
            return

        host = str(cfg.get(CONF_HOST, "")).strip()
        serial = str(cfg.get(CONF_SERIAL, "")).strip()
        credential = str(cfg.get(CONF_ACCESS_CODE, "")).strip()
        if not all((host, serial, credential)):
            return

        from .provider_bambu_lan_v2 import BambuLanProviderV2

        provider = BambuLanProviderV2(
            self.hass,
            host=host,
            serial=serial,
            access_code=credential,
            printer_name=str(cfg.get(CONF_PRINTER_NAME, "")).strip()
            or DEFAULT_PRINTER_NAME,
            tls_insecure=bool(
                cfg.get(CONF_TLS_INSECURE, DEFAULT_TLS_INSECURE),
            ),
        )
        self._providers[provider.provider_id] = provider

    @property
    def provider_count(self) -> int:
        return len(self._providers)

    @property
    def is_ready(self) -> bool:
        return self.started_at is not None

    async def async_start(self) -> None:
        if self.started_at is not None:
            return
        if not self._providers:
            await self.hass.async_add_executor_job(self._configure_providers)
        await self.jobs.async_load()
        for provider in self._providers.values():
            await provider.async_start()
        self.jarvis_events.reset()
        self.started_at = datetime.now(UTC)

    async def async_stop(self) -> None:
        for provider in reversed(tuple(self._providers.values())):
            await provider.async_stop()
        self.jarvis_events.reset()
        self.started_at = None

    async def async_printers(self) -> tuple[PrinterSnapshot, ...]:
        items: list[PrinterSnapshot] = []
        for provider in self._providers.values():
            items.extend(await provider.async_printers())
        snapshots = tuple(items)
        await self.jobs.async_observe(snapshots)
        self.jarvis_events.observe(snapshots)
        return snapshots

    async def async_printer(self, printer_id: str) -> PrinterSnapshot | None:
        return next(
            (
                item
                for item in await self.async_printers()
                if item.printer_id == printer_id
            ),
            None,
        )

    async def async_command(
        self,
        printer_id: str,
        command: str,
        *,
        speed_level: int | None = None,
    ) -> PrinterCommandResult | None:
        for provider in self._providers.values():
            result = await provider.async_command(printer_id, command, speed_level=speed_level)
            if result is not None:
                return result
        return None

    async def async_upload_print_artifact(
        self,
        printer_id: str,
        filename: str,
        data: bytes,
        *,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> UploadedPrintArtifact | None:
        for provider in self._providers.values():
            operation = getattr(provider, "async_upload_print_artifact", None)
            if not callable(operation):
                continue
            result = await operation(
                printer_id,
                filename,
                data,
                on_progress=on_progress,
            )
            if result is not None:
                return result
        return None

    async def async_delete_uploaded_artifact(
        self,
        printer_id: str,
        filename: str,
    ) -> bool | None:
        for provider in self._providers.values():
            operation = getattr(provider, "async_delete_uploaded_artifact", None)
            if not callable(operation):
                continue
            result = await operation(printer_id, filename)
            if result is not None:
                return bool(result)
        return None

    async def async_start_uploaded_artifact(
        self,
        uploaded: UploadedPrintArtifact,
        *,
        use_ams: bool,
        ams_mapping: list[int] | None,
        bed_leveling: bool,
        flow_cali: bool,
        vibration_cali: bool,
        timelapse: bool,
    ) -> dict[str, Any] | None:
        for provider in self._providers.values():
            operation = getattr(provider, "async_start_uploaded_artifact", None)
            if not callable(operation):
                continue
            result = await operation(
                uploaded,
                use_ams=use_ams,
                ams_mapping=ams_mapping,
                bed_leveling=bed_leveling,
                flow_cali=flow_cali,
                vibration_cali=vibration_cali,
                timelapse=timelapse,
            )
            if result is not None:
                return result
        return None

    def health(self) -> dict[str, Any]:
        providers = []
        for provider in self._providers.values():
            diagnostic = getattr(provider, "diagnostic_state", None)
            providers.append(
                diagnostic()
                if callable(diagnostic)
                else {"provider_id": provider.provider_id}
            )
        jobs = self.jobs.as_dict()
        return {
            "entry_id": self.entry.entry_id,
            "title": self.entry.title,
            "ready": self.is_ready,
            "provider_count": self.provider_count,
            "providers": providers,
            "job_current_count": jobs["current_count"],
            "job_queue_count": jobs["queue_count"],
            "job_history_count": jobs["history_count"],
            "jarvis_event_bridge": True,
            "started_at": self.started_at.isoformat() if self.started_at else None,
        }