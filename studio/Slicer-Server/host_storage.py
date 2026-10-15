"""Linux persistent-volume provisioning for the restricted installer.

Only local trusted host setup calls this module. No mount, Docker, service,
engine or package-manager command is executed. See HOST_STORAGE.md.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import os
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat

import package_activation as activation

DEFAULT_BASE = Path("/var/lib/ultimate-slicer-server")
MAX_MOUNTINFO = 4 * 1024**2
SUPPORTED_FILESYSTEMS = frozenset(("ext4", "xfs"))
LAYOUT = ("engines", "data", "profiles")
MIN_FREE_BYTES = 256 * 1024**2
RUNTIME_GID = 65532
RUNTIME_MODE = 0o2770
MUTABLE_LAYOUT = ("data", "profiles")


class StorageError(ValueError):
    """Stable code, never include private paths or device identities."""


@dataclass(frozen=True)
class Mount:
    mount_id: int
    device: str
    root: str
    point: str
    filesystem: str
    writable: bool


@dataclass(frozen=True)
class Volume:
    uuid: str
    root: str
    point: str
    filesystem: str


def _unescape(value):
    def replace(match):
        code = match.group(0)
        if code not in (r"\040", r"\011", r"\012", r"\134"):
            raise StorageError("invalid_mountinfo")
        return chr(int(code[1:], 8))
    result = re.sub(r"\\[0-7]{3}", replace, value)
    if "\\" in re.sub(r"\\[0-7]{3}", "", value):
        raise StorageError("invalid_mountinfo")
    return result


def parse_mountinfo(data: bytes) -> tuple[Mount, ...]:
    if type(data) is not bytes or len(data) > MAX_MOUNTINFO:
        raise StorageError("mountinfo_size")
    try:
        text = data.decode("utf-8")
        records = []
        ids = set()
        for line in text.splitlines():
            left, right = line.split(" - ", 1)
            fields, tail = left.split(), right.split()
            if len(fields) < 6 or len(tail) != 3:
                raise ValueError()
            ident = int(fields[0])
            int(fields[1])
            if ident <= 0 or ident in ids or not re.fullmatch(r"[0-9]+:[0-9]+", fields[2]):
                raise ValueError()
            ids.add(ident)
            root, point = _unescape(fields[3]), _unescape(fields[4])
            if (not point.startswith("/") or not root
                    or (tail[0] in SUPPORTED_FILESYSTEMS and not root.startswith("/"))):
                raise ValueError()
            records.append(Mount(ident, fields[2], root, point, tail[0],
                                 "rw" in fields[5].split(",") and "ro" not in fields[5].split(",")
                                 and "rw" in tail[2].split(",") and "ro" not in tail[2].split(",")))
        if not records:
            raise ValueError()
        return tuple(records)
    except (UnicodeError, ValueError):
        raise StorageError("invalid_mountinfo") from None


def select_mount(records, path: str, device: str) -> Mount:
    target = PurePosixPath(path)
    if not target.is_absolute() or ".." in target.parts:
        raise StorageError("invalid_storage_path")
    candidates = [m for m in records if target.is_relative_to(PurePosixPath(m.point))]
    if not candidates:
        raise StorageError("mount_not_found")
    longest = max(len(PurePosixPath(m.point).parts) for m in candidates)
    matches = [m for m in candidates if len(PurePosixPath(m.point).parts) == longest]
    # Overmounted/stacked entries cannot be disambiguated by st_dev alone.
    if len(matches) != 1:
        raise StorageError("ambiguous_mount")
    selected = matches[0]
    if selected.device != device:
        raise StorageError("mount_device_mismatch")
    if selected.filesystem not in SUPPORTED_FILESYSTEMS:
        raise StorageError("unsupported_persistent_filesystem")
    if not selected.writable:
        raise StorageError("read_only_volume")
    return selected


def _safe_directory(path, *, missing=False, runtime_data=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise StorageError("invalid_storage_path")
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise StorageError("linked_storage_path")
        if part.exists():
            info = part.stat()
            if not stat.S_ISDIR(info.st_mode):
                raise StorageError("invalid_storage_path")
            if os.name != "nt" and runtime_data and part == path:
                if (info.st_uid != 0 or info.st_gid != RUNTIME_GID
                        or stat.S_IMODE(info.st_mode) != RUNTIME_MODE):
                    raise StorageError("runtime_directory_permissions")
                if any(name in os.listxattr(part) for name in
                       ("system.posix_acl_access", "system.posix_acl_default")):
                    raise StorageError("runtime_directory_acl")
                continue
            if os.name != "nt" and (info.st_uid not in (0, os.geteuid()) or info.st_mode & 0o022):
                # A sticky shared /tmp is allowed only as a test ancestor, never
                # by native probing: temporary paths are explicitly rejected.
                if part != Path("/tmp") or not info.st_mode & stat.S_ISVTX:
                    raise StorageError("unsafe_storage_ancestor")
    if not missing and not path.is_dir():
        raise StorageError("storage_path_missing")
    return path


def native_volume(path: Path, *, runtime_data=False) -> Volume:
    """Read-only proof using current mountinfo, st_dev and udev UUID device links."""
    if platform.system() != "Linux":
        raise StorageError("linux_host_required")
    target = PurePosixPath(str(path))
    if any(target.is_relative_to(root) for root in ("/tmp", "/var/tmp", "/run", "/dev", "/proc", "/sys")):
        raise StorageError("temporary_storage_path")
    path = _safe_directory(path, missing=True, runtime_data=runtime_data)
    existing = path
    while not existing.exists():
        existing = existing.parent
    info = existing.stat()
    with Path("/proc/self/mountinfo").open("rb") as stream:
        records = parse_mountinfo(stream.read(MAX_MOUNTINFO + 1))
    mount = select_mount(records, str(existing), f"{os.major(info.st_dev)}:{os.minor(info.st_dev)}")
    uuid = _uuid_for_device(info.st_dev)
    return Volume(uuid, mount.root, mount.point, mount.filesystem)


def _uuid_for_device(device_id):
    uuid_root = Path("/dev/disk/by-uuid")
    if not uuid_root.is_dir():
        raise StorageError("filesystem_uuid_unavailable")
    matches = []
    for entry in uuid_root.iterdir():
        if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", entry.name):
            continue
        try:
            device = entry.stat()
        except OSError:
            continue
        if stat.S_ISBLK(device.st_mode) and device.st_rdev == device_id:
            matches.append(entry.name)
    if len(matches) != 1:
        raise StorageError("filesystem_uuid_ambiguous")
    return matches[0]


def _control(control):
    path = _safe_directory(control)
    if os.name != "nt":
        mode = path.stat().st_mode
        if path.stat().st_uid != os.geteuid() or mode & 0o077:
            raise StorageError("private_control_required")
    transactions = path / "transactions"
    if not transactions.exists():
        transactions.mkdir(mode=0o700)
    _safe_directory(transactions)
    lock = transactions / "install.lock"
    if lock.is_symlink() or getattr(lock, "is_junction", lambda: False)():
        raise StorageError("unsafe_control_state")
    return path


def _read_binding(control):
    path = control / "VOLUME.json"
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise StorageError("unsafe_control_state")
    if not path.is_file():
        raise StorageError("volume_not_bound")
    if os.name != "nt" and (path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o077):
        raise StorageError("unsafe_control_state")
    value = activation._read_json(path, maximum=8192)
    if (set(value) != {"schema", "state", "base", "volume"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or value["state"] not in ("provisioning", "ready")
            or type(value["base"]) is not str or type(value["volume"]) is not dict
            or set(value["volume"]) != {"uuid", "root", "point", "filesystem"}
            or any(type(v) is not str or not v for v in value["volume"].values())):
        raise StorageError("invalid_volume_binding")
    return value


def provision(control: Path, *, base: Path | None = None,
              approved_roots: tuple[Path, ...] = (Path("/var/lib"),),
              observe=native_volume) -> dict:
    """Create a new owned layout under an explicitly approved local root.

    The native default is /var/lib/ultimate-slicer-server. Remote requests may
    not select observe, approved_roots or an arbitrary path. A future host
    pairing operation owns advanced path validation and authorization.
    """
    control = _control(control)
    base = _safe_directory(base if base is not None else DEFAULT_BASE, missing=True)
    roots = tuple(_safe_directory(p) for p in approved_roots)
    if not roots or not any(base != p and base.is_relative_to(p) for p in roots):
        raise StorageError("storage_outside_approved_roots")
    if control == base or control in base.parents or base in control.parents:
        raise StorageError("control_store_overlap")
    # Do not synthesize intermediate paths or silently traverse a missing mount.
    _safe_directory(base.parent)
    with activation._store_lock(control):
        if (control / "VOLUME.json").exists():
            guard = VolumeGuard(control, observe=observe)
            if guard.binding["base"] != str(base):
                raise StorageError("storage_binding_mismatch")
            guard.check()
            return guard.layout()
        if base.exists() and any(base.iterdir()):
            raise StorageError("storage_not_empty")
        first = observe(base)
        if type(first) is not Volume or first.filesystem not in SUPPORTED_FILESYSTEMS:
            raise StorageError("invalid_volume_evidence")
        if shutil.disk_usage(base if base.exists() else base.parent).free < MIN_FREE_BYTES:
            raise StorageError("insufficient_storage_space")
        # Durable intent outside the volume precedes all layout mutations. An
        # interrupted provisioning needs explicit local reconciliation.
        binding = {"schema": 1, "state": "provisioning", "base": str(base), "volume": asdict(first)}
        activation._atomic_json(control / "VOLUME.json", binding)
        if observe(base) != first:
            raise StorageError("volume_changed")
        if not base.exists():
            base.mkdir(mode=0o700)
        for name in LAYOUT:
            (base / name).mkdir(mode=0o700)
        activation._fsync_directory(base)
        activation._fsync_directory(base.parent)
        if observe(base) != first:
            raise StorageError("volume_changed")
        for name in LAYOUT:
            if observe(base / name) != first:
                raise StorageError("nested_volume_mismatch")
        binding["state"] = "ready"
        activation._atomic_json(control / "VOLUME.json", binding)
        guard = VolumeGuard(control, observe=observe)
        guard.check()
        return guard.layout()


class VolumeGuard:
    """Callable directly usable as restricted_installer.verify_volume."""

    def __init__(self, control: Path, *, observe=native_volume):
        self.control = _control(control)
        self.binding = _read_binding(self.control)
        self.observe = observe

    def check(self):
        current = _read_binding(self.control)
        if current != self.binding:
            raise StorageError("volume_binding_changed")
        if current["state"] != "ready":
            raise StorageError("provisioning_reconciliation_required")
        base = _safe_directory(Path(current["base"]))
        if base == self.control or self.control in base.parents or base in self.control.parents:
            raise StorageError("control_store_overlap")
        runtime = _runtime_permissions(self.control, current)
        expected = Volume(**current["volume"])
        for path in (base, *(base / name for name in LAYOUT)):
            mutable = runtime is not None and path != base and path.name in MUTABLE_LAYOUT
            _safe_directory(path, runtime_data=mutable)
            observed = (native_volume(path, runtime_data=mutable)
                        if self.observe is native_volume else self.observe(path))
            if observed != expected:
                raise StorageError("volume_changed")
        return True

    def __call__(self):
        # Never downgrade a failed native check to a permissive fallback.
        try:
            return self.check()
        except (StorageError, activation.ActivationError, OSError):
            return False

    def layout(self):
        base = Path(self.binding["base"])
        return {"base": base, "engines": base / "engines",
                "data": base / "data", "profiles": base / "profiles"}


def _volume_digest(binding):
    return hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _runtime_permissions(control, binding):
    path = Path(control) / "PERMISSIONS.json"
    if path.is_symlink():
        raise StorageError("unsafe_runtime_permissions")
    if not path.exists():
        return None
    info = path.stat()
    if (not stat.S_ISREG(info.st_mode) or
            (os.name != "nt" and (info.st_uid != os.geteuid() or info.st_mode & 0o077))):
        raise StorageError("unsafe_runtime_permissions")
    value = activation._read_json(path, maximum=4096)
    if (set(value) != {"schema", "state", "volume_sha256", "gid", "mode"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or type(value["gid"]) is not int or value["gid"] != RUNTIME_GID
            or type(value["mode"]) is not int or value["mode"] != RUNTIME_MODE
            or value["volume_sha256"] != _volume_digest(binding)
            or value["state"] not in ("preparing", "ready")):
        raise StorageError("invalid_runtime_permissions")
    if value["state"] != "ready":
        raise StorageError("runtime_permissions_reconciliation_required")
    if os.name == "nt":
        raise StorageError("linux_runtime_permissions_required")
    return value


def grant_runtime_access(control: Path, workers_stopped, *, observe=native_volume):
    """Trusted local Linux/root operation; only initially empty data/profile roots.

    No recursive ownership rewrite, container start, arbitrary UID/GID or remote
    path selection. A crash after the intent requires explicit reconciliation.
    """
    if platform.system() != "Linux" or os.name == "nt" or os.geteuid() != 0:
        raise StorageError("linux_root_required")
    control = _control(control)
    with activation._store_lock(control):
        guard = VolumeGuard(control, observe=observe)
        guard.check()
        if _runtime_permissions(control, guard.binding) is not None:
            return guard.layout()
        if not callable(workers_stopped) or workers_stopped() is not True:
            raise StorageError("workers_not_stopped")
        guard.check()
        layout = guard.layout()
        for name in MUTABLE_LAYOUT:
            target = layout[name]
            _safe_directory(target)
            if any(target.iterdir()):
                raise StorageError("runtime_directory_not_empty")
            if any(x in os.listxattr(target) for x in
                   ("system.posix_acl_access", "system.posix_acl_default")):
                raise StorageError("runtime_directory_acl")
        record = {"schema": 1, "state": "preparing",
                  "volume_sha256": _volume_digest(guard.binding),
                  "gid": RUNTIME_GID, "mode": RUNTIME_MODE}
        activation._atomic_json(control / "PERMISSIONS.json", record)
        expected = Volume(**guard.binding["volume"])
        for name in MUTABLE_LAYOUT:
            target = layout[name]
            if observe(target) != expected:
                raise StorageError("volume_changed")
            descriptor = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                # Parent remains installer-private; workers cannot replace this root.
                if os.fstat(descriptor).st_ino != target.stat().st_ino:
                    raise StorageError("runtime_directory_changed")
                os.fchown(descriptor, 0, RUNTIME_GID)
                os.fchmod(descriptor, RUNTIME_MODE)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        for name in MUTABLE_LAYOUT:
            target = layout[name]
            _safe_directory(target, runtime_data=True)
            observed = (native_volume(target, runtime_data=True)
                        if observe is native_volume else observe(target))
            if observed != expected:
                raise StorageError("volume_changed")
        if _read_binding(control) != guard.binding:
            raise StorageError("volume_binding_changed")
        record["state"] = "ready"
        activation._atomic_json(control / "PERMISSIONS.json", record)
        guard.check()
        return layout
