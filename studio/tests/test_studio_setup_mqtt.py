"""MQTT setup probe with a fake broker; no sockets, publishes or printer actions."""
import importlib.util
from pathlib import Path
import ssl
import sys
import types
import unittest
from unittest.mock import patch

COMPONENT=Path(__file__).resolve().parents[1]/'deploy/homeassistant/custom_components/ultimate_3d_studio'

def load_probe():
    pkg=types.ModuleType('setup_mqtt_test');pkg.__path__=[str(COMPONENT)]
    spec=importlib.util.spec_from_file_location('setup_mqtt_test.setup_mqtt',COMPONENT/'setup_mqtt.py')
    module=importlib.util.module_from_spec(spec)
    constants=types.ModuleType('setup_mqtt_test.const');constants.MQTT_PORT=8883;constants.MQTT_USERNAME='bblp'
    with patch.dict(sys.modules,{'setup_mqtt_test':pkg,'setup_mqtt_test.const':constants}):spec.loader.exec_module(module)
    return module

class ProbeTests(unittest.TestCase):
    def run_probe(self,*,connect_reason=0,subscribe_reason=0,error=None,subscribe_rc=0):
        module=load_probe()
        reason=lambda value:types.SimpleNamespace(value=value,is_failure=value>=128)
        class Client:
            def __init__(self,**kwargs):self.kwargs=kwargs;self.calls=[];self.stopped=False;self.disconnected=False
            def username_pw_set(self,*args):self.login=args
            def tls_set(self,**kwargs):self.tls=kwargs
            def tls_insecure_set(self,value):self.insecure=value
            def connect(self,*args,**kwargs):
                self.address=args
                if error:raise error
            def loop_start(self):self.on_connect(self,None,None,reason(connect_reason),None)
            def subscribe(self,topic,qos):
                self.calls.append((topic,qos))
                if not subscribe_rc:self.on_subscribe(self,None,1,[reason(subscribe_reason)],None)
                return subscribe_rc,1
            def disconnect(self):self.disconnected=True
            def loop_stop(self):self.stopped=True
        instance=Client()
        mqtt=types.ModuleType('paho.mqtt.client');mqtt.Client=lambda **kwargs:instance
        mqtt.CallbackAPIVersion=types.SimpleNamespace(VERSION2=2);mqtt.MQTTv311=4;mqtt.MQTT_ERR_SUCCESS=0
        pkg=types.ModuleType('setup_mqtt_test');pkg.__path__=[str(COMPONENT)]
        constants=types.ModuleType('setup_mqtt_test.const');constants.MQTT_PORT=8883;constants.MQTT_USERNAME='bblp'
        with patch.dict(sys.modules,{'setup_mqtt_test':pkg,'setup_mqtt_test.const':constants,'paho':types.ModuleType('paho'),'paho.mqtt':types.ModuleType('paho.mqtt'),'paho.mqtt.client':mqtt}):
            try:module.probe_mqtt('192.0.2.1','DEMO-SERIAL','secret-not-for-logs',False)
            except module.MqttSetupError as exc:self.failure=str(exc)
            else:self.failure=None
        self.assertTrue(instance.disconnected)
        if error is None:self.assertTrue(instance.stopped)
        return instance
    def test_login_and_status_suback_without_publish(self):
        c=self.run_probe();self.assertIsNone(self.failure)
        self.assertEqual(c.calls,[('device/DEMO-SERIAL/report',0)])
        self.assertEqual(c.login,('bblp','secret-not-for-logs'));self.assertFalse(c.insecure)
        self.assertEqual(c.address,('192.0.2.1',8883));self.assertEqual(c.connect_timeout,5.0)
    def test_authentication_rejected(self):
        c=self.run_probe(connect_reason=135);self.assertEqual(self.failure,'mqtt_auth_failed');self.assertEqual(c.calls,[])
    def test_protocol_rejected(self):
        self.run_probe(connect_reason=132);self.assertEqual(self.failure,'mqtt_rejected')
    def test_subscription_rejected(self):
        self.run_probe(subscribe_reason=128);self.assertEqual(self.failure,'mqtt_subscribe_failed')
    def test_subscription_local_failure(self):
        self.run_probe(subscribe_rc=4);self.assertEqual(self.failure,'mqtt_subscribe_failed')
    def test_tls_error_does_not_echo_secret(self):
        self.run_probe(error=ssl.SSLError('secret-not-for-logs'));self.assertEqual(self.failure,'mqtt_tls_failed')
    def test_network_error_does_not_echo_secret(self):
        self.run_probe(error=OSError('secret-not-for-logs'));self.assertEqual(self.failure,'mqtt_unreachable')

if __name__=='__main__':unittest.main()
