from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from ..mqtt_transport import BambuLanMqttTransport
from .commands import build_get_version, build_push_all
from .models import NetworkCommand, NetworkCommandResult


TelemetryCallback = Callable[[dict[str, Any]], None]
StatusCallback = Callable[[], None]
DisconnectCallback = Callable[[str], None]
ErrorCallback = Callable[[str], None]


class BambuNetworkPlugin:
    """Standalone Bambu LAN network plugin.

    The plugin owns MQTT transport, request/response correlation and raw JSON
    interpretation. The Studio provider consumes only normalized command results and
    telemetry callbacks.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        access_code: str,
        serial: str,
        tls_insecure: bool,
        on_telemetry: TelemetryCallback,
        on_connected: StatusCallback,
        on_disconnected: DisconnectCallback,
        on_error: ErrorCallback,
    ) -> None:
        self._on_telemetry = on_telemetry
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_error = on_error
        self._pending: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        self.transport = BambuLanMqttTransport(
            host=host,
            port=port,
            username=username,
            access_code=access_code,
            serial=serial,
            tls_insecure=tls_insecure,
            on_telemetry=self._handle_message,
            on_connected=self._handle_connected,
            on_disconnected=on_disconnected,
            on_error=on_error,
        )

    def start(self) -> None:
        self.transport.start()

    def stop(self) -> None:
        self.transport.stop()
        with self._pending_lock:
            self._pending.clear()

    def request_initial_state(self) -> None:
        self.submit(build_push_all(), wait_for_response=False)
        self.submit(build_get_version(), wait_for_response=False)

    def submit(
        self,
        command: NetworkCommand,
        *,
        wait_for_response: bool = True,
        response_timeout: float = 10.0,
    ) -> NetworkCommandResult:
        waiter: queue.Queue[dict[str, Any]] | None = None
        if wait_for_response:
            waiter = queue.Queue(maxsize=1)
            with self._pending_lock:
                if command.sequence_id in self._pending:
                    raise RuntimeError(
                        f"Duplicate sequence_id pending: {command.sequence_id}"
                    )
                self._pending[command.sequence_id] = waiter

        started = time.monotonic()
        try:
            publish_result = self.transport.publish(command.payload, command.qos)
            if not wait_for_response or waiter is None:
                return NetworkCommandResult(
                    section=command.section,
                    command=command.command,
                    sequence_id=command.sequence_id,
                    submitted=publish_result.submitted,
                    mqtt_confirmed=publish_result.confirmed,
                    response_received=False,
                    printer_accepted=False,
                    elapsed_seconds=time.monotonic() - started,
                )

            try:
                response = waiter.get(timeout=response_timeout)
            except queue.Empty:
                return NetworkCommandResult(
                    section=command.section,
                    command=command.command,
                    sequence_id=command.sequence_id,
                    submitted=publish_result.submitted,
                    mqtt_confirmed=publish_result.confirmed,
                    response_received=False,
                    printer_accepted=False,
                    reason=(
                        "Printer response timeout after "
                        f"{response_timeout:.1f} seconds"
                    ),
                    elapsed_seconds=time.monotonic() - started,
                )

            section_payload = self._response_section(response, command.section)
            result_value = self._string_value(section_payload.get("result"))
            reason = self._string_value(
                section_payload.get("reason")
                or section_payload.get("message")
                or section_payload.get("msg")
            )
            error_code = (
                section_payload.get("error_code")
                or section_payload.get("err_code")
                or section_payload.get("code")
            )
            accepted = self._is_accepted(section_payload, result_value, error_code)

            return NetworkCommandResult(
                section=command.section,
                command=command.command,
                sequence_id=command.sequence_id,
                submitted=publish_result.submitted,
                mqtt_confirmed=publish_result.confirmed,
                response_received=True,
                printer_accepted=accepted,
                result=result_value,
                reason=reason,
                error_code=error_code,
                response=response,
                elapsed_seconds=time.monotonic() - started,
            )
        finally:
            if wait_for_response:
                with self._pending_lock:
                    self._pending.pop(command.sequence_id, None)

    def _handle_connected(self) -> None:
        self._on_connected()
        try:
            self.request_initial_state()
        except Exception as exc:
            self._on_error(str(exc))

    def _handle_message(self, payload: dict[str, Any]) -> None:
        sequence_id = self._find_sequence_id(payload)
        if sequence_id:
            with self._pending_lock:
                waiter = self._pending.get(sequence_id)
            if waiter is not None:
                try:
                    waiter.put_nowait(payload)
                except queue.Full:
                    pass
        self._on_telemetry(payload)

    @staticmethod
    def _find_sequence_id(payload: dict[str, Any]) -> str | None:
        for value in payload.values():
            if not isinstance(value, dict):
                continue
            sequence_id = value.get("sequence_id")
            if sequence_id is not None:
                return str(sequence_id)
        return None

    @staticmethod
    def _response_section(
        payload: dict[str, Any],
        preferred_section: str,
    ) -> dict[str, Any]:
        preferred = payload.get(preferred_section)
        if isinstance(preferred, dict):
            return preferred
        for value in payload.values():
            if isinstance(value, dict):
                return value
        return {}

    @staticmethod
    def _string_value(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _is_accepted(
        section_payload: dict[str, Any],
        result_value: str | None,
        error_code: Any,
    ) -> bool:
        if error_code not in (None, 0, "0", ""):
            return False
        if result_value is not None:
            return result_value.lower() in {
                "success",
                "succeed",
                "ok",
                "accepted",
            }
        return section_payload.get("reason") in (None, "")
