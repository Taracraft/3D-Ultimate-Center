"""Threaded TLS MQTT transport."""
from __future__ import annotations

import json
import logging
import ssl
import threading
import uuid
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)


def _reason_is_failure(reason_code: Any) -> bool:
    """Handle Paho v2 ReasonCode as well as older numeric return codes."""
    if hasattr(reason_code, "is_failure"):
        return bool(reason_code.is_failure)
    value = getattr(reason_code, "value", reason_code)
    try:
        return int(value) != 0
    except (TypeError, ValueError):
        return str(reason_code).lower() not in {"success", "0"}


class PrinterMqttClient:
    """Blocking construction is intentional and must run in an executor."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        serial: str,
        transport_name: str,
        tls_insecure: bool,
        on_telemetry: Callable[[dict[str, Any], str], None],
        on_connected: Callable[[str], None],
        on_disconnected: Callable[[str], None],
    ) -> None:
        self.host = host
        self.port = port
        self.serial = serial
        self.transport_name = transport_name
        self._on_telemetry = on_telemetry
        self._on_connected_callback = on_connected
        self._on_disconnected_callback = on_disconnected
        self._started = False
        self._lock = threading.Lock()

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"printer-control-center-ha-{transport_name}-{uuid.uuid4().hex[:8]}",
            protocol=mqtt.MQTTv311,
        )
        self._client.username_pw_set(username, password)

        # paho tls_set may load CA certificates and is therefore blocking.
        # The coordinator creates this object via async_add_executor_job.
        self._client.tls_set(
            cert_reqs=ssl.CERT_NONE if tls_insecure else ssl.CERT_REQUIRED
        )
        self._client.tls_insecure_set(tls_insecure)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    @property
    def report_topic(self) -> str:
        return f"device/{self.serial}/report"

    @property
    def request_topic(self) -> str:
        return f"device/{self.serial}/request"

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        _LOGGER.info(
            "Starting %s MQTT transport to %s:%s",
            self.transport_name,
            self.host,
            self.port,
        )
        self._client.connect_async(self.host, self.port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._started = False
        try:
            self._client.disconnect()
        finally:
            self._client.loop_stop()

    def publish(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, separators=(",", ":"))
        result = self._client.publish(self.request_topic, message, qos=0)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish failed with rc={result.rc}")

    def request_full_status(self) -> None:
        self.publish(
            {
                "pushing": {
                    "sequence_id": "0",
                    "command": "pushall",
                    "version": 1,
                    "push_target": 1,
                }
            }
        )
        self.publish({"info": {"sequence_id": "0", "command": "get_version"}})

    def _request_full_status_delayed(self) -> None:
        try:
            self.request_full_status()
        except Exception:
            _LOGGER.exception("Unable to request delayed full printer status")

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if _reason_is_failure(reason_code):
            _LOGGER.error(
                "%s MQTT connection rejected: %s",
                self.transport_name,
                reason_code,
            )
            return

        _LOGGER.info("%s MQTT connected", self.transport_name)
        client.subscribe(self.report_topic)
        self._on_connected_callback(self.transport_name)

        try:
            self.request_full_status()
            threading.Timer(2.0, self._request_full_status_delayed).start()
        except Exception:
            _LOGGER.exception("Unable to request initial printer status")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        _LOGGER.warning("%s MQTT disconnected: %s", self.transport_name, reason_code)
        self._on_disconnected_callback(self.transport_name)

    def _on_message(self, client, userdata, message) -> None:
        try:
            payload = json.loads(message.payload.decode("utf-8", errors="replace"))
            if isinstance(payload, dict):
                self._on_telemetry(payload, self.transport_name)
        except Exception:
            _LOGGER.exception("Invalid MQTT payload on %s", message.topic)