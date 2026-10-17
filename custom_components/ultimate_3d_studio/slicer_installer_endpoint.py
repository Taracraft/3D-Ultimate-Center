"""Load the host-provisioned installer endpoint only from fixed protected mounts.

The endpoint descriptor and its local pins are separate read-only bind mounts.
No UI, request, ConfigFlow, forwarded header, or handoff value is a trust source.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

MAX_ENDPOINT_BYTES = 4096
PIN_DIRECTORY = "/run/ultimate-slicer-server/pins"
PIN_FILE = PIN_DIRECTORY + "/expected.json"
ENDPOINT_DIRECTORY = "/run/ultimate-slicer-server/installer"
ENDPOINT_FILE = ENDPOINT_DIRECTORY + "/endpoint.json"
HANDOFF_DIRECTORY = "/run/ultimate-slicer-server/handoff"
MOUNTINFO_FILE = "/proc/self/mountinfo"
_REQUIRED_KEYS = frozenset(
    ("schema", "host_id", "server_uid", "socket_directory", "handoff_directory")
)
_ENDPOINT_MODES = frozenset((0o444,))
_MOUNTINFO_LIMIT = 1024 * 1024


class InstallerEndpointError(ValueError):
    """Stable error for absent, malformed, or untrusted endpoint metadata."""


@dataclass(frozen=True)
class InstallerEndpoint:
    """Validated fixed endpoint values for one locally provisioned host."""

    host_id: str
    server_uid: int
    socket_directory: str
    handoff_directory: str


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InstallerEndpointError("duplicate_endpoint_key")
        result[key] = value
    return result


def _constant(_value):
    raise InstallerEndpointError("invalid_endpoint_json")


def _host_id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise InstallerEndpointError("invalid_host_id")
    return value


def _uid(value):
    if type(value) is not int or not 0 <= value < 2**32:
        raise InstallerEndpointError("invalid_server_uid")
    return value


def _path(value, field):
    if type(value) is not str or not value.startswith("/") or "//" in value:
        raise InstallerEndpointError("invalid_" + field)
    path = PurePosixPath(value)
    if (path.as_posix() != value or any(part in (".", "..") for part in path.parts)
            or path == PurePosixPath("/")):
        raise InstallerEndpointError("invalid_" + field)
    return path


def _decode_record(payload, *, size_error, json_error, schema_error):
    if type(payload) is not bytes or not 1 <= len(payload) <= MAX_ENDPOINT_BYTES:
        raise InstallerEndpointError(size_error)
    try:
        value = json.loads(payload.decode("ascii"), object_pairs_hook=_pairs, parse_constant=_constant)
    except InstallerEndpointError:
        raise
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise InstallerEndpointError(json_error) from None
    if (type(value) is not dict or set(value) != _REQUIRED_KEYS
            or type(value["schema"]) is not int or value["schema"] != 1):
        raise InstallerEndpointError(schema_error)
    return value


def _endpoint_from_record(value):
    host_id = _host_id(value["host_id"])
    server_uid = _uid(value["server_uid"])
    socket_directory = _path(value["socket_directory"], "socket_directory")
    handoff_directory = _path(value["handoff_directory"], "handoff_directory")
    if (socket_directory == handoff_directory
            or socket_directory in handoff_directory.parents
            or handoff_directory in socket_directory.parents):
        raise InstallerEndpointError("overlapping_endpoint_directories")
    return InstallerEndpoint(
        host_id=host_id,
        server_uid=server_uid,
        socket_directory=socket_directory.as_posix(),
        handoff_directory=handoff_directory.as_posix(),
    )


def decode_installer_endpoint_pins(payload: bytes) -> InstallerEndpoint:
    """Decode the separately provisioned, locally trusted pin record."""
    value = _decode_record(payload, size_error="invalid_pin_size",
                           json_error="invalid_pin_json", schema_error="invalid_pin_schema")
    return _endpoint_from_record(value)


def decode_installer_endpoint(
    payload: bytes,
    *,
    expected_host_id: str,
    expected_server_uid: int,
    expected_socket_directory: str,
    expected_handoff_directory: str,
) -> InstallerEndpoint:
    """Decode endpoint metadata matching identity and path pins from host provisioning."""
    expected = _endpoint_from_record({
        "host_id": expected_host_id,
        "server_uid": expected_server_uid,
        "socket_directory": expected_socket_directory,
        "handoff_directory": expected_handoff_directory,
    })
    value = _decode_record(payload, size_error="invalid_endpoint_size",
                           json_error="invalid_endpoint_json", schema_error="invalid_endpoint_schema")
    actual = _endpoint_from_record(value)
    if actual != expected:
        raise InstallerEndpointError("endpoint_pin_mismatch")
    return actual


def _unescape_mount_field(value):
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def _mount_entries(mountinfo_text):
    if type(mountinfo_text) is not str or len(mountinfo_text.encode("utf-8")) > _MOUNTINFO_LIMIT:
        raise InstallerEndpointError("invalid_mountinfo")
    entries = []
    for line in mountinfo_text.splitlines():
        before, separator, _after = line.partition(" - ")
        fields = before.split()
        if not separator or len(fields) < 6:
            raise InstallerEndpointError("invalid_mountinfo")
        try:
            mount_id = int(fields[0], 10)
        except ValueError:
            raise InstallerEndpointError("invalid_mountinfo") from None
        mountpoint = _unescape_mount_field(fields[4])
        options = frozenset(fields[5].split(","))
        if mount_id <= 0 or not mountpoint.startswith("/") or not options:
            raise InstallerEndpointError("invalid_mountinfo")
        entries.append((mount_id, mountpoint, options))
    if not entries:
        raise InstallerEndpointError("invalid_mountinfo")
    return entries


def _covering_mount(path, entries):
    path = PurePosixPath(path).as_posix()
    matches = []
    for entry in entries:
        mountpoint = entry[1].rstrip("/") or "/"
        if path == mountpoint or mountpoint == "/" or path.startswith(mountpoint + "/"):
            matches.append(entry)
    if not matches:
        raise InstallerEndpointError("endpoint_mount_missing")
    def _specificity(entry):
        return len(entry[1].rstrip("/") or "/")
    longest = max(_specificity(entry) for entry in matches)
    most_specific = [entry for entry in matches if _specificity(entry) == longest]
    if len(most_specific) != 1:
        raise InstallerEndpointError("endpoint_mount_ambiguous")
    return most_specific[0]


def _validate_mount_layout(pin_file, endpoint_file, handoff_directory, mountinfo_text):
    entries = _mount_entries(mountinfo_text)
    pin_mount = _covering_mount(pin_file, entries)
    endpoint_mount = _covering_mount(endpoint_file, entries)
    handoff_mount = _covering_mount(handoff_directory, entries)
    if (pin_mount[1] != PIN_DIRECTORY or "ro" not in pin_mount[2]
            or endpoint_mount[1] != ENDPOINT_DIRECTORY or "ro" not in endpoint_mount[2]
            or handoff_mount[1] != HANDOFF_DIRECTORY or "ro" in handoff_mount[2]):
        raise InstallerEndpointError("endpoint_mount_policy")
    if len({pin_mount[0], endpoint_mount[0], handoff_mount[0]}) != 3:
        raise InstallerEndpointError("endpoint_mount_separation")


def _read_record(path, *, owner_uid, mode):
    path = Path(path)
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or not 1 <= info.st_size <= MAX_ENDPOINT_BYTES):
            raise InstallerEndpointError("unsafe_endpoint_file")
        if os.name != "nt" and (info.st_uid != owner_uid or stat.S_IMODE(info.st_mode) != mode):
            raise InstallerEndpointError("unsafe_endpoint_file")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "rb") as stream:
            current = os.fstat(stream.fileno())
            if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                raise InstallerEndpointError("endpoint_file_changed")
            data = stream.read(MAX_ENDPOINT_BYTES + 1)
        if len(data) > MAX_ENDPOINT_BYTES:
            raise InstallerEndpointError("unsafe_endpoint_file")
        return data
    except InstallerEndpointError:
        raise
    except OSError:
        raise InstallerEndpointError("provisioned_endpoint_unavailable") from None


def _load_provisioned_installer_endpoint_at(*, pin_file, endpoint_file, handoff_directory, mountinfo_file):
    """Internal injectable loader; production wrapper below uses fixed paths only."""
    try:
        mountinfo = Path(mountinfo_file).read_text(encoding="ascii")
    except (OSError, UnicodeError):
        raise InstallerEndpointError("provisioned_endpoint_unavailable") from None
    _validate_mount_layout(str(pin_file), str(endpoint_file), str(handoff_directory), mountinfo)
    pin_bytes = _read_record(pin_file, owner_uid=0, mode=0o444)
    pins = decode_installer_endpoint_pins(pin_bytes)
    endpoint_bytes = _read_record(endpoint_file, owner_uid=pins.server_uid, mode=0o444)
    return decode_installer_endpoint(
        endpoint_bytes, expected_host_id=pins.host_id, expected_server_uid=pins.server_uid,
        expected_socket_directory=pins.socket_directory, expected_handoff_directory=pins.handoff_directory,
    )


def load_provisioned_installer_endpoint() -> InstallerEndpoint:
    """Read only the fixed host mounts; never accept caller-selected paths."""
    return _load_provisioned_installer_endpoint_at(
        pin_file=PIN_FILE, endpoint_file=ENDPOINT_FILE,
        handoff_directory=HANDOFF_DIRECTORY, mountinfo_file=MOUNTINFO_FILE,
    )

