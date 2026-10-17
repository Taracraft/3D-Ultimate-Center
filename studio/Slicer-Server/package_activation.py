"""Persistent engine-store transactions; never execute an engine.

The installer owns this module. API and worker containers receive only the
selected immutable generation as a read-only mount. See PACKAGE_ACTIVATION.md.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat

from engine_catalog import ENTRYPOINTS, Release, _release, release_document

STORE_SCHEMA = 1
TRANSACTION_STATES = frozenset(("preparing", "ready", "activating", "restoring",
                                "removing_first_active"))
TERMINAL_STATES = frozenset(("activated", "failed", "aborted", "adopted", "rolled_back", "restored",
                             "first_active_absent"))
SPACE_MARGIN = 64 * 1024**2
COPY_CHUNK = 65536


class ActivationError(ValueError):
    """Stable error code only; do not expose host paths or manifest values."""


def _linked(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _safe_path(path: Path, *, must_exist: bool = True) -> Path:
    path = Path(path).absolute()
    current = path
    while True:
        if current.exists() and _linked(current):
            raise ActivationError("linked_store_path")
        if current.parent == current:
            break
        current = current.parent
    if must_exist and not path.is_dir():
        raise ActivationError("store_unavailable")
    return path


def _private_owner(path: Path, *, writable: bool) -> os.stat_result:
    try:
        info = path.stat()
    except OSError:
        raise ActivationError("store_unavailable") from None
    if not stat.S_ISDIR(info.st_mode):
        raise ActivationError("store_unavailable")
    if os.name != "nt":
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ActivationError("store_permissions")
        if writable and not os.access(path, os.W_OK | os.X_OK):
            raise ActivationError("store_permissions")
    elif writable and not os.access(path, os.W_OK):
        raise ActivationError("store_permissions")
    return info


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json(path: Path, value: dict) -> None:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")
    temporary = path.parent / ("." + path.name + "." + secrets.token_hex(8) + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            path.chmod(0o600)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path, *, maximum: int = 4 * 1024**2) -> dict:
    try:
        if _linked(path):
            raise ActivationError("linked_store_path")
        with path.open("rb") as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise ActivationError("state_too_large")
        value = json.loads(data)
    except ActivationError:
        raise
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise ActivationError("invalid_state") from None
    if type(value) is not dict:
        raise ActivationError("invalid_state")
    return value


def _store_marker(root: Path) -> dict:
    value = _read_json(root / "STORE.json", maximum=4096)
    if (set(value) != {"schema", "store_id", "device"}
            or value["schema"] != STORE_SCHEMA
            or type(value["store_id"]) is not str
            or re.fullmatch(r"[a-f0-9]{32}", value["store_id"]) is None
            or type(value["device"]) is not int):
        raise ActivationError("invalid_store_identity")
    return value


def initialize_store(root: Path) -> dict:
    """Create a new empty store and return identity data the caller must retain."""
    root = _safe_path(root, must_exist=False)
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise ActivationError("store_not_empty")
    else:
        parent = _safe_path(root.parent)
        _private_owner(parent, writable=True)
        root.mkdir(mode=0o700)
    _private_owner(root, writable=True)
    if os.name != "nt":
        root.chmod(0o700)
    for name, mode in (("generations", 0o755), ("transactions", 0o700),
                       ("reservations", 0o700)):
        (root / name).mkdir(mode=mode)
    info = root.stat()
    marker = {"schema": STORE_SCHEMA, "store_id": secrets.token_hex(16),
              "device": int(info.st_dev)}
    _atomic_json(root / "STORE.json", marker)
    _fsync_directory(root)
    return marker


def verify_store(root: Path, store_id: str) -> dict:
    """Verify the persistent identity, ownership, modes and same-device layout."""
    root = _safe_path(root)
    info = _private_owner(root, writable=True)
    marker = _store_marker(root)
    if not secrets.compare_digest(marker["store_id"], str(store_id)):
        raise ActivationError("wrong_store_identity")
    if marker["device"] != int(info.st_dev):
        raise ActivationError("wrong_store_device")
    for name in ("generations", "transactions", "reservations"):
        child = root / name
        if _linked(child) or not child.is_dir() or child.stat().st_dev != info.st_dev:
            raise ActivationError("wrong_store_device")
        _private_owner(child, writable=True)
    return marker


@contextmanager
def _store_lock(root: Path):
    path = root / "transactions/install.lock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    stream = os.fdopen(descriptor, "r+b", buffering=0)
    locked = False
    try:
        if os.path.getsize(path) == 0:
            stream.write(b"0")
            stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except (OSError, BlockingIOError):
            raise ActivationError("installer_busy") from None
        yield
    finally:
        try:
            if locked and os.name == "nt":
                import msvcrt
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            elif locked:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


def _release_from_receipt(value: object) -> Release:
    if type(value) is not dict or "system" in value:
        raise ActivationError("invalid_candidate")
    try:
        # Staging serializes dataclasses including the optional archive_path=None.
        # Catalog JSON omits that field to mean source path equals target path.
        normalized = json.loads(json.dumps(value))
        for artifact in normalized.get("artifacts", []):
            for item in artifact.get("files", []):
                if item.get("archive_path") is None:
                    item.pop("archive_path", None)
        return _release({**normalized, "system": "linux"})
    except (TypeError, ValueError):
        raise ActivationError("invalid_candidate") from None


def _manifest(release: Release) -> dict[str, tuple[str, int, bool]]:
    return {spec.path: (spec.sha256, spec.size_bytes, spec.executable)
            for artifact in release.artifacts for spec in artifact.files}


def _regular_file(path: Path) -> os.stat_result:
    if _linked(path):
        raise ActivationError("linked_generation_path")
    try:
        info = path.stat()
    except OSError:
        raise ActivationError("manifest_mismatch") from None
    if not stat.S_ISREG(info.st_mode):
        raise ActivationError("manifest_mismatch")
    return info


def _hash_file(path: Path, expected_size: int) -> str:
    info = _regular_file(path)
    if info.st_size != expected_size:
        raise ActivationError("manifest_mismatch")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(COPY_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_tree(root: Path, release: Release) -> None:
    expected = _manifest(release)
    actual = set()
    if _linked(root) or not root.is_dir():
        raise ActivationError("manifest_mismatch")
    if os.name != "nt":
        info = root.stat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ActivationError("manifest_mode_mismatch")
    for path in root.rglob("*"):
        if _linked(path):
            raise ActivationError("linked_generation_path")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        elif path.is_dir():
            if os.name != "nt":
                info = path.stat()
                if info.st_uid != os.geteuid() or info.st_mode & 0o022:
                    raise ActivationError("manifest_mode_mismatch")
        else:
            raise ActivationError("manifest_mismatch")
    if actual != set(expected):
        raise ActivationError("manifest_mismatch")
    for relative, (digest, size, executable) in expected.items():
        path = root / relative
        if _hash_file(path, size) != digest:
            raise ActivationError("manifest_mismatch")
        if os.name != "nt":
            info = path.stat()
            if (info.st_uid != os.geteuid()
                    or stat.S_IMODE(info.st_mode) != (0o755 if executable else 0o644)):
                raise ActivationError("manifest_mode_mismatch")


def _candidate(path: Path) -> Release:
    path = _safe_path(path)
    receipt = _read_json(path / "READY.json")
    if (set(receipt) != {"schema", "state", "release", "engine_executed", "activated"}
            or receipt["schema"] != 1 or receipt["state"] != "prepared"
            or receipt["engine_executed"] is not False or receipt["activated"] is not False):
        raise ActivationError("invalid_candidate")
    release = _release_from_receipt(receipt["release"])
    if set(p.name for p in path.iterdir()) != {"payload", "READY.json"}:
        raise ActivationError("invalid_candidate")
    payload = path / "payload"
    if set(p.name for p in payload.iterdir()) != {release.engine}:
        raise ActivationError("invalid_candidate")
    _validate_tree(payload / release.engine, release)
    return release


def _generation_document(releases: dict[str, Release]) -> dict:
    rows = []
    for engine in sorted(releases):
        rows.append(release_document(releases[engine]))
    body = {"schema": 1, "releases": rows}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")
    normalized = json.loads(canonical)
    normalized["generation_id"] = "g-" + hashlib.sha256(canonical).hexdigest()
    return normalized


def _generation_releases(document: dict) -> dict[str, Release]:
    if (set(document) != {"schema", "generation_id", "releases"}
            or document["schema"] != 1 or type(document["releases"]) is not list
            or re.fullmatch(r"g-[a-f0-9]{64}", str(document["generation_id"])) is None):
        raise ActivationError("invalid_generation")
    releases = {}
    for row in document["releases"]:
        release = _release_from_receipt(row)
        if release.engine in releases:
            raise ActivationError("invalid_generation")
        releases[release.engine] = release
    expected = _generation_document(releases)
    if expected != document:
        raise ActivationError("invalid_generation")
    return releases


def validate_generation(root: Path, generation_id: str) -> dict:
    if re.fullmatch(r"g-[a-f0-9]{64}", str(generation_id)) is None:
        raise ActivationError("invalid_generation")
    generation = root / "generations" / generation_id
    if _linked(generation) or not generation.is_dir():
        raise ActivationError("invalid_generation")
    document = _read_json(generation / "GENERATION.json")
    releases = _generation_releases(document)
    names = {p.name for p in generation.iterdir()}
    if names != set(releases) | {"GENERATION.json"}:
        raise ActivationError("invalid_generation")
    for engine, release in releases.items():
        _validate_tree(generation / engine, release)
    return document


def _copy_tree(source: Path, target: Path, release: Release) -> None:
    target.mkdir(mode=0o755)
    for relative, (_, size, executable) in _manifest(release).items():
        src = source / relative
        dst = target / relative
        dst.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
        digest = hashlib.sha256()
        remaining = size
        with src.open("rb") as incoming, dst.open("xb") as outgoing:
            while remaining:
                chunk = incoming.read(min(COPY_CHUNK, remaining))
                if not chunk or len(chunk) > remaining:
                    raise ActivationError("manifest_mismatch")
                outgoing.write(chunk)
                digest.update(chunk)
                remaining -= len(chunk)
            if incoming.read(1):
                raise ActivationError("manifest_mismatch")
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if os.name != "nt":
            dst.chmod(0o755 if executable else 0o644)
        if digest.hexdigest() != _manifest(release)[relative][0]:
            raise ActivationError("manifest_mismatch")


def _allocate(stream, size: int) -> None:
    if hasattr(os, "posix_fallocate"):
        os.posix_fallocate(stream.fileno(), 0, size)
        return
    # The production target is Linux. Keep synthetic Windows checks bounded;
    # never pretend a sparse truncate is a durable reservation.
    if size > 16 * 1024**2:
        raise ActivationError("space_reservation_unsupported")
    remaining = size
    zero = bytes(min(COPY_CHUNK, max(1, size)))
    while remaining:
        chunk = zero[:min(len(zero), remaining)]
        stream.write(chunk)
        remaining -= len(chunk)


@contextmanager
def _reservation(root: Path, transaction_id: str, required: int):
    if type(required) is not int or required <= 0:
        raise ActivationError("invalid_space_request")
    path = root / "reservations" / (transaction_id + ".space")
    try:
        if shutil.disk_usage(root).free < required:
            raise ActivationError("insufficient_space")
        with path.open("xb") as stream:
            _allocate(stream, required)
            stream.flush()
            os.fsync(stream.fileno())
    except ActivationError:
        raise
    except OSError:
        raise ActivationError("space_reservation_failed") from None
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def _transaction_path(root: Path, transaction_id: str) -> Path:
    if re.fullmatch(r"t-[a-f0-9]{32}", str(transaction_id)) is None:
        raise ActivationError("invalid_transaction")
    return root / "transactions" / (transaction_id + ".json")


def _active_transactions(root: Path) -> list[dict]:
    result = []
    for path in sorted((root / "transactions").glob("t-*.json")):
        value = _read_json(path)
        if value.get("state") in TRANSACTION_STATES:
            result.append(value)
    return result


def _active(root: Path) -> str | None:
    path = root / "ACTIVE.json"
    if not path.exists():
        return None
    value = _read_json(path, maximum=4096)
    if set(value) != {"schema", "generation_id"} or value["schema"] != 1:
        raise ActivationError("invalid_active_pointer")
    validate_generation(root, value["generation_id"])
    return value["generation_id"]


def activate_generation(root: Path, store_id: str, candidates: dict,
                        workers_stopped, *, cancelled=None, transaction_id=None,
                        expected_generation=None) -> dict:
    """Copy, revalidate and atomically select one complete three-engine generation."""
    verify_store(root, store_id)
    if type(candidates) is not dict or set(candidates) != set(ENTRYPOINTS):
        raise ActivationError("incomplete_generation")
    root = Path(root).absolute()
    with _store_lock(root):
        verify_store(root, store_id)
        if _active_transactions(root):
            raise ActivationError("orphaned_transaction")
        releases = {engine: _candidate(Path(candidates[engine])) for engine in candidates}
        if any(release.engine != engine for engine, release in releases.items()):
            raise ActivationError("candidate_engine_mismatch")
        document = _generation_document(releases)
        generation_id = document["generation_id"]
        if expected_generation is not None and generation_id != expected_generation:
            raise ActivationError("candidate_generation_changed")
        transaction_id = transaction_id or ("t-" + secrets.token_hex(16))
        transaction_path = _transaction_path(root, transaction_id)
        if transaction_path.exists():
            raise ActivationError("transaction_already_exists")
        previous = _active(root)
        state = {"schema": 1, "transaction_id": transaction_id, "state": "preparing",
                 "generation_id": generation_id, "previous_generation_id": previous}
        _atomic_json(transaction_path, state)
        temporary = root / "generations" / ("." + transaction_id)
        switched = False
        required = sum(r.installed_bytes for r in releases.values()) + SPACE_MARGIN
        try:
            if cancelled is not None and cancelled():
                raise ActivationError("cancelled")
            with _reservation(root, transaction_id, required):
                if temporary.exists():
                    raise ActivationError("generation_collision")
                temporary.mkdir(mode=0o755)
                for engine in sorted(releases):
                    _copy_tree(Path(candidates[engine]) / "payload" / engine,
                               temporary / engine, releases[engine])
                _atomic_json(temporary / "GENERATION.json", document)
                target = root / "generations" / generation_id
                if target.exists():
                    validate_generation(root, generation_id)
                    shutil.rmtree(temporary)
                else:
                    os.replace(temporary, target)
                    _fsync_directory(target.parent)
                validate_generation(root, generation_id)
                state["state"] = "ready"
                _atomic_json(transaction_path, state)
                if cancelled is not None and cancelled():
                    raise ActivationError("cancelled")
                if not callable(workers_stopped) or workers_stopped() is not True:
                    raise ActivationError("workers_not_stopped")
                # Recheck after the stop acknowledgement and immediately before
                # the single pointer switch. No individual engine is switched.
                validate_generation(root, generation_id)
                state["state"] = "activating"
                _atomic_json(transaction_path, state)
                _atomic_json(root / "ACTIVE.json",
                             {"schema": 1, "generation_id": generation_id})
                switched = True
                state["state"] = "activated"
                _atomic_json(transaction_path, state)
            return {"transaction_id": transaction_id, "generation_id": generation_id,
                    "previous_generation_id": previous, "activated": True}
        except BaseException as exc:
            temporary.exists() and shutil.rmtree(temporary)
            if not switched:
                state["state"] = "failed"
                state["error"] = str(exc) if isinstance(exc, ActivationError) else "activation_failed"
                _atomic_json(transaction_path, state)
            if isinstance(exc, ActivationError):
                raise
            raise ActivationError("activation_failed") from None


def recover_transaction(root: Path, store_id: str, transaction_id: str,
                        action: str, workers_stopped=None) -> dict:
    """Resolve one retained non-terminal transaction without deleting generations."""
    verify_store(root, store_id)
    root = Path(root).absolute()
    with _store_lock(root):
        verify_store(root, store_id)
        path = _transaction_path(root, transaction_id)
        state = _read_json(path)
        if state.get("state") not in TRANSACTION_STATES:
            raise ActivationError("transaction_not_recoverable")
        if action == "abort" and state["state"] in {"preparing", "ready"}:
            state["state"] = "aborted"
        elif action in {"adopt", "rollback"} and state["state"] == "activating":
            if not callable(workers_stopped) or workers_stopped() is not True:
                raise ActivationError("workers_not_stopped")
            target = (state.get("generation_id") if action == "adopt"
                      else state.get("previous_generation_id"))
            if target is None:
                raise ActivationError("rollback_unavailable")
            validate_generation(root, target)
            _atomic_json(root / "ACTIVE.json", {"schema": 1, "generation_id": target})
            state["state"] = "adopted" if action == "adopt" else "rolled_back"
        else:
            raise ActivationError("invalid_recovery_action")
        _atomic_json(path, state)
        return {"transaction_id": transaction_id, "state": state["state"],
                "generation_id": _active(root)}


def restore_committed_generation(root: Path, store_id: str, transaction_id: str,
                                 expected_generation: str, previous_generation: str,
                                 workers_stopped) -> dict:
    """Request-bound, restartable store rollback after a runtime failure.

    The lifecycle supplies both generations from its durable prior snapshot.
    No generation is deleted. A restoring intent blocks subsequent activation.
    """
    root = Path(root).absolute()
    verify_store(root, store_id)
    with _store_lock(root):
        verify_store(root, store_id)
        path = _transaction_path(root, transaction_id)
        validate_generation(root, previous_generation)
        if re.fullmatch(r"g-[a-f0-9]{64}", str(expected_generation)) is None:
            raise ActivationError("invalid_generation")
        state = _read_json(path) if path.exists() else {
            "schema": 1, "transaction_id": transaction_id, "state": "not_started",
            "generation_id": expected_generation,
            "previous_generation_id": previous_generation}
        if (state.get("schema") != 1 or state.get("transaction_id") != transaction_id
                or state.get("generation_id") != expected_generation
                or state.get("previous_generation_id") != previous_generation
                or state.get("state") not in
                {"not_started", "preparing", "ready", "failed", "activating",
                 "activated", "restoring", "restored"}):
            raise ActivationError("restore_binding_mismatch")
        if any(row.get("transaction_id") != transaction_id
               for row in _active_transactions(root)):
            raise ActivationError("orphaned_transaction")
        current = _active(root)
        if current not in (expected_generation, previous_generation):
            raise ActivationError("restore_active_mismatch")
        if state["state"] in {"not_started", "preparing", "ready", "restored"}:
            if current != previous_generation:
                raise ActivationError("restore_active_mismatch")
        if not callable(workers_stopped) or workers_stopped() is not True:
            raise ActivationError("workers_not_stopped")
        verify_store(root, store_id)
        validate_generation(root, previous_generation)
        if _active(root) != current:
            raise ActivationError("restore_active_mismatch")
        if state["state"] == "restored":
            return {"transaction_id": transaction_id, "state": "restored",
                    "generation_id": previous_generation}
        state["state"] = "restoring"
        _atomic_json(path, state)
        if _read_json(path) != state:
            raise ActivationError("restore_readback_failed")
        _atomic_json(root / "ACTIVE.json",
                     {"schema": 1, "generation_id": previous_generation})
        if _active(root) != previous_generation:
            raise ActivationError("restore_readback_failed")
        state["state"] = "restored"
        _atomic_json(path, state)
        if _read_json(path) != state:
            raise ActivationError("restore_readback_failed")
        return {"transaction_id": transaction_id, "state": "restored",
                "generation_id": previous_generation}



def restore_first_install_absence(root: Path, store_id: str, transaction_id: str,
                                  expected_generation: str, workers_stopped) -> dict:
    """Remove only the first ACTIVE pointer; retain generation, data and journal.

    The activation transaction must prove that no predecessor existed. The
    operation is restartable across a lost unlink or final journal receipt.
    """
    root = Path(root).absolute()
    verify_store(root, store_id)
    with _store_lock(root):
        verify_store(root, store_id)
        path = _transaction_path(root, transaction_id)
        try:
            state = _read_json(path)
        except ActivationError:
            raise ActivationError("first_install_restore_binding_mismatch") from None
        if (state.get("schema") != 1 or state.get("transaction_id") != transaction_id
                or state.get("generation_id") != expected_generation
                or state.get("previous_generation_id") is not None
                or state.get("state") not in
                {"activated", "removing_first_active", "first_active_absent"}):
            raise ActivationError("first_install_restore_binding_mismatch")
        if any(row.get("transaction_id") != transaction_id
               for row in _active_transactions(root)):
            raise ActivationError("orphaned_transaction")
        current = _active(root)
        if current not in (expected_generation, None):
            raise ActivationError("restore_active_mismatch")
        if state["state"] == "first_active_absent":
            if current is not None:
                raise ActivationError("restore_active_mismatch")
            return {"transaction_id": transaction_id, "state": "first_active_absent",
                    "generation_id": None}
        if not callable(workers_stopped) or workers_stopped() is not True:
            raise ActivationError("workers_not_stopped")
        validate_generation(root, expected_generation)
        if _active(root) != current:
            raise ActivationError("restore_active_mismatch")
        if state["state"] == "activated":
            state["state"] = "removing_first_active"
            _atomic_json(path, state)
            if _read_json(path) != state:
                raise ActivationError("restore_readback_failed")
        active_path = root / "ACTIVE.json"
        if os.path.lexists(active_path):
            if _active(root) != expected_generation:
                raise ActivationError("restore_active_mismatch")
            active_path.unlink()
            _fsync_directory(root)
        if _active(root) is not None:
            raise ActivationError("restore_readback_failed")
        state["state"] = "first_active_absent"
        _atomic_json(path, state)
        if _read_json(path) != state:
            raise ActivationError("restore_readback_failed")
        return {"transaction_id": transaction_id, "state": "first_active_absent",
                "generation_id": None}

def active_generation(root: Path, store_id: str) -> dict | None:
    verify_store(root, store_id)
    generation_id = _active(Path(root).absolute())
    return None if generation_id is None else validate_generation(Path(root), generation_id)
