"""Protected connection offer shared by a trusted local installer and HA.

This is not an enrollment endpoint. The caller must obtain directory, host and
principal pins from the already verified installer endpoint and credential store.
Offers are never deleted by HA merely because an in-memory options update exists.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys

from .slicer_connection_settings import normalize_slicer_base_url, validate_slicer_api_secret

CONNECTION_FILE = "slicer-connection.json"
MAX_CONNECTION_BYTES = 8192
FIELDS = frozenset(("schema", "host_id", "principal", "transfer_id", "base_url", "api_secret"))


class ConnectionHandoffError(ValueError):
    """Stable, non-secret connection delivery error."""


def _reject(code):
    raise ConnectionHandoffError(code)


def _identity(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{32}", value) is None:
        _reject("invalid_connection_handoff")
    return value


def _principal(value):
    if type(value) is not str or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value) is None:
        _reject("invalid_connection_handoff")
    return value


def _uid(value):
    if type(value) is not int or not 0 <= value < 2**32:
        _reject("invalid_connection_handoff")
    return value


def _pairs(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            _reject("invalid_connection_handoff")
        result[name] = value
    return result


def _constant(_value):
    _reject("invalid_connection_handoff")


@dataclass(frozen=True, repr=False)
class ConnectionOffer:
    host_id: str
    principal: str
    transfer_id: str
    base_url: str
    api_secret: str
    raw_sha256: str
    file_identity: tuple | None = None
    directory_identity: tuple | None = None

    def same_file(self, other):
        return (type(other) is ConnectionOffer
                and secrets.compare_digest(self.raw_sha256, other.raw_sha256)
                and self.file_identity == other.file_identity
                and self.directory_identity == other.directory_identity)


def decode_connection_offer(raw, *, expected_host_id, expected_principal):
    host = _identity(expected_host_id)
    principal = _principal(expected_principal)
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_CONNECTION_BYTES:
        _reject("invalid_connection_handoff")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs, parse_constant=_constant)
        if (type(value) is not dict or set(value) != FIELDS
                or type(value["schema"]) is not int or value["schema"] != 1
                or value["host_id"] != host or value["principal"] != principal):
            _reject("invalid_connection_handoff")
        transfer = _identity(value["transfer_id"])
        if type(value["base_url"]) is not str or type(value["api_secret"]) is not str:
            _reject("invalid_connection_handoff")
        endpoint = normalize_slicer_base_url(value["base_url"])
        secret = validate_slicer_api_secret(value["api_secret"])
        # Automatic cross-host provisioning never inherits the manual loopback exception.
        if not endpoint.startswith("https://") or endpoint != value["base_url"]:
            _reject("invalid_connection_handoff")
    except ConnectionHandoffError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ConnectionHandoffError("invalid_connection_handoff") from None
    return ConnectionOffer(host, principal, transfer, endpoint, secret, hashlib.sha256(raw).hexdigest())


def _directory(directory, server_uid):
    root = Path(directory)
    if not root.is_absolute() or ".." in root.parts:
        _reject("unsafe_connection_handoff")
    for item in (root, *root.parents):
        if item.is_symlink() or getattr(item, "is_junction", lambda: False)():
            _reject("unsafe_connection_handoff")
    info = root.stat()
    if not stat.S_ISDIR(info.st_mode):
        _reject("unsafe_connection_handoff")
    if os.name != "nt" and (info.st_uid != server_uid or info.st_mode & 0o027):
        _reject("unsafe_connection_handoff")
    return root, (info.st_dev, info.st_ino)


def _stat_identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)



def _same_open_file(path_info, descriptor_info):
    # Windows path stat historically exposes creation time in st_ctime_ns,
    # while descriptor stat may expose metadata change time. Compare their
    # shared identity fields, then independently compare each API before/after.
    # POSIX keeps the full cross-API metadata comparison including ctime.
    path_identity = _stat_identity(path_info)
    descriptor_identity = _stat_identity(descriptor_info)
    if os.name == "nt":
        return path_identity[:-1] == descriptor_identity[:-1]
    return path_identity == descriptor_identity


def _read(directory, *, server_uid, recipient_uid, expected_host_id, expected_principal):
    root, directory_identity = _directory(directory, server_uid)
    path = root / CONNECTION_FILE
    before = path.lstat()
    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
            or not 1 <= before.st_size <= MAX_CONNECTION_BYTES):
        _reject("unsafe_connection_handoff")
    if os.name != "nt" and (before.st_uid != recipient_uid or stat.S_IMODE(before.st_mode) != 0o400):
        _reject("unsafe_connection_handoff")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not _same_open_file(before, opened):
            _reject("connection_handoff_changed")
        raw = stream.read(MAX_CONNECTION_BYTES + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    if (len(raw) != before.st_size or _stat_identity(opened) != _stat_identity(after)
            or _stat_identity(before) != _stat_identity(current)
            or _directory(directory, server_uid)[1] != directory_identity):
        _reject("connection_handoff_changed")
    offer = decode_connection_offer(raw, expected_host_id=expected_host_id,
                                    expected_principal=expected_principal)
    return ConnectionOffer(offer.host_id, offer.principal, offer.transfer_id,
                           offer.base_url, offer.api_secret, offer.raw_sha256,
                           (_stat_identity(before), _stat_identity(opened)), directory_identity)


def read_connection_offer(directory, *, server_uid, expected_host_id, expected_principal):
    """Receiving identity reads a fixed filename under the independently pinned mount."""
    try:
        return _read(directory, server_uid=_uid(server_uid),
                     recipient_uid=os.geteuid() if hasattr(os, "geteuid") else None,
                     expected_host_id=expected_host_id, expected_principal=expected_principal)
    except ConnectionHandoffError:
        raise
    except FileNotFoundError:
        raise ConnectionHandoffError("connection_handoff_missing") from None
    except OSError:
        raise ConnectionHandoffError("unsafe_connection_handoff") from None


def encode_connection_offer(*, host_id, principal, transfer_id, base_url, api_secret):
    """Construct bounded canonical bytes; never place these bytes in logs or UI results."""
    try:
        raw = json.dumps({"schema": 1, "host_id": host_id, "principal": principal,
                          "transfer_id": transfer_id, "base_url": base_url, "api_secret": api_secret},
                         sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        decode_connection_offer(raw, expected_host_id=host_id, expected_principal=principal)
    except ConnectionHandoffError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ConnectionHandoffError("invalid_connection_handoff") from None
    return raw


def publish_connection_offer(directory, *, host_id, principal, transfer_id,
                             base_url, api_secret, recipient_uid, recipient_gid):
    """Trusted Linux root only; atomic no-overwrite publication, idempotent same offer.

