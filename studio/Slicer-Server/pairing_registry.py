"""Local pairing registry. No listener, shell, engine or secret logging.

See HOST_PAIRING.md. The provisioned directory and its owner are trusted.
A hostile process with the same OS identity is outside this boundary.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

import package_activation as activation
from restricted_installer import Credential, SCOPES, _credentials_snapshot

MAX_BYTES = 65536
MAX_PRINCIPALS = 128


class RegistryError(ValueError):
    """Stable local administration error codes."""


def _principal(value):
    if type(value) is not str or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value) is None:
        raise RegistryError("invalid_principal")
    return value


def _scopes(value):
    if type(value) is not frozenset or not value or not value <= SCOPES:
        raise RegistryError("invalid_scopes")
    return sorted(value)


def _directory(directory):
    path = Path(directory)
    if not path.is_absolute() or ".." in path.parts:
        raise RegistryError("unsafe_registry_directory")
    activation._safe_path(path)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode):
        raise RegistryError("unsafe_registry_directory")
    if os.name != "nt" and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise RegistryError("unsafe_registry_directory")
    return path


def _file_info(info):
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise RegistryError("unsafe_registry_file")
    if os.name != "nt" and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise RegistryError("unsafe_registry_file")


def _open(path, flags):
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise RegistryError("unsafe_registry_file")
    try:
        _file_info(path.lstat())
    except FileNotFoundError:
        pass
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0), 0o600)
    try:
        info = os.fstat(fd)
        _file_info(info)
        current = path.lstat()
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise RegistryError("registry_file_changed")
    except BaseException:
        os.close(fd)
        raise
    return fd


@contextmanager
def _locked(directory):
    directory = _directory(directory)
    fd = _open(directory / ".registry.lock", os.O_RDWR | os.O_CREAT)
    try:
        if os.fstat(fd).st_size > 1:
            raise RegistryError("unsafe_registry_lock")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RegistryError("registry_busy") from None
        try:
            yield directory
        finally:
            if os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise RegistryError("invalid_registry")
        result[key] = value
    return result


def _validate(value, host_id):
    if (type(value) is not dict or set(value) != {"schema", "host_id", "revision", "entries"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or value["host_id"] != host_id
            or type(value["revision"]) is not int or not 0 <= value["revision"] < 2**63
            or type(value["entries"]) is not list or len(value["entries"]) > MAX_PRINCIPALS):
        raise RegistryError("invalid_registry")
    credentials = []
    for entry in value["entries"]:
        if (type(entry) is not dict
                or set(entry) != {"principal", "token_sha256", "scopes", "state"}
                or type(entry["token_sha256"]) is not str
                or re.fullmatch(r"[a-f0-9]{64}", entry["token_sha256"]) is None
                or type(entry["scopes"]) is not list
                or any(type(s) is not str for s in entry["scopes"])
                or entry["scopes"] != sorted(set(entry["scopes"]))
                or entry["state"] not in ("active", "revoked")):
            raise RegistryError("invalid_registry")
        _principal(entry["principal"])
        _scopes(frozenset(entry["scopes"]))
        credentials.append(Credential(entry["principal"],
                                      bytes.fromhex(entry["token_sha256"]),
                                      frozenset(entry["scopes"])))
    _credentials_snapshot(tuple(credentials), allow_empty=True)
    return value


def initialize(directory):
    """Initialize an empty, already privately provisioned directory once."""
    with _locked(directory) as root:
        if set(p.name for p in root.iterdir()) != {".registry.lock"}:
            raise RegistryError("registry_directory_not_empty")
        host_id = secrets.token_hex(16)
        value = {"schema": 1, "host_id": host_id, "revision": 0, "entries": []}
        activation._atomic_json(root / "REGISTRY.json", value)
        Registry(root, host_id).snapshot()
        return host_id


class Registry:
    """Trusted local provider/admin API; expected host ID is externally pinned."""

    def __init__(self, directory, host_id):
        if type(host_id) is not str or re.fullmatch(r"[a-f0-9]{32}", host_id) is None:
            raise RegistryError("invalid_host_id")
        self.directory = _directory(directory)
        self.host_id = host_id
        self._read()

    def _read(self):
        root = _directory(self.directory)
        fd = _open(root / "REGISTRY.json", os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            if os.fstat(stream.fileno()).st_size > MAX_BYTES:
                raise RegistryError("registry_too_large")
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise RegistryError("registry_too_large")
        try:
            value = json.loads(data, object_pairs_hook=_pairs)
        except (ValueError, UnicodeError, RecursionError):
            raise RegistryError("invalid_registry") from None
        return _validate(value, self.host_id)

    def snapshot(self):
        """Read fresh on each call; failure must never reuse old credentials."""
        value = self._read()
        return tuple(Credential(e["principal"], bytes.fromhex(e["token_sha256"]),
                                frozenset(e["scopes"]))
                     for e in value["entries"] if e["state"] == "active")

    def _commit(self, value):
        value["revision"] += 1
        _validate(value, self.host_id)
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
        if len(encoded) > MAX_BYTES:
            raise RegistryError("registry_too_large")
        activation._atomic_json(self.directory / "REGISTRY.json", value)

    def issue(self, principal, scopes):
        """Return a new secret once to the trusted local caller, never persist it."""
        principal, scopes = _principal(principal), _scopes(scopes)
        with _locked(self.directory):
            value = self._read()
            if any(e["principal"] == principal for e in value["entries"]):
                raise RegistryError("principal_reserved")
            if len(value["entries"]) >= MAX_PRINCIPALS:
                raise RegistryError("registry_capacity")
            token = secrets.token_urlsafe(48)
            value["entries"].append({"principal": principal, "scopes": scopes,
                                     "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
                                     "state": "active"})
            self._commit(value)
            return token

    def rotate(self, principal, *, scopes=None):
        principal = _principal(principal)
        if scopes is not None:
            scopes = _scopes(scopes)
        with _locked(self.directory):
            value = self._read()
            entry = self._active(value, principal)
            token = secrets.token_urlsafe(48)
            entry["token_sha256"] = hashlib.sha256(token.encode("ascii")).hexdigest()
            if scopes is not None:
                entry["scopes"] = scopes
            self._commit(value)
            return token

    @staticmethod
    def _active(value, principal):
        entry = next((e for e in value["entries"] if e["principal"] == principal), None)
        if entry is None or entry["state"] != "active":
            raise RegistryError("principal_not_active")
        return entry

    def revoke(self, principal):
        principal = _principal(principal)
        with _locked(self.directory):
            value = self._read()
            entry = next((e for e in value["entries"] if e["principal"] == principal), None)
            if entry is None:
                raise RegistryError("unknown_principal")
            if entry["state"] == "revoked":
                return
            entry["state"] = "revoked"
            self._commit(value)
