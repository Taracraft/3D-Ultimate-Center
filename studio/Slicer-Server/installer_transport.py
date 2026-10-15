"""Bounded Linux Unix-socket installer transport; explicit start only.

No network TCP listener, shell, Docker action or service registration.
See INSTALLER_TRANSPORT.md for trust, deadlines and draining semantics.
"""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import struct
import sys
import threading
import time

import package_activation as activation
import pairing_registry as pairing
import restricted_installer as core

CONTROL = frozenset(("preflight", "status", "cancel"))
LANES = {"control": CONTROL, "mutation": frozenset(core.WRITE_FIELDS) | {"rollback", "resume"}}
MAX_REPLY = 16384
HEADER = struct.Struct("!4s32sHI")


class TransportError(ValueError):
    """Stable local transport error."""


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 300:
        raise TransportError("invalid_deadline")
    return float(value)


def _identity(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise TransportError("invalid_host_id")
    return value


def _uid(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise TransportError("invalid_peer_uid")
    return value


def _linux():
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise TransportError("unix_peer_unavailable")


def _directory(path, owner):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise TransportError("unsafe_socket_directory")
    activation._safe_path(path)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != owner or info.st_mode & 0o027:
        raise TransportError("unsafe_socket_directory")
    return path


def _peer(sock, expected_uid):
    _linux()
    if sock.family != socket.AF_UNIX:
        raise TransportError("unverified_peer")
    _, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != expected_uid:
        raise TransportError("unverified_peer")


def _remaining(sock, deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise TimeoutError()
    sock.settimeout(left)


def _read(sock, length, deadline):
    result = bytearray()
    while len(result) < length:
        _remaining(sock, deadline)
        chunk = sock.recv(length - len(result))
        if not chunk:
            raise TransportError("connection_closed")
        result.extend(chunk)
    return bytes(result)


def _send(sock, data, deadline):
    # sendall uses this one remaining timeout for the complete write.
    _remaining(sock, deadline)
    sock.sendall(data)


def _request_frame(host_id, authorization, body):
    _identity(host_id)
    if (type(authorization) is not str or re.fullmatch(r"Bearer [A-Za-z0-9_-]{43,128}", authorization) is None
            or type(body) is not bytes or not 1 <= len(body) <= core.MAX_REQUEST_BYTES):
        raise TransportError("invalid_frame")
    auth = authorization.encode("ascii")
    return HEADER.pack(b"STI1", host_id.encode("ascii"), len(auth), len(body)) + auth + body


class UnixInstallerServer:
    """Two fixed sockets; bounded admission includes peer/auth/read work."""

    def __init__(self, directory, service, registry, *, client_uid, client_gid,
                 io_timeout=10.0, control_workers=2):
        _linux()
        if type(service) is not core.Installer or type(registry) is not pairing.Registry:
            raise TransportError("invalid_installer")
        if service.credential_provider != registry.snapshot:
            raise TransportError("registry_provider_required")
        if type(control_workers) is not int or not 2 <= control_workers <= 8:
            raise TransportError("invalid_capacity")
        self.directory = _directory(directory, os.geteuid())
        self.service, self.registry = service, registry
        self.host_id = _identity(registry.host_id)
        self.client_uid, self.client_gid = _uid(client_uid), _uid(client_gid)
        if self.directory.stat().st_gid != self.client_gid:
            raise TransportError("socket_group_mismatch")
        self.io_timeout = _seconds(io_timeout)
        self.capacities = {"control": control_workers, "mutation": 1}
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._active = 0
        self._started = False
        self._closed = False
        self._listeners, self._nodes, self._threads, self._pools = {}, {}, [], {}
        self._slots = {lane: threading.BoundedSemaphore(n) for lane, n in self.capacities.items()}

    def start(self):
        if self._started or self._closed:
            raise TransportError("transport_already_started")
        self._started = True
        try:
            for lane in LANES:
                path = self.directory / (lane + ".sock")
                if path.exists() or path.is_symlink():
                    raise TransportError("socket_path_occupied")
            for lane in LANES:
                _directory(self.directory, os.geteuid())
                path = self.directory / (lane + ".sock")
                listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._listeners[lane] = listener
                listener.bind(str(path))
                info = path.lstat()
                self._nodes[path] = (info.st_dev, info.st_ino)
                os.chown(path, os.geteuid(), self.client_gid)
                path.chmod(0o660)
                listener.listen(self.capacities[lane])
                listener.settimeout(0.2)
                self._pools[lane] = ThreadPoolExecutor(max_workers=self.capacities[lane], thread_name_prefix="installer-" + lane)
            for lane in LANES:
                thread = threading.Thread(target=self._accept, args=(lane,), daemon=True)
                self._threads.append(thread)
                thread.start()
        except BaseException:
            self.close()
            raise
        return self

    def _accept(self, lane):
        listener = self._listeners[lane]
        while not self._stop.is_set():
            try:
                conn, _ = listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            slot = self._slots[lane]
            if not slot.acquire(blocking=False):
                conn.close()  # No unbounded queue or blocking error write.
                continue
            with self._lock:
                self._active += 1
            try:
                future = self._pools[lane].submit(self._handle, conn, lane)
            except Exception:
                conn.close()
                self._done(lane)
            else:
                future.add_done_callback(lambda _, lane=lane: self._done(lane))

    def _done(self, lane):
        with self._lock:
            self._active -= 1
        self._slots[lane].release()

    def _handle(self, conn, lane):
        deadline = time.monotonic() + self.io_timeout
        with conn:
            try:
                _peer(conn, self.client_uid)
                magic, host, auth_size, body_size = HEADER.unpack(_read(conn, HEADER.size, deadline))
                if (magic != b"STI1" or host != self.host_id.encode("ascii")
                        or not 50 <= auth_size <= 135 or not 1 <= body_size <= core.MAX_REQUEST_BYTES):
                    raise TransportError("invalid_frame")
                auth = _read(conn, auth_size, deadline).decode("ascii")
                body = _read(conn, body_size, deadline)
                # Check auth before parsing/routing; dispatch rechecks the latest
                # registry immediately before accepting the operation.
                self.service._authenticate(auth, True)
                request = self.service._parse(body)
                if request["operation"] not in LANES[lane]:
                    raise TransportError("wrong_lane")
                _remaining(conn, deadline)
                result = self.service.dispatch(auth, body, secure_channel=True)
            except (core.InstallerError, TransportError) as exc:
                result = {"ok": False, "error": str(exc)}
            except Exception:
                result = {"ok": False, "error": "transport_failed"}
            try:
                data = json.dumps({"host_id": self.host_id, "result": result},
                                  separators=(",", ":"), allow_nan=False).encode("ascii")
                if len(data) > MAX_REPLY:
                    return
                _send(conn, struct.pack("!I", len(data)) + data, deadline)
            except Exception:
                pass  # Disconnect/timeout never cancels an accepted mutation.

    def close(self):
        self._closed = True
        self._stop.set()
        for listener in self._listeners.values():
            listener.close()
        for thread in self._threads:
            thread.join(timeout=1)
        for pool in self._pools.values():
            pool.shutdown(wait=False, cancel_futures=False)
        for path, identity in self._nodes.items():
            try:
                info = path.lstat()
                if stat.S_ISSOCK(info.st_mode) and (info.st_dev, info.st_ino) == identity:
                    path.unlink()
            except FileNotFoundError:
                pass
        with self._lock:
            return {"accepting": False, "draining": self._active > 0}

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()


class UnixInstallerClient:
    def __init__(self, directory, *, host_id, server_uid, timeout=10.0):
        _linux()
        self.server_uid = _uid(server_uid)
        self.directory = _directory(directory, self.server_uid)
        self.host_id = _identity(host_id)
        self.timeout = _seconds(timeout)

    def request(self, token, request):
        if type(request) is not dict:
            raise TransportError("invalid_request")
        operation = request.get("operation")
        if type(operation) is not str or operation not in CONTROL | LANES["mutation"]:
            raise TransportError("invalid_request")
        lane = "control" if operation in CONTROL else "mutation"
        try:
            body = json.dumps(request, separators=(",", ":"), allow_nan=False).encode("ascii")
        except (ValueError, TypeError):
            raise TransportError("invalid_request") from None
        if type(token) is not str:
            raise TransportError("invalid_frame")
        frame = _request_frame(self.host_id, "Bearer " + token, body)
        deadline = time.monotonic() + self.timeout
        try:
            _directory(self.directory, self.server_uid)
            path = self.directory / (lane + ".sock")
            info = path.lstat()
            if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != self.server_uid
                    or info.st_mode & 0o007):
                raise TransportError("unsafe_socket")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                _remaining(conn, deadline)
                conn.connect(str(path))
                _peer(conn, self.server_uid)  # Verify before transmitting token.
                _send(conn, frame, deadline)
                length, = struct.unpack("!I", _read(conn, 4, deadline))
                if not 1 <= length <= MAX_REPLY:
                    raise TransportError("invalid_response")
                reply = json.loads(_read(conn, length, deadline), object_pairs_hook=core._pairs)
                if (type(reply) is not dict or set(reply) != {"host_id", "result"}
                        or reply["host_id"] != self.host_id or type(reply["result"]) is not dict
                        or type(reply["result"].get("ok")) is not bool):
                    raise TransportError("invalid_response")
                return reply["result"]
        except Exception:
            # No reconnect/retry: an accepted mutation can still be running.
            result = {"ok": False, "error": "response_unavailable", "outcome": "unknown"}
            ident = (request.get("target") if operation in ("rollback", "resume")
                     else request.get("request_id"))
            if type(ident) is str and re.fullmatch(r"[a-f0-9]{32}", ident):
                result["request_id"] = ident
            return result
