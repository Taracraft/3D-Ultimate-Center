"""Native Bambu-compatible TLS JPEG camera reader for Studio."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import socket
import ssl
import struct
import threading
import time
from typing import Callable

_LOGGER = logging.getLogger(__name__)
_CAMERA_PORT = 6000
_AUTH_PACKET_TYPE = 0x40
_AUTH_PACKET_COMMAND = 0x3000
_MAX_JPEG_BYTES = 10_000_000
_MIN_RECONNECT_DELAY = 2.0
_MAX_RECONNECT_DELAY = 30.0


@dataclass(frozen=True, slots=True)
class CameraRuntimeStatus:
    host: str
    port: int
    connected: bool
    frames_received: int
    sequence: int
    last_frame_at: str | None
    last_error: str


def _padded_ascii(value: str, length: int) -> bytes:
    payload = value.encode("ascii")
    if len(payload) > length:
        raise ValueError(f"Camera authentication value exceeds {length} bytes")
    return payload.ljust(length, b"\x00")


def _read_exact(connection: ssl.SSLSocket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError(
                f"Native camera connection closed with {remaining} bytes pending"
            )
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class NativePrinterCameraClient:
    def __init__(
        self,
        *,
        host: str,
        access_code: str,
        tls_insecure: bool = True,
        on_state_change: Callable[[], None] | None = None,
    ) -> None:
        self.host = host
        self.access_code = access_code
        self.tls_insecure = tls_insecure
        self._on_state_change = on_state_change
        self._condition = threading.Condition()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._frame: bytes | None = None
        self._sequence = 0
        self._frames_received = 0
        self._last_frame_at: str | None = None
        self._last_error = ""
        self._connected = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"ultimate-3d-studio-camera-{self.host}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        with self._condition:
            self._condition.notify_all()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=12)
        self._thread = None
        self._set_connected(False)

    @property
    def latest_frame(self) -> bytes | None:
        with self._condition:
            return self._frame

    @property
    def connected(self) -> bool:
        with self._condition:
            return self._connected

    def runtime_status(self) -> CameraRuntimeStatus:
        with self._condition:
            return CameraRuntimeStatus(
                host=self.host,
                port=_CAMERA_PORT,
                connected=self._connected,
                frames_received=self._frames_received,
                sequence=self._sequence,
                last_frame_at=self._last_frame_at,
                last_error=self._last_error,
            )

    def _notify_state_change(self) -> None:
        if self._on_state_change is None:
            return
        try:
            self._on_state_change()
        except Exception:
            _LOGGER.exception("Studio native camera state callback failed")

    def _set_connected(self, value: bool) -> None:
        changed = False
        with self._condition:
            if self._connected != value:
                self._connected = value
                changed = True
            self._condition.notify_all()
        if changed:
            self._notify_state_change()

    def _set_error(self, message: str) -> None:
        changed = False
        with self._condition:
            if self._last_error != message:
                self._last_error = message
                changed = True
            self._condition.notify_all()
        if changed:
            self._notify_state_change()

    def _store_frame(self, frame: bytes) -> None:
        with self._condition:
            self._frame = frame
            self._sequence += 1
            self._frames_received += 1
            self._last_frame_at = datetime.now(UTC).isoformat(timespec="seconds")
            self._last_error = ""
            self._condition.notify_all()
        self._notify_state_change()

    def _auth_packet(self) -> bytes:
        return (
            struct.pack("<IIII", _AUTH_PACKET_TYPE, _AUTH_PACKET_COMMAND, 0, 0)
            + _padded_ascii("bblp", 32)
            + _padded_ascii(self.access_code, 32)
        )

    def _ssl_context(self) -> ssl.SSLContext:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if self.tls_insecure:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        return context

    def _stream_once(self) -> None:
        context = self._ssl_context()
        with socket.create_connection((self.host, _CAMERA_PORT), timeout=8) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=self.host) as connection:
                connection.settimeout(12)
                connection.sendall(self._auth_packet())
                self._set_connected(True)
                while not self._stop_event.is_set():
                    header = _read_exact(connection, 16)
                    payload_size, _track, _flags, _reserved = struct.unpack("<IIII", header)
                    if payload_size <= 0 or payload_size > _MAX_JPEG_BYTES:
                        raise ValueError(f"Native camera reported invalid JPEG size: {payload_size}")
                    frame = _read_exact(connection, payload_size)
                    if not frame.startswith(b"\xff\xd8") or not frame.endswith(b"\xff\xd9"):
                        continue
                    self._store_frame(frame)

    def _run(self) -> None:
        delay = _MIN_RECONNECT_DELAY
        while not self._stop_event.is_set():
            try:
                self._stream_once()
                delay = _MIN_RECONNECT_DELAY
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                self._set_error(f"{type(exc).__name__}: {exc}")
                _LOGGER.warning(
                    "Studio native camera connection to %s:%s interrupted: %s",
                    self.host,
                    _CAMERA_PORT,
                    exc,
                )
            finally:
                self._set_connected(False)
            if self._stop_event.wait(delay):
                break
            delay = min(_MAX_RECONNECT_DELAY, delay * 1.7)
