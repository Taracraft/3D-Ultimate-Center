"""Bambu LAN JSON protocol layer with request/response correlation."""

from __future__ import annotations

import copy
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from .mqtt_transport import BambuLanMqttTransport, MqttPublishResult


SUCCESS_RESULTS = {"success", "ok", "accepted", "done"}
FAILURE_RESULTS = {"fail", "failed", "error", "rejected", "deny", "denied"}

_sequence_lock = threading.Lock()
_sequence_value = int(time.time() * 1000) % 2_000_000_000


@dataclass(frozen=True, slots=True)
class NetworkCommand:
    section: str
    command: str
    sequence_id: str
    payload: dict[str, Any]
    qos: int = 1


@dataclass(frozen=True, slots=True)
class NetworkCommandResult:
    section: str
    command: str
    sequence_id: str
    submitted: bool
    mqtt_puback_received: bool
    transport_delivered: bool
    response_received: bool
    printer_accepted: bool
    result: str | None
    reason: str | None
    error_code: int | None
    response: dict[str, Any] | None
    elapsed_seconds: float

    @property
    def mqtt_confirmed(self) -> bool:
        """Backward-compatible alias for the former diagnostic field."""
        return self.mqtt_puback_received


@dataclass(slots=True)
class _PendingRequest:
    command: NetworkCommand
    event: threading.Event
    response: dict[str, Any] | None = None


def create_sequence_id() -> str:
    global _sequence_value

    with _sequence_lock:
        _sequence_value += 1
        if _sequence_value >= 2_000_000_000:
            _sequence_value = 1
        return str(_sequence_value)


def build_print_control(command: str) -> NetworkCommand:
    normalized = command.strip().lower()
    if normalized not in {"pause", "resume", "stop"}:
        raise ValueError(f"Unsupported print control command: {command}")

    sequence_id = create_sequence_id()
    payload = {
        "print": {
            "sequence_id": sequence_id,
            "command": normalized,
            "param": "",
        }
    }
    return NetworkCommand(
        section="print",
        command=normalized,
        sequence_id=sequence_id,
        payload=payload,
        qos=1,
    )


def build_print_speed(level: int) -> NetworkCommand:
    if level not in {1, 2, 3, 4}:
        raise ValueError(f"Unsupported Bambu print speed level: {level}")
    sequence_id = create_sequence_id()
    return NetworkCommand(
        section="print",
        command="print_speed",
        sequence_id=sequence_id,
        payload={"print": {"sequence_id": sequence_id, "command": "print_speed", "param": str(level)}},
        qos=1,
    )


def build_gcode_line(gcode: str) -> NetworkCommand:
    normalized = gcode.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized.strip():
        raise ValueError("G-code must not be empty")

    normalized = normalized.rstrip("\n") + "\n"
    sequence_id = create_sequence_id()
    payload = {
        "print": {
            "sequence_id": sequence_id,
            "command": "gcode_line",
            "param": normalized,
        }
    }
    return NetworkCommand(
        section="print",
        command="gcode_line",
        sequence_id=sequence_id,
        payload=payload,
        qos=1,
    )


def build_get_version() -> NetworkCommand:
    sequence_id = create_sequence_id()
    payload = {
        "info": {
            "sequence_id": sequence_id,
            "command": "get_version",
        }
    }
    return NetworkCommand(
        section="info",
        command="get_version",
        sequence_id=sequence_id,
        payload=payload,
        qos=1,
    )


def build_pushall() -> NetworkCommand:
    sequence_id = create_sequence_id()
    payload = {
        "pushing": {
            "sequence_id": sequence_id,
            "command": "pushall",
            "version": 1,
            "push_target": 1,
        }
    }
    return NetworkCommand(
        section="pushing",
        command="pushall",
        sequence_id=sequence_id,
        payload=payload,
        qos=0,
    )


