"""Offline RTSPS decoder boundaries; never opens a printer connection."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'deploy/homeassistant/custom_components/ultimate_3d_studio'
PKG = 'x1c_camera_boundary_test'
package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules[PKG] = package
spec = importlib.util.spec_from_file_location(PKG + '.camera_rtsp', ROOT / 'camera_rtsp.py')
camera = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = camera
spec.loader.exec_module(camera)

class CameraBoundaries(unittest.TestCase):
    def test_ipv6_and_encoded_credential(self):
        self.assertEqual(camera.camera_source('::1', 'a@b:c'),
                         'rtsps://bblp:a%40b%3Ac@[::1]:322/streaming/live/1')
        for host in ['x@evil', 'https://printer', 'printer/path', 'a b', '-printer', '']:
            with self.subTest(host=host), self.assertRaises(ValueError):
                camera.camera_source(host, 'synthetic')

    def test_decoder_errors_cannot_expose_credential_or_url(self):
        client = camera.RtspPrinterCameraClient(host='printer.invalid', access_code='synthetic-secret')
        def failed(*args, **kwargs):
            raise ValueError(args[0])
        with patch.dict(sys.modules, {'av': types.SimpleNamespace(open=failed)}):
            with self.assertRaisesRegex(RuntimeError, r'^RTSPS camera failed \(ValueError\)$'):
                client._stream_once()
        self.assertNotIn('synthetic-secret', repr(client.runtime_status()))
        self.assertEqual(client.runtime_status().port, 322)

    def test_decode_stores_valid_jpeg_and_uses_tcp_tls(self):
        client = camera.RtspPrinterCameraClient(host='printer.invalid', access_code='synthetic', tls_insecure=False)
        raw = b'\xff\xd8synthetic-frame\xff\xd9'
        class Frame:
            def to_image(self): return self
            def save(self, output, **kwargs): output.write(raw)
        class Container:
            streams = types.SimpleNamespace(video=[object()])
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def decode(self, **kwargs): return iter([Frame()])
        from unittest.mock import Mock
        decoder = Mock(return_value=Container())
        with patch.dict(sys.modules, {'av': types.SimpleNamespace(open=decoder)}):
            client._stream_once()
        self.assertEqual(client.latest_frame, raw)
        self.assertTrue(client.connected)
        self.assertEqual(decoder.call_args.kwargs['options'], {'rtsp_transport':'tcp','tls_verify':'1'})

if __name__ == '__main__': unittest.main()
