"""Standalone Bambu LAN provider for Ultimate 3D Studio V6."""

from __future__ import annotations

from functools import partial
import logging
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback

from .audit_log import get_audit_log
from .bambu_direct_print import (
    UploadedPrintArtifact,
    build_project_file_command,
    delete_remote_file,
    upload_gcode_3mf,
)
from .commands import PrinterCommandResult
from .const import MQTT_PORT, MQTT_USERNAME
from .models import PrinterSnapshot
from .slicer_execution_contract import a1_hardware_limits
from .network_plugin import (
    BambuNetworkPlugin,
    NetworkCommand,
    NetworkCommandResult,
    build_ams_filament_setting,
    build_print_control,
    build_print_speed,
)
from .printer_issues import issue_signature
from .telemetry import BambuTelemetryState

_LOGGER = logging.getLogger(__name__)


class BambuLanProvider:
    provider_id = "bambu_lan"

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        host: str,
        serial: str,
        access_code: str,
        printer_name: str,
        tls_insecure: bool,
    ) -> None:
        self.hass = hass
        self.host = host
        self.serial = serial
        self.access_code = access_code
        self.printer_name = printer_name
        self.tls_insecure = tls_insecure
        self.telemetry = BambuTelemetryState()
        self.connected = False
        self.last_error: str | None = None
        self.network: BambuNetworkPlugin | None = None
        self.last_command_result: NetworkCommandResult | None = None
        self.last_project_file_request: dict[str, Any] | None = None
        self._last_issue_signature = ""
        self._last_issues: list[dict[str, Any]] = []

    async def async_start(self) -> None:
        if self.network is not None:
            return

        self.network = await self.hass.async_add_executor_job(
            partial(
                BambuNetworkPlugin,
                host=self.host,
                port=MQTT_PORT,
                username=MQTT_USERNAME,
                access_code=self.access_code,
                serial=self.serial,
                tls_insecure=self.tls_insecure,
                on_telemetry=self._telemetry_thread,
                on_connected=self._connected_thread,
                on_disconnected=self._disconnected_thread,
                on_error=self._error_thread,
            )
        )
        await self.hass.async_add_executor_job(self.network.start)

    async def async_stop(self) -> None:
        network = self.network
        self.network = None
        self.connected = False
        if network is not None:
            await self.hass.async_add_executor_job(network.stop)

    async def async_printers(self) -> tuple[PrinterSnapshot, ...]:
        issues = self.telemetry.issues
        return (
            PrinterSnapshot(
                printer_id=self.serial,
                name=self.printer_name,
                provider=self.provider_id,
                model=self.telemetry.model,
                serial=self.serial,
                host=self.host,
                connection_state="connected" if self.connected else "disconnected",
                printer_state=(
                    self.telemetry.printer_state
                    if self.telemetry.updated_at
                    else "unknown"
                ),
                progress=self.telemetry.progress,
                current_file=self.telemetry.current_file,
                nozzle_temperature=self.telemetry.nozzle_temperature,
                nozzle_target_temperature=self.telemetry.nozzle_target_temperature,
                bed_temperature=self.telemetry.bed_temperature,
                bed_target_temperature=self.telemetry.bed_target_temperature,
                current_layer=self.telemetry.current_layer,
                total_layers=self.telemetry.total_layers,
                speed_level=self.telemetry.speed_level,
                wifi_signal=self.telemetry.wifi_signal,
                error_code=(
                    self.telemetry.error_code
                    if self.telemetry.error_code is not None
                    else (
                        self.last_command_result.error_code
                        if self.last_command_result is not None
                        and not self.last_command_result.printer_accepted
                        else None
                    )
                ),
                error_message=(
                    self.telemetry.error_message
                    or self.last_error
                    or (
                        self.last_command_result.reason
                        if self.last_command_result is not None
                        and not self.last_command_result.printer_accepted
                        else None
                    )
                ),
                hms=self.telemetry.hms,
                issues=issues,
                ams=self.telemetry.ams,
                updated_at=self.telemetry.updated_at_iso,
            ),
        )

    async def _async_submit(
        self,
        command: NetworkCommand,
        *,
        timeout: float = 10.0,
    ) -> NetworkCommandResult:
        if not self.connected:
            raise RuntimeError("Printer is not connected")
        if self.network is None:
            raise RuntimeError("Bambu network plugin is not available")

        result = await self.hass.async_add_executor_job(
            partial(
                self.network.submit,
                command,
                wait_for_response=True,
                response_timeout=timeout,
            )
        )
        self.last_command_result = result

        if not result.printer_accepted:
            details = []
            if result.result:
                details.append(f"result={result.result}")
            if result.reason:
                details.append(f"reason={result.reason}")
            if result.error_code is not None:
                details.append(f"error_code={result.error_code}")
            if not result.response_received:
                details.append("no printer response")
            detail_text = ", ".join(details) or "printer rejected command"
            raise RuntimeError(
                f"Bambu command {command.command} was not accepted: {detail_text}"
            )

        return result

    async def async_command(
        self,
        printer_id: str,
        command: str,
        *,
        speed_level: int | None = None,
    ) -> PrinterCommandResult | None:
        if printer_id != self.serial:
            return None

        network_command = build_print_speed(speed_level) if command == "speed" and speed_level is not None else build_print_control(command)
        result = await self._async_submit(network_command)
        return PrinterCommandResult(
            printer_id=self.serial,
            provider=self.provider_id,
            command=command,
            sequence_id=result.sequence_id,
            accepted=result.printer_accepted,
        )

    async def async_set_filament_color(
        self,
        printer_id: str,
        *,
        ams_id: int,
        tray_id: int,
        tray_info_idx: str,
        tray_color: str,
        nozzle_temp_min: int,
        nozzle_temp_max: int,
        tray_type: str,
    ) -> dict[str, Any] | None:
        if printer_id != self.serial:
            return None
        result = await self._async_submit(
            build_ams_filament_setting(
                ams_id=ams_id,
                tray_id=tray_id,
                tray_info_idx=tray_info_idx,
                tray_color=tray_color,
                nozzle_temp_min=nozzle_temp_min,
                nozzle_temp_max=nozzle_temp_max,
                tray_type=tray_type,
            ),
            timeout=15.0,
        )
        return {
            "printer_id": self.serial,
            "provider": self.provider_id,
            "command": "ams_filament_setting",
            "sequence_id": result.sequence_id,
            "accepted": result.printer_accepted,
            "mqtt_puback_received": result.mqtt_puback_received,
            "transport_delivered": result.transport_delivered,
            "response_received": result.response_received,
            "result": result.result,
            "reason": result.reason,
            "error_code": result.error_code,
        }

    async def async_upload_print_artifact(
        self,
        printer_id: str,
        filename: str,
        data: bytes,
        *,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> UploadedPrintArtifact | None:
        if printer_id != self.serial:
            return None
        if not self.connected:
            raise RuntimeError("Printer is not connected")

        return await self.hass.async_add_executor_job(
            partial(
                upload_gcode_3mf,
                host=self.host,
                access_code=self.access_code,
                printer_id=self.serial,
                filename=filename,
                data=data,
                tls_insecure=self.tls_insecure,
                on_progress=on_progress,
                hardware_limits=a1_hardware_limits(self.telemetry.model),
                printer_model=self.telemetry.model,
            )
        )

    async def async_delete_uploaded_artifact(
        self,
        printer_id: str,
        filename: str,
    ) -> bool | None:
        if printer_id != self.serial:
            return None

        return await self.hass.async_add_executor_job(
            partial(
                delete_remote_file,
                host=self.host,
                access_code=self.access_code,
                filename=filename,
                tls_insecure=self.tls_insecure,
            )
        )

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
        if uploaded.printer_id != self.serial:
            return None

        payload = build_project_file_command(
            uploaded,
            use_ams=use_ams,
            ams_mapping=ams_mapping,
            bed_leveling=bed_leveling,
            flow_cali=flow_cali,
            vibration_cali=vibration_cali,
            timelapse=timelapse,
        )
        print_payload = payload.get("print")
        if not isinstance(print_payload, dict):
            raise RuntimeError("Invalid project_file payload")

        sequence_id = str(print_payload.get("sequence_id", "")).strip()
        if not sequence_id:
            raise RuntimeError("project_file payload has no sequence_id")

        mapping_value = print_payload.get("ams_mapping")
        self.last_project_file_request = {
            "printer_id": self.serial,
            "remote_filename": uploaded.remote_filename,
            "url": str(print_payload.get("url", "")),
            "param": str(print_payload.get("param", "")),
            "use_ams": bool(print_payload.get("use_ams", False)),
            "ams_mapping": list(mapping_value) if isinstance(mapping_value, list) else [],
        }

        result = await self._async_submit(
            NetworkCommand(
                section="print",
                command="project_file",
                sequence_id=sequence_id,
                payload=payload,
                qos=0,
            ),
            timeout=20.0,
        )
        return {
            "printer_id": self.serial,
            "provider": self.provider_id,
            "command": "project_file",
            "sequence_id": result.sequence_id,
            "accepted": result.printer_accepted,
            "remote_filename": uploaded.remote_filename,
            "url": self.last_project_file_request["url"],
            "use_ams": self.last_project_file_request["use_ams"],
            "ams_mapping": self.last_project_file_request["ams_mapping"],
            "mqtt_puback_received": result.mqtt_puback_received,
            "transport_delivered": result.transport_delivered,
            "response_received": result.response_received,
            "result": result.result,
            "reason": result.reason,
            "error_code": result.error_code,
        }

    def diagnostic_state(self) -> dict[str, Any]:
        ams = self.telemetry.ams
        issues = self.telemetry.issues
        last_command = self.last_command_result
        return {
            "provider_id": self.provider_id,
            "host": self.host,
            "serial": self.serial,
            "connected": self.connected,
            "last_error": self.last_error,
            "error_code": self.telemetry.error_code,
            "error_message": self.telemetry.error_message,
            "active_issue_count": len(issues),
            "active_issues": issues,
            "hms": self.telemetry.hms,
            "network_plugin": {
                "name": "bambu_lan_json",
                "separate_module": True,
                "mqtt_port": MQTT_PORT,
                "request_response_correlation": True,
                "printer_result_required": True,
            },
            "last_project_file_request": self.last_project_file_request,
            "last_command": None
            if last_command is None
            else {
                "section": last_command.section,
                "command": last_command.command,
                "sequence_id": last_command.sequence_id,
                "submitted": last_command.submitted,
                "mqtt_puback_received": last_command.mqtt_puback_received,
                "transport_delivered": last_command.transport_delivered,
                "response_received": last_command.response_received,
                "printer_accepted": last_command.printer_accepted,
                "result": last_command.result,
                "reason": last_command.reason,
                "error_code": last_command.error_code,
                "elapsed_seconds": last_command.elapsed_seconds,
                "response": last_command.response,
            },
            "direct_print_transport": {
                "ftps_port": 990,
                "mqtt_port": MQTT_PORT,
                "upload_supported": True,
                "start_supported": True,
                "publish_confirmation": "printer_json_response_required",
            },
            "ams_available": ams.get("available", False),
            "ams_kind": ams.get("kind"),
            "ams_unit_count": ams.get("unit_count", 0),
            "ams_slot_count": ams.get("slot_count", 0),
            "ams_active_tray": ams.get("active_tray"),
            "ams": ams,
            "updated_at": self.telemetry.updated_at_iso,
        }

    @callback
    def _handle_telemetry(self, payload: dict[str, Any]) -> None:
        self.telemetry.update(payload)
        self.connected = True
        self.last_error = None
        self._publish_issue_transition()

    def _publish_issue_transition(self) -> None:
        issues = self.telemetry.issues
        signature = issue_signature(issues)
        if signature == self._last_issue_signature:
            return

        previous_issues = self._last_issues
        self._last_issue_signature = signature
        self._last_issues = [dict(item) for item in issues]

        if issues:
            codes = ", ".join(str(item.get("code") or "unbekannt") for item in issues)
            messages = " | ".join(str(item.get("message") or "") for item in issues if item.get("message"))
            highest = "error" if any(item.get("severity") == "error" for item in issues) else "warning"
            log_message = f"Bambu-Druckerstörung aktiv: {codes}"
            if messages:
                log_message += f" - {messages}"
            if highest == "error":
                _LOGGER.error(log_message)
            else:
                _LOGGER.warning(log_message)
            self.hass.async_create_task(
                get_audit_log(self.hass).async_append(
                    category="Druck",
                    component="bambu_lan_issue_monitor",
                    event="printer_issue_activated",
                    status=highest,
                    source="bambu_lan_telemetry",
                    printer_id=self.serial,
                    details={
                        "printer_name": self.printer_name,
                        "printer_state": self.telemetry.printer_state,
                        "issues": issues,
                    },
                )
            )
            return

        if previous_issues:
            codes = ", ".join(str(item.get("code") or "unbekannt") for item in previous_issues)
            _LOGGER.info("Bambu-Druckerstörung behoben: %s", codes)
            self.hass.async_create_task(
                get_audit_log(self.hass).async_append(
                    category="Druck",
                    component="bambu_lan_issue_monitor",
                    event="printer_issue_resolved",
                    status="success",
                    source="bambu_lan_telemetry",
                    printer_id=self.serial,
                    details={
                        "printer_name": self.printer_name,
                        "printer_state": self.telemetry.printer_state,
                        "resolved_issues": previous_issues,
                    },
                )
            )

    def _telemetry_thread(self, payload: dict[str, Any]) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_telemetry, payload)

    @callback
    def _handle_connected(self) -> None:
        self.connected = True
        self.last_error = None

    def _connected_thread(self) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_connected)

    @callback
    def _handle_disconnected(self, reason: str) -> None:
        self.connected = False
        self.last_error = reason or None

    def _disconnected_thread(self, reason: str) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_disconnected, reason)

    @callback
    def _handle_error(self, message: str) -> None:
        self.last_error = message

    def _error_thread(self, message: str) -> None:
        self.hass.loop.call_soon_threadsafe(self._handle_error, message)
