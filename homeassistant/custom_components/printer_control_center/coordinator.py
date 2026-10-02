"""Coordinator for the 3D-Printer Control Center printer integration."""
from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ACCESS_CODE,
    CONF_ACCESS_TOKEN,
    CONF_AUTO_DISCOVER_IP,
    CONF_CLOUD_UID,
    CONF_DISCOVERY_HOSTS,
    CONF_DISCOVERY_PORTS,
    CONF_DISCOVERY_SUBNETS,
    CONF_HOST,
    CONF_MODE,
    CONF_REGION,
    CONF_RESCAN_ON_DISCONNECT,
    CONF_SCAN_BROADCAST,
    CONF_SCAN_CONNECTIONS,
    CONF_SCAN_MAX_HOSTS,
    CONF_SCAN_NEIGHBORS,
    CONF_SCAN_PROFILE,
    CONF_SCAN_ROUTES,
    CONF_SCAN_TIMEOUT_MS,
    CONF_SCAN_WORKERS,
    CONF_SERIAL,
    CONF_TLS_INSECURE,
    DOMAIN,
    MODE_CLOUD,
    MODE_HYBRID,
    MODE_LAN,
    REGION_CHINA,
)
from .discovery import ScanReport, advanced_scan
from .models import PrinterSnapshot
from .mqtt_client import PrinterMqttClient
from .camera_native import NativePrinterCameraClient
from .capabilities import camera_capability, effective_camera_mode
from .const import CAMERA_MODE_CHAMBER_IMAGE_6000, CAMERA_MODE_DISABLED, CAMERA_MODE_RTSPS_322

_LOGGER = logging.getLogger(__name__)


