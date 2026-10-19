"""Read-only Bambu X1/H2 RTSPS frames using HA's in-process PyAV decoder.

Credentials remain in server memory. There is no subprocess, public restream,
printer command, downloaded vendor plugin, or credential-bearing status field.
"""
from __future__ import annotations

from dataclasses import replace
from io import BytesIO
import ipaddress
import re
import time
from urllib.parse import quote

from .camera_native import NativePrinterCameraClient, _MAX_JPEG_BYTES

def camera_source(host: str, access_code: str) -> str:
    host = str(host).strip()
    try:
        address = ipaddress.ip_address(host.strip('[]'))
        authority = '[' + str(address) + ']' if address.version == 6 else str(address)
    except ValueError:
        labels = host.rstrip('.').split('.')
        if len(host) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', x) for x in labels):
            raise ValueError('Invalid printer camera host') from None
        authority = host
    if not isinstance(access_code, str) or not 1 <= len(access_code) <= 32 or not access_code.isascii():
        raise ValueError('Invalid printer camera credential')
    return 'rtsps://bblp:' + quote(access_code, safe='') + '@' + authority + ':322/streaming/live/1'

class RtspPrinterCameraClient(NativePrinterCameraClient):
    port = 322

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Validate before any network or decoder operation.
        self._source = camera_source(self.host, self.access_code)

    def stream_source(self) -> str:
        """Only HA's internal stream provider may consume this value."""
        return self._source

    def runtime_status(self):
        return replace(super().runtime_status(), port=self.port)

    def _stream_once(self) -> None:
        try:
            import av
            options = {'rtsp_transport':'tcp', 'tls_verify':'0' if self.tls_insecure else '1'}
            with av.open(self._source, mode='r', options=options, timeout=(8.0, 8.0)) as container:
                if not container.streams.video:
                    raise RuntimeError('RTSPS has no video stream')
                last_snapshot = 0.0
                for frame in container.decode(video=0):
                    if self._stop_event.is_set():
                        break
                    now = time.monotonic()
                    if now - last_snapshot < .5:
                        continue
                    output = BytesIO()
                    frame.to_image().save(output, format='JPEG', quality=85)
                    raw = output.getvalue()
                    if len(raw) > _MAX_JPEG_BYTES or not raw.startswith(b'\xff\xd8') or not raw.endswith(b'\xff\xd9'):
                        raise ValueError('Invalid RTSPS frame')
                    self._store_frame(raw)
                    self._set_connected(True)
                    last_snapshot = now
        except Exception as exc:
            # Decoder/library errors can contain the entire source URL.
            # Never propagate their original text to status attributes/logs.
            raise RuntimeError('RTSPS camera failed (' + type(exc).__name__ + ')') from None
