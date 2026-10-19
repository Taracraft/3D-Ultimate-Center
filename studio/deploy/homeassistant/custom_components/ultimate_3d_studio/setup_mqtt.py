"""Bounded MQTT login/subscription probe; never publishes a printer command."""
from __future__ import annotations
import ssl
import threading
import uuid

class MqttSetupError(Exception):
    """Stable translation key only; credentials never enter errors."""

def probe_mqtt(host, serial, access_code, tls_insecure):
    from .const import MQTT_PORT, MQTT_USERNAME
    import paho.mqtt.client as mqtt
    finished = threading.Event()
    outcome = ['mqtt_unreachable']
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         client_id='u3d-check-'+uuid.uuid4().hex[:10], protocol=mqtt.MQTTv311, reconnect_on_failure=False)
    client.connect_timeout = 5.0
    client.username_pw_set(MQTT_USERNAME, access_code)
    client.tls_set(cert_reqs=ssl.CERT_NONE if tls_insecure else ssl.CERT_REQUIRED)
    client.tls_insecure_set(tls_insecure)
    def on_connect(client, userdata, flags, reason, properties):
        if reason.is_failure:
            outcome[0] = 'mqtt_auth_failed' if reason.value in (134, 135) else 'mqtt_rejected'
            finished.set()
        else:
            rc, _ = client.subscribe('device/'+serial+'/report', qos=0)
            if rc != mqtt.MQTT_ERR_SUCCESS:
                outcome[0] = 'mqtt_subscribe_failed'; finished.set()
    def on_subscribe(client, userdata, mid, reasons, properties):
        outcome[0] = 'mqtt_subscribe_failed' if not reasons or any(r.is_failure for r in reasons) else None
        finished.set()
    def on_disconnect(client, userdata, flags, reason, properties):
        if not finished.is_set():
            outcome[0] = 'mqtt_disconnected'; finished.set()
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_disconnect = on_disconnect
    started = False
    try:
        client.connect(host, MQTT_PORT, keepalive=15)
        client.loop_start(); started = True
        if not finished.wait(8.0):
            raise MqttSetupError('mqtt_timeout')
        if outcome[0]:
            raise MqttSetupError(outcome[0])
    except ssl.SSLError:
        raise MqttSetupError('mqtt_tls_failed') from None
    except OSError:
        raise MqttSetupError('mqtt_unreachable') from None
    finally:
        try:
            client.disconnect()
        finally:
            if started:
                client.loop_stop()
