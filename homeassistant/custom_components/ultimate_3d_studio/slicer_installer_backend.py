"""Server-side HA installer client; secrets never cross the UI boundary."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import stat
import struct
import sys
import time
from typing import Callable

PROTOCOL = 1
MAX_REQUEST_BYTES = 8192
MAX_REPLY_BYTES = 16384
MAX_HANDOFF_BYTES = 2048
HEADER = struct.Struct("!4s32sHI")
CONTROL = frozenset(("preflight", "status", "cancel"))
MUTATION = frozenset(("initialize", "stage", "retry", "activate", "recover", "rollback", "resume"))
OPERATIONS = CONTROL | MUTATION
SECRET_KEYS = frozenset(("authorization", "token", "secret", "password"))
TOKEN_FILE = "installer-token.json"
CREDENTIAL_FILE = "installer-credential.json"


class InstallerBackendError(ValueError):
    """Stable HA-side failure without secret or host path details."""


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InstallerBackendError("invalid_json")
        result[key] = value
    return result


def _host_id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise InstallerBackendError("invalid_host_id")
    return value


def _principal(value):
    if type(value) is not str or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value) is None:
        raise InstallerBackendError("invalid_principal")
    return value


def _uid(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise InstallerBackendError("invalid_peer_uid")
    return value


def _seconds(value):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 300:
        raise InstallerBackendError("invalid_deadline")
    return float(value)


def _request_id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise InstallerBackendError("invalid_request_id")
    return value


def _directory(path, *, owner=None, private=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or path.is_symlink():
        raise InstallerBackendError("unsafe_directory")
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise InstallerBackendError("unsafe_directory")
    if os.name != "nt":
        if owner is not None and info.st_uid != owner:
            raise InstallerBackendError("unsafe_directory")
        forbidden = 0o077 if private else 0o027
        if info.st_mode & forbidden:
            raise InstallerBackendError("unsafe_directory")
    return path


def _fsync_directory(path):
    if os.name == "nt":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_regular(path, *, maximum, owner=None, mode=None):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or not 1 <= info.st_size <= maximum):
        raise InstallerBackendError("unsafe_file")
    if os.name != "nt":
        if owner is not None and info.st_uid != owner:
            raise InstallerBackendError("unsafe_file")
        if mode is not None and stat.S_IMODE(info.st_mode) != mode:
            raise InstallerBackendError("unsafe_file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        current = os.fstat(stream.fileno())
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise InstallerBackendError("file_changed")
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise InstallerBackendError("unsafe_file")
    return data, (info.st_dev, info.st_ino)


def _atomic_private_json(path, value):
    path = Path(path)
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    temp = path.parent / ("." + path.name + "." + secrets.token_hex(16) + ".tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(temp, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            if os.name != "nt":
                os.fchmod(stream.fileno(), 0o600)
            os.fsync(stream.fileno())
        os.replace(temp, path)
        _fsync_directory(path.parent)
    finally:
        temp.unlink(missing_ok=True)
    return data


@dataclass(frozen=True, repr=False)
class _Credential:
    host_id: str
    principal: str
    token: str


class InstallerCredentialStore:
    """Durably adopt one protected handoff, then remove its exact inode."""

    def __init__(self, directory, *, expected_host_id, server_uid):
        self.owner = os.geteuid() if hasattr(os, "geteuid") else None
        self.directory = Path(directory)
        if not self.directory.exists():
            self.directory.mkdir(mode=0o700, parents=False)
        self.directory = _directory(self.directory, owner=self.owner, private=True)
        self.expected_host_id = _host_id(expected_host_id)
        self.server_uid = _uid(server_uid)
        self.path = self.directory / CREDENTIAL_FILE

    def _decode(self, data):
        try:
            value = json.loads(data, object_pairs_hook=_pairs)
            if type(value) is not dict or set(value) != {"host_id", "principal", "token"}:
                raise ValueError()
            if _host_id(value["host_id"]) != self.expected_host_id:
                raise ValueError()
            _principal(value["principal"])
            if type(value["token"]) is not str or re.fullmatch(r"[A-Za-z0-9_-]{64}", value["token"]) is None:
                raise ValueError()
            return _Credential(**value)
        except (ValueError, TypeError, UnicodeError, RecursionError, InstallerBackendError):
            raise InstallerBackendError("invalid_credential") from None

    def load(self):
        data, _ = _read_regular(self.path, maximum=MAX_HANDOFF_BYTES,
                                owner=self.owner, mode=0o600)
        return self._decode(data)

    def public_status(self):
        try:
            current = self.load()
        except (FileNotFoundError, InstallerBackendError):
            return {"credential_stored": False, "host_id": self.expected_host_id}
        return {"credential_stored": True, "host_id": current.host_id,
                "principal": current.principal}

    def adopt_handoff(self, handoff_directory):
        root = _directory(handoff_directory, owner=self.server_uid, private=False)
        source = root / TOKEN_FILE
        data, identity = _read_regular(source, maximum=MAX_HANDOFF_BYTES,
                                       owner=self.owner, mode=0o400)
        credential = self._decode(data)
        written = _atomic_private_json(self.path, {
            "host_id": credential.host_id,
            "principal": credential.principal,
            "token": credential.token,
        })
        check, _ = _read_regular(self.path, maximum=MAX_HANDOFF_BYTES,
                                 owner=self.owner, mode=0o600)
        if not secrets.compare_digest(hashlib.sha256(check).digest(), hashlib.sha256(written).digest()):
            raise InstallerBackendError("credential_store_unconfirmed")
        current = source.lstat()
        if (current.st_dev, current.st_ino) != identity:
            raise InstallerBackendError("handoff_cleanup_unconfirmed")
        if os.name == "nt":
            # Windows maps the synthetic 0400 fixture to a read-only attribute.
            # The production path is Linux and keeps the validated inode/mode.
            source.chmod(0o600)
        source.unlink()
        _fsync_directory(root)
        return self.public_status()


def _peer(sock, expected_uid):
    if sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"):
        raise InstallerBackendError("unix_peer_unavailable")
    if sock.family != socket.AF_UNIX:
        raise InstallerBackendError("unverified_peer")
    _, uid, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != expected_uid:
        raise InstallerBackendError("unverified_peer")


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
            raise InstallerBackendError("connection_closed")
        result.extend(chunk)
    return bytes(result)


class UnixInstallerClient:
    """HA-packaged client compatible with the fixed STI1 host transport."""

    def __init__(self, directory, *, host_id, server_uid, timeout=10.0):
        self.server_uid = _uid(server_uid)
        self.directory = _directory(directory, owner=self.server_uid, private=False)
        self.host_id = _host_id(host_id)
        self.timeout = _seconds(timeout)

    def request(self, token, request):
        if type(request) is not dict or type(request.get("operation")) is not str:
            raise InstallerBackendError("invalid_request")
        operation = request["operation"]
        if operation not in OPERATIONS or type(token) is not str or re.fullmatch(r"[A-Za-z0-9_-]{64}", token) is None:
            raise InstallerBackendError("invalid_request")
        try:
            body = json.dumps(request, separators=(",", ":"), allow_nan=False).encode("ascii")
        except (ValueError, TypeError, UnicodeError):
            raise InstallerBackendError("invalid_request") from None
        if not 1 <= len(body) <= MAX_REQUEST_BYTES:
            raise InstallerBackendError("invalid_request")
        auth = ("Bearer " + token).encode("ascii")
        frame = HEADER.pack(b"STI1", self.host_id.encode("ascii"), len(auth), len(body)) + auth + body
        lane = "control" if operation in CONTROL else "mutation"
        deadline = time.monotonic() + self.timeout
        try:
            root = _directory(self.directory, owner=self.server_uid, private=False)
            path = root / (lane + ".sock")
            info = path.lstat()
            if (not stat.S_ISSOCK(info.st_mode) or info.st_uid != self.server_uid
                    or info.st_mode & 0o007):
                raise InstallerBackendError("unsafe_socket")
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                _remaining(conn, deadline)
                conn.connect(str(path))
                _peer(conn, self.server_uid)
                _remaining(conn, deadline)
                conn.sendall(frame)
                length, = struct.unpack("!I", _read(conn, 4, deadline))
                if not 1 <= length <= MAX_REPLY_BYTES:
                    raise InstallerBackendError("invalid_response")
                reply = json.loads(_read(conn, length, deadline), object_pairs_hook=_pairs)
                if (type(reply) is not dict or set(reply) != {"host_id", "result"}
                        or reply["host_id"] != self.host_id or type(reply["result"]) is not dict
                        or type(reply["result"].get("ok")) is not bool):
                    raise InstallerBackendError("invalid_response")
                return reply["result"]
        except Exception:
            result = {"ok": False, "error": "response_unavailable", "outcome": "unknown"}
            ident = request.get("target") if operation in ("rollback", "resume") else request.get("request_id")
            if type(ident) is str and re.fullmatch(r"[a-f0-9]{32}", ident):
                result["request_id"] = ident
            return result


def _sanitize_result(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        copy = json.loads(encoded, object_pairs_hook=_pairs)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise InstallerBackendError("invalid_response") from None
    if len(encoded) > MAX_REPLY_BYTES or type(copy) is not dict or type(copy.get("ok")) is not bool:
        raise InstallerBackendError("invalid_response")
    stack = [copy]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            if any(str(key).lower() in SECRET_KEYS for key in item):
                raise InstallerBackendError("secret_in_response")
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return copy


class InstallerBackend:
    """Own the stored credential and expose only sanitized installer results."""

    def __init__(self, credential_store, socket_directory, *, server_uid,
                 timeout=10.0, client_factory: Callable = UnixInstallerClient):
        if type(credential_store) is not InstallerCredentialStore or not callable(client_factory):
            raise InstallerBackendError("invalid_backend")
        self.credential_store = credential_store
        self.socket_directory = Path(socket_directory)
        self.server_uid = _uid(server_uid)
        self.timeout = _seconds(timeout)
        self.client_factory = client_factory

    def adopt_handoff(self, directory):
        return self.credential_store.adopt_handoff(directory)

    def credential_status(self):
        return self.credential_store.public_status()

    def request(self, request):
        credential = self.credential_store.load()
        client = self.client_factory(self.socket_directory, host_id=credential.host_id,
                                     server_uid=self.server_uid, timeout=self.timeout)
        return _sanitize_result(client.request(credential.token, request))