The directory must already be provisioned. Existing or uncertain deliveries are
retained; credential rotation requires a separately confirmed reconciliation.
"""
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        _reject("connection_publisher_unavailable")
    uid, gid = _uid(recipient_uid), _uid(recipient_gid)
    raw = encode_connection_offer(host_id=host_id, principal=principal, transfer_id=transfer_id,
                                  base_url=base_url, api_secret=api_secret)
    root, directory_identity = _directory(directory, 0)
    if root.stat().st_gid != gid:
        _reject("unsafe_connection_handoff")
    import fcntl
    lock = os.open(root / ".slicer-connection.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    temporary = None
    try:
        info = os.fstat(lock)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600:
            _reject("unsafe_connection_handoff")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ConnectionHandoffError("connection_handoff_busy") from None
        target = root / CONNECTION_FILE
        if target.exists() or target.is_symlink():
            previous = _read(root, server_uid=0, recipient_uid=uid,
                             expected_host_id=host_id, expected_principal=principal)
            if not secrets.compare_digest(previous.raw_sha256, hashlib.sha256(raw).hexdigest()):
                _reject("connection_handoff_occupied")
            return {"published": True, "already_present": True}
        temporary = root / (".connection-" + secrets.token_hex(16) + ".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fchown(stream.fileno(), uid, gid)
            os.fchmod(stream.fileno(), 0o400)
            os.fsync(stream.fileno())
        if _directory(directory, 0)[1] != directory_identity:
            _reject("connection_handoff_changed")
        # link() cannot replace another administrator's concurrently published file.
        os.link(temporary, target, follow_symlinks=False)
        temporary.unlink()
        temporary = None
        dfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        delivered = _read(root, server_uid=0, recipient_uid=uid,
                          expected_host_id=host_id, expected_principal=principal)
        if not secrets.compare_digest(delivered.raw_sha256, hashlib.sha256(raw).hexdigest()):
            _reject("connection_handoff_changed")
        return {"published": True, "already_present": False}
    except ConnectionHandoffError:
        raise
    except OSError:
        raise ConnectionHandoffError("connection_publication_unconfirmed") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        os.close(lock)