class PrinterControlCenterCoordinator(DataUpdateCoordinator[PrinterSnapshot]):
    """MQTT, telemetry and endpoint discovery coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"3D-Printer Control Center {entry.data[CONF_SERIAL]}",
        )
        self.entry = entry
        self.config = {**entry.data, **entry.options}
        self.serial = str(self.config[CONF_SERIAL])
        self.snapshot = PrinterSnapshot()
        self.data = self.snapshot
        self._clients: list[PrinterMqttClient] = []
        self._connected_transports: set[str] = set()
        self._rescan_scheduled = False
        self.camera_client: NativePrinterCameraClient | None = None
        self.camera_mode = CAMERA_MODE_DISABLED
        self.camera_capability = camera_capability(CAMERA_MODE_DISABLED)
        self._camera_sync_scheduled = False

        self.active_host = str(self.config.get(CONF_HOST, "")).strip()
        self.last_scan_report: ScanReport | None = None

    @property
    def manual_host(self) -> str:
        """Return the explicitly configured LAN IP. Manual configuration always wins."""
        return str(self.config.get(CONF_HOST, "")).strip()

    @property
    def camera_host(self) -> str:
        """Return the camera endpoint without allowing a scan to override manual IP."""
        return self.manual_host or self.active_host

    async def _async_create_client(self, **kwargs) -> PrinterMqttClient:
        return await self.hass.async_add_executor_job(
            partial(PrinterMqttClient, **kwargs)
        )

    def _scan_kwargs(self) -> dict[str, Any]:
        return {
            "serial": self.serial,
            "configured_host": str(self.config.get(CONF_HOST, "")),
            "explicit_hosts": str(self.config.get(CONF_DISCOVERY_HOSTS, "")),
            "subnet_cidrs": str(self.config.get(CONF_DISCOVERY_SUBNETS, "")),
            "custom_ports": str(self.config.get(CONF_DISCOVERY_PORTS, "")),
            "profile": str(self.config.get(CONF_SCAN_PROFILE, "balanced")),
            "timeout_ms": int(self.config.get(CONF_SCAN_TIMEOUT_MS, 300)),
            "workers": int(self.config.get(CONF_SCAN_WORKERS, 128)),
            "max_hosts": int(self.config.get(CONF_SCAN_MAX_HOSTS, 2048)),
            "include_broadcast": bool(self.config.get(CONF_SCAN_BROADCAST, True)),
            "include_neighbors": bool(self.config.get(CONF_SCAN_NEIGHBORS, True)),
            "include_connections": bool(self.config.get(CONF_SCAN_CONNECTIONS, True)),
            "include_routes": bool(self.config.get(CONF_SCAN_ROUTES, True)),
        }

    async def async_scan_network(self, persist_host: bool = False) -> ScanReport:
        """Execute endpoint discovery and optionally persist selected endpoint."""
        try:
            report = await self.hass.async_add_executor_job(
                partial(advanced_scan, **self._scan_kwargs())
            )
        except Exception as exc:
            _LOGGER.exception("Advanced endpoint scan failed")
            report = ScanReport(
                started_at="",
                finished_at="",
                profile=str(self.config.get(CONF_SCAN_PROFILE, "balanced")),
                scanned_hosts=0,
                candidates=[],
                error=str(exc),
            )

        self.last_scan_report = report

        if self.manual_host:
            # An explicitly configured LAN IP is authoritative. Discovery may
            # report candidates for diagnostics, but it must never override the
            # endpoint used for MQTT, camera or SD-card access.
            self.active_host = self.manual_host
        elif report.selected_host:
            self.active_host = report.selected_host

            if persist_host:
                options = {**self.entry.options, CONF_HOST: report.selected_host}
                self.hass.config_entries.async_update_entry(self.entry, options=options)

        self.async_set_updated_data(self.snapshot)
        return report

    async def _async_prepare_endpoint(self) -> None:
        """Prefer a validated endpoint before starting MQTT."""
        mode = self.config[CONF_MODE]
        if mode not in (MODE_LAN, MODE_HYBRID):
            return

        self.active_host = self.manual_host

        # Manual IP always wins. Automatic discovery is an optional fallback
        # because broadcast/route scans are not reliable in every VLAN or VPN.
        if not self.active_host and bool(self.config.get(CONF_AUTO_DISCOVER_IP, False)):
            report = await self.async_scan_network(persist_host=False)
            if report.selected_host:
                self.active_host = report.selected_host

    async def async_start(self) -> None:
        mode = self.config[CONF_MODE]
        tls_insecure = bool(self.config.get(CONF_TLS_INSECURE, True))

        await self._async_prepare_endpoint()

        if mode in (MODE_LAN, MODE_HYBRID):
            if not self.active_host:
                _LOGGER.error("No LAN endpoint available for %s", self.serial)
            else:
                self._clients.append(
                    await self._async_create_client(
                        host=self.active_host,
                        port=8883,
                        username="bblp",
                        password=str(self.config[CONF_ACCESS_CODE]),
                        serial=self.serial,
                        transport_name="lan",
                        tls_insecure=tls_insecure,
                        on_telemetry=self._telemetry_from_thread,
                        on_connected=self._connected_from_thread,
                        on_disconnected=self._disconnected_from_thread,
                    )
                )

        if mode in (MODE_CLOUD, MODE_HYBRID):
            uid = str(self.config[CONF_CLOUD_UID])
            region = str(self.config[CONF_REGION])
            cloud_host = (
                "cn.mqtt.bambulab.com"
                if region == REGION_CHINA
                else "us.mqtt.bambulab.com"
            )
            self._clients.append(
                await self._async_create_client(
                    host=cloud_host,
                    port=8883,
                    username=f"u_{uid}",
                    password=str(self.config[CONF_ACCESS_TOKEN]),
                    serial=self.serial,
                    transport_name="cloud",
                    tls_insecure=False,
                    on_telemetry=self._telemetry_from_thread,
                    on_connected=self._connected_from_thread,
                    on_disconnected=self._disconnected_from_thread,
                )
            )

        for client in self._clients:
            await self.hass.async_add_executor_job(client.start)

        await self._async_sync_camera()


    def _effective_camera_mode(self) -> str:
        model_hint = " ".join(
            str(value or "")
            for value in (
                getattr(self.snapshot, "printer_model", ""),
                self.config.get("printer_name", ""),
                self.config.get(CONF_SERIAL, ""),
            )
        )
        return effective_camera_mode(self.config, model_hint)

    def camera_status(self) -> dict[str, Any]:
        """Return sanitized camera capability status for entities and sensors."""
        mode = self._effective_camera_mode()
        capability = camera_capability(mode)
        host = self.camera_host
        status: dict[str, Any] = {
            "camera_mode": mode,
            "camera_transport": capability.transport,
            "camera_label": capability.label,
            "camera_port": capability.port or "",
            "camera_host": host,
            "camera_available": False,
            "camera_connected": False,
            "camera_last_error": "",
        }
        if mode == CAMERA_MODE_RTSPS_322:
            status["camera_available"] = bool(host and self.config.get(CONF_ACCESS_CODE))
        elif mode == CAMERA_MODE_CHAMBER_IMAGE_6000 and self.camera_client is not None:
            runtime = self.camera_client.runtime_status()
            status.update({
                "camera_available": True,
                "camera_connected": runtime.connected,
                "camera_last_error": runtime.last_error,
            })
        return status

    async def _async_sync_camera(self) -> None:
        """Start the native TCP-6000 reader only for compatible model families."""
        self._camera_sync_scheduled = False
        mode = self._effective_camera_mode()
        capability = camera_capability(mode)
        self.camera_mode = mode
        self.camera_capability = capability

        wants_native = mode == CAMERA_MODE_CHAMBER_IMAGE_6000
        if not wants_native:
            if self.camera_client is not None:
                await self.hass.async_add_executor_job(self.camera_client.stop)
                self.camera_client = None
                self.async_set_updated_data(self.snapshot)
            return

        camera_host = self.camera_host
        if not camera_host:
            return

        tls_insecure = bool(self.config.get(CONF_TLS_INSECURE, True))
        if self.camera_client is None or self.camera_client.host != camera_host:
            if self.camera_client is not None:
                await self.hass.async_add_executor_job(self.camera_client.stop)
            self.camera_client = NativePrinterCameraClient(
                host=camera_host,
                access_code=str(self.config[CONF_ACCESS_CODE]),
                tls_insecure=tls_insecure,
                on_state_change=self._camera_state_from_thread,
            )
            await self.hass.async_add_executor_job(self.camera_client.start)
            self.async_set_updated_data(self.snapshot)

    def _schedule_camera_sync(self) -> None:
        if self._camera_sync_scheduled:
            return
        self._camera_sync_scheduled = True
        self.hass.async_create_task(self._async_sync_camera())

    async def async_stop(self) -> None:
        if self.camera_client is not None:
            await self.hass.async_add_executor_job(self.camera_client.stop)
            self.camera_client = None

        for client in self._clients:
            await self.hass.async_add_executor_job(client.stop)
        self._clients.clear()

    async def async_scan_and_reload(self) -> ScanReport:
        """Scan endpoint candidates and reload if the selected host changed."""
        previous = self.active_host
        report = await self.async_scan_network(persist_host=True)

        if report.selected_host and report.selected_host != previous:
            _LOGGER.info(
                "Endpoint changed for %s: %s -> %s",
                self.serial,
                previous,
                report.selected_host,
            )

        return report

    def request_full_status(self) -> None:
        """Request a fresh status through the preferred connected transport."""
        errors: list[str] = []
        for name in ("lan", "cloud"):
            for client in self._clients:
                if client.transport_name != name or name not in self._connected_transports:
                    continue
                try:
                    client.request_full_status()
                    return
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
        if errors:
            raise RuntimeError("Unable to request printer status: " + "; ".join(errors))

    def publish(self, payload: dict[str, Any]) -> None:
        """Send command through preferred transport: LAN first, then Cloud."""
        errors: list[str] = []
        for name in ("lan", "cloud"):
            for client in self._clients:
                if client.transport_name != name or name not in self._connected_transports:
                    continue
                try:
                    client.publish(payload)
                    return
                except Exception as exc:
                    errors.append(f"{name}: {exc}")
        raise RuntimeError("No connected MQTT transport available: " + "; ".join(errors))

    @callback
    def _handle_telemetry(self, payload: dict[str, Any], transport: str) -> None:
        if self.snapshot.transport == "lan" and transport == "cloud":
            return
        previous_camera_mode = self.camera_mode
        self.snapshot.update(payload, transport)
        self.async_set_updated_data(self.snapshot)
        if self._effective_camera_mode() != previous_camera_mode:
            self._schedule_camera_sync()

    def _telemetry_from_thread(self, payload: dict[str, Any], transport: str) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_telemetry, payload, transport)

    @callback
    def _handle_connected(self, transport: str) -> None:
        self._connected_transports.add(transport)
        self.snapshot.online = True
        if transport == "lan" or self.snapshot.transport == "disconnected":
            self.snapshot.transport = transport
        self.async_set_updated_data(self.snapshot)

    def _connected_from_thread(self, transport: str) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_connected, transport)

    @callback
    def _handle_disconnected(self, transport: str) -> None:
        self._connected_transports.discard(transport)

        if not self._connected_transports:
            self.snapshot.online = False
            self.snapshot.transport = "disconnected"
        elif "lan" in self._connected_transports:
            self.snapshot.transport = "lan"
        else:
            self.snapshot.transport = "cloud"

        self.async_set_updated_data(self.snapshot)

        if (
            transport == "lan"
            and bool(self.config.get(CONF_RESCAN_ON_DISCONNECT, True))
            and bool(self.config.get(CONF_AUTO_DISCOVER_IP, False))
            and not self.manual_host
            and not self._rescan_scheduled
        ):
            self._rescan_scheduled = True
            self.hass.async_create_task(self._async_rescan_after_disconnect())

    async def _async_rescan_after_disconnect(self) -> None:
        try:
            await self.async_scan_and_reload()
        finally:
            self._rescan_scheduled = False

    def _disconnected_from_thread(self, transport: str) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_disconnected, transport)


    @callback
    def _handle_camera_state(self) -> None:
        """Publish safe camera status changes to interested entities."""
        self.async_set_updated_data(self.snapshot)

    def _camera_state_from_thread(self) -> None:
        """Move camera thread state changes into the HA event loop."""
        self.hass.loop.call_soon_threadsafe(self._handle_camera_state)