class BambuNetworkPlugin:
    """Own Bambu JSON driver layered on the low-level MQTT transport."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        access_code: str,
        serial: str,
        tls_insecure: bool,
        on_telemetry: Callable[[dict[str, Any]], None],
        on_connected: Callable[[], None],
        on_disconnected: Callable[[str], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._on_telemetry = on_telemetry
        self._on_connected = on_connected
        self._on_disconnected = on_disconnected
        self._on_error = on_error
        self._pending_lock = threading.Lock()
        self._pending: dict[tuple[str, str, str], _PendingRequest] = {}
        self._last_response_lock = threading.Lock()
        self._last_response: dict[str, Any] | None = None

        self.transport = BambuLanMqttTransport(
            host=host,
            port=port,
            username=username,
            access_code=access_code,
            serial=serial,
            tls_insecure=tls_insecure,
            on_telemetry=self._handle_message,
            on_connected=self._handle_connected,
            on_disconnected=self._handle_disconnected,
            on_error=self._handle_error,
        )

    @property
    def last_response(self) -> dict[str, Any] | None:
        with self._last_response_lock:
            return copy.deepcopy(self._last_response)

    def start(self) -> None:
        self.transport.start()

    def stop(self) -> None:
        with self._pending_lock:
            pending = tuple(self._pending.values())
            self._pending.clear()
        for request in pending:
            request.event.set()
        self.transport.stop()

    def submit(
        self,
        command: NetworkCommand,
        *,
        wait_for_response: bool = True,
        response_timeout: float = 10.0,
    ) -> NetworkCommandResult:
        key = (command.section, command.command, command.sequence_id)
        pending = _PendingRequest(command=command, event=threading.Event())

        if wait_for_response:
            with self._pending_lock:
                if key in self._pending:
                    raise RuntimeError(
                        f"Duplicate pending Bambu request: {command.command} "
                        f"sequence_id={command.sequence_id}"
                    )
                self._pending[key] = pending

        started = time.monotonic()
        publish_result: MqttPublishResult
        try:
            publish_result = self.transport.publish(command.payload, qos=command.qos)
        except Exception:
            if wait_for_response:
                with self._pending_lock:
                    self._pending.pop(key, None)
            raise

        response: dict[str, Any] | None = None
        if wait_for_response:
            pending.event.wait(max(0.1, response_timeout))
            with self._pending_lock:
                current = self._pending.pop(key, None)
            response = current.response if current is not None else pending.response

        elapsed = time.monotonic() - started
        accepted, result, reason, error_code = self._parse_result(command, response)
        response_received = response is not None

        return NetworkCommandResult(
            section=command.section,
            command=command.command,
            sequence_id=command.sequence_id,
            submitted=publish_result.submitted,
            mqtt_puback_received=publish_result.confirmed,
            transport_delivered=publish_result.confirmed or response_received,
            response_received=response_received,
            printer_accepted=accepted,
            result=result,
            reason=reason,
            error_code=error_code,
            response=copy.deepcopy(response),
            elapsed_seconds=elapsed,
        )

    def _handle_connected(self) -> None:
        self._on_connected()

    def _handle_disconnected(self, reason: str) -> None:
        self._on_disconnected(reason)

    def _handle_error(self, message: str) -> None:
        self._on_error(message)

    def _handle_message(self, payload: dict[str, Any]) -> None:
        with self._last_response_lock:
            self._last_response = copy.deepcopy(payload)

        self._correlate(payload)
        self._on_telemetry(payload)

    def _correlate(self, payload: dict[str, Any]) -> None:
        matches: list[tuple[tuple[str, str, str], _PendingRequest, dict[str, Any]]] = []

        with self._pending_lock:
            for section, section_payload in payload.items():
                if not isinstance(section_payload, dict):
                    continue

                sequence_id = self._string_value(section_payload.get("sequence_id"))
                command = self._string_value(section_payload.get("command"))
                if not sequence_id:
                    continue

                for key, pending in self._pending.items():
                    expected_section, expected_command, expected_sequence = key
                    if expected_sequence != sequence_id:
                        continue
                    if section != expected_section:
                        continue
                    if command and command != expected_command:
                        continue
                    matches.append((key, pending, payload))

            for key, pending, response in matches:
                pending.response = copy.deepcopy(response)
                self._pending.pop(key, None)
                pending.event.set()

    @staticmethod
    def _string_value(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _parse_result(
        cls,
        command: NetworkCommand,
        response: dict[str, Any] | None,
    ) -> tuple[bool, str | None, str | None, int | None]:
        if response is None:
            return False, None, "timeout waiting for printer JSON response", None

        section_payload = response.get(command.section)
        if not isinstance(section_payload, dict):
            return False, None, f"response has no {command.section} section", None

        result = cls._optional_string(section_payload.get("result"))
        reason = cls._extract_reason(section_payload)
        error_code = cls._extract_error_code(section_payload)
        normalized_result = result.lower() if result else ""

        if error_code not in (None, 0):
            accepted = False
        elif normalized_result in FAILURE_RESULTS:
            accepted = False
        elif normalized_result in SUCCESS_RESULTS:
            accepted = True
        elif reason:
            accepted = reason.lower() in SUCCESS_RESULTS
        else:
            accepted = command.section in {"info", "pushing"}

        return accepted, result, reason, error_code

    @staticmethod
    def _optional_string(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _extract_reason(cls, section_payload: dict[str, Any]) -> str | None:
        for key in ("reason", "message", "msg", "error", "detail"):
            text = cls._optional_string(section_payload.get(key))
            if text:
                return text
        return None

    @staticmethod
    def _extract_error_code(section_payload: dict[str, Any]) -> int | None:
        for key in ("error_code", "err_code", "code"):
            value = section_payload.get(key)
            if value is None or value == "":
                continue
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
        return None
