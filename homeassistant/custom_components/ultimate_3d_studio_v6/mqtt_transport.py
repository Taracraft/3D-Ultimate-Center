from __future__ import annotations

import json
import ssl
import threading
import uuid
from dataclasses import dataclass


_NON_REPLAYABLE_QOS0_COMMANDS = frozenset({"project_file", "resume"})


def _non_replayable_command(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    section = payload.get("print")
    if not isinstance(section, dict):
        return None
    command = str(section.get("command") or "").strip().casefold()
    if command in _NON_REPLAYABLE_QOS0_COMMANDS:
        return command
    if (
        command == "ams_control"
        and str(section.get("param") or "").strip().casefold() == "resume"
    ):
        return "ams_control:resume"
    return None


@dataclass(frozen=True, slots=True)
class MqttPublishResult:
    submitted: bool
    confirmed: bool
    mid: int
    qos: int
    topic: str


class BambuLanMqttTransport:
    """Low-level MQTT/TLS transport without Bambu protocol interpretation."""

    def __init__(
        self,
        *,
        host,
        port,
        username,
        access_code,
        serial,
        tls_insecure,
        on_telemetry,
        on_connected,
        on_disconnected,
        on_error,
    ):
        import paho.mqtt.client as mqtt

        self._mqtt = mqtt
        self.host = host
        self.port = port
        self.serial = serial
        self.on_telemetry = on_telemetry
        self.on_connected = on_connected
        self.on_disconnected = on_disconnected
        self.on_error = on_error
        self.started = False
        self.lock = threading.Lock()
        self.connected_event = threading.Event()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"u3dv6-{uuid.uuid4().hex[:10]}",
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(username, access_code)
        self.client.tls_set(
            cert_reqs=ssl.CERT_NONE if tls_insecure else ssl.CERT_REQUIRED
        )
        self.client.tls_insecure_set(tls_insecure)
        self.client.reconnect_delay_set(min_delay=2, max_delay=60)
        self.client.on_connect = self._connect
        self.client.on_disconnect = self._disconnect
        self.client.on_connect_fail = self._connect_fail
        self.client.on_message = self._message

    @property
    def report_topic(self):
        return f"device/{self.serial}/report"

    @property
    def request_topic(self):
        return f"device/{self.serial}/request"

    def start(self):
        with self.lock:
            if self.started:
                return
            self.started = True
        self.client.connect_async(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def stop(self):
        with self.lock:
            if not self.started:
                return
            self.started = False
        self.connected_event.clear()
        try:
            self.client.disconnect()
        finally:
            self.client.loop_stop()

    def _ensure_connected(self, timeout: float = 10.0):
        if self.client.is_connected() and self.connected_event.is_set():
            return
        if not self.started:
            raise RuntimeError("MQTT transport is not started")
        try:
            self.client.reconnect()
        except Exception:
            pass
        if not self.connected_event.wait(timeout):
            raise RuntimeError(
                f"MQTT connection to {self.host}:{self.port} is not ready "
                f"after {timeout:.0f} seconds"
            )

    def publish(self, payload, qos=0) -> MqttPublishResult:
        """Submit one MQTT message without retrying an ambiguous QoS publish."""
        qos = int(qos)
        command = _non_replayable_command(payload)
        if command is not None and qos != 0:
            raise RuntimeError(
                f"Non-replayable MQTT command {command} requires QoS 0"
            )
        self._ensure_connected()
        message = json.dumps(payload, separators=(",", ":"))

        result = self.client.publish(
            self.request_topic,
            message,
            qos=qos,
            retain=False,
        )
        if result.rc != self._mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"MQTT publish failed on {self.request_topic}: rc={result.rc}"
            )

        if qos <= 0:
            return MqttPublishResult(
                submitted=True,
                confirmed=True,
                mid=result.mid,
                qos=qos,
                topic=self.request_topic,
            )

        result.wait_for_publish(timeout=8)
        confirmed = bool(result.is_published())
        if not confirmed:
            self.on_error(
                f"MQTT command submitted without PUBACK on {self.request_topic}; "
                "printer JSON response is required"
            )

        return MqttPublishResult(
            submitted=True,
            confirmed=confirmed,
            mid=result.mid,
            qos=qos,
            topic=self.request_topic,
        )

    def _connect(self, client, userdata, flags, reason, properties):
        if hasattr(reason, "is_failure") and reason.is_failure:
            self.connected_event.clear()
            self.on_error(f"MQTT rejected by {self.host}:{self.port}: {reason}")
            return
        client.subscribe(self.report_topic)
        self.connected_event.set()
        self.on_connected()

    def _disconnect(self, client, userdata, flags, reason, properties):
        self.connected_event.clear()
        self.on_disconnected(str(reason))

    def _connect_fail(self, client, userdata):
        self.connected_event.clear()
        self.on_error(f"MQTT connection to {self.host}:{self.port} failed")

    def _message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8", errors="replace"))
        except Exception as exc:
            self.on_error(f"Invalid MQTT payload: {exc}")
            return
        if isinstance(payload, dict):
            self.on_telemetry(payload)
