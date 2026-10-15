"""Durable host lifecycle transaction; trusted adapters, never remote commands.

See HOST_LIFECYCLE.md. A completed switch remains paused until explicit resume.
This module does not itself provide a Docker daemon adapter or HA endpoint.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat

import package_activation as storage

MAX_JOURNAL = 65536
MAX_RECEIPTS = 128
PHASES = frozenset(("prepared", "pausing", "stopping", "activating", "starting",
                    "checking", "ready_paused", "rolling_back", "restored_paused",
                    "resuming", "complete"))
SERVICES = frozenset(("api", "worker"))


class LifecycleError(ValueError):
    """Stable local error code; never expose subprocess output or credentials."""


def identifier(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise LifecycleError("invalid_request_id")
    return value


def generation(value):
    if type(value) is not str or re.fullmatch(r"g-[a-f0-9]{64}", value) is None:
        raise LifecycleError("invalid_generation")
    return value


def _digest(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise LifecycleError("invalid_runtime_binding")
    return value


def binding(value):
    """Exact public identities; no paths, commands, tokens or arbitrary payloads."""
    if (type(value) is not dict or set(value) !=
            {"generation_id", "image_id", "compose_sha256", "volume_sha256"}):
        raise LifecycleError("invalid_runtime_binding")
    generation(value["generation_id"])
    image = value["image_id"]
    if type(image) is not str or not image.startswith("sha256:"):
        raise LifecycleError("invalid_runtime_binding")
    _digest(image[7:])
    _digest(value["compose_sha256"])
    _digest(value["volume_sha256"])
    return dict(value)


def _proof(value, expected, *, running):
    if (type(value) is not dict or set(value) !=
            {"binding", "containers", "running", "mounts_verified", "isolation_verified"}
            or binding(value["binding"]) != expected
            or type(value["running"]) is not bool or type(running) is not bool
            or value["running"] is not running
            or value["mounts_verified"] is not True
            or value["isolation_verified"] is not True):
        raise LifecycleError("runtime_proof_rejected")
    containers = value["containers"]
    if (type(containers) is not dict or set(containers) != SERVICES
            or any(type(v) is not str or re.fullmatch(r"[a-f0-9]{64}", v) is None
                   for v in containers.values())
            or len(set(containers.values())) != 2):
        raise LifecycleError("runtime_proof_rejected")
    return json.loads(json.dumps(value))


def _private_directory(path):
    path = Path(path)
    for p in (path, *path.parents):
        if p.is_symlink() or getattr(p, "is_junction", lambda: False)():
            raise LifecycleError("unsafe_lifecycle_state")
    storage._private_owner(path, writable=True)
    if os.name != "nt" and stat.S_IMODE(path.stat().st_mode) != 0o700:
        raise LifecycleError("private_lifecycle_directory_required")


def _read(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_size > MAX_JOURNAL
            or (os.name != "nt" and
                (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600))):
        raise LifecycleError("unsafe_lifecycle_state")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as stream:
        actual = os.fstat(stream.fileno())
        if (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
            raise LifecycleError("unsafe_lifecycle_state")
        data = stream.read(MAX_JOURNAL + 1)
    def pairs(items):
        row = {}
        for k, v in items:
            if k in row:
                raise LifecycleError("invalid_lifecycle_state")
            row[k] = v
        return row
    try:
        if len(data) > MAX_JOURNAL:
            raise ValueError()
        return json.loads(data, object_pairs_hook=pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise LifecycleError("invalid_lifecycle_state") from None


class Lifecycle:
    """One trusted installation, serialized in an independent private directory.

    driver must bind its implementation to fixed local provisioning and verify
    exact container IDs, image, mounts and isolation from fresh daemon evidence.
    No caller-supplied callbacks, paths or command strings cross this interface.

    activate/restore are trusted generation-store adapters. Restore must reconcile
    the store journal and ACTIVE to the previous generation while stopped.
    verify_volume is the provisioned VolumeGuard. A truthy value is insufficient.
    """
    def __init__(self, directory, driver, *, verify_volume, active_generation,
                 activate, restore):
        self.directory = Path(directory).absolute()
        _private_directory(self.directory)
        self.driver = driver
        self.verify_volume = verify_volume
        self.active_generation = active_generation
        self.activate = activate
        self.restore = restore
        for method in ("snapshot", "pause", "paused", "stop", "stopped",
                       "start", "health", "resume", "resumed"):
            if not callable(getattr(driver, method, None)):
                raise LifecycleError("missing_runtime_adapter")
        if not all(callable(x) for x in
                   (verify_volume, active_generation, activate, restore)):
            raise LifecycleError("missing_store_adapter")
        transactions = self.directory / "transactions"
        if not transactions.exists():
            transactions.mkdir(mode=0o700)
            storage._fsync_directory(self.directory)
        _private_directory(transactions)
        lock = transactions / "install.lock"
        if os.path.lexists(lock):
            info = lock.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
                    (os.name != "nt" and
                     (info.st_uid != os.geteuid() or info.st_mode & 0o077))):
                raise LifecycleError("unsafe_lifecycle_state")
        self.path = self.directory / "LIFECYCLE.json"
        self.receipts = self.directory / "receipts"
        if not self.receipts.exists():
            self.receipts.mkdir(mode=0o700)
            storage._fsync_directory(self.directory)
        _private_directory(self.receipts)

    def _volume(self):
        _private_directory(self.directory)
        if self.verify_volume() is not True:
            raise LifecycleError("persistent_volume_unverified")

    def _load(self, path=None):
        _private_directory(self.directory)
        row = _read(self.path if path is None else path)
        if (type(row) is not dict or set(row) !=
                {"schema", "request_id", "phase", "previous", "target",
                 "previous_containers", "result_containers", "result_binding"}
                or type(row["schema"]) is not int or row["schema"] != 1
                or type(row["phase"]) is not str or row["phase"] not in PHASES):
            raise LifecycleError("invalid_lifecycle_state")
        identifier(row["request_id"])
        binding(row["previous"])
        binding(row["target"])
        for key, expected in (("previous_containers", row["previous"]),
                              ("result_containers", row["result_binding"])):
            if row[key] is not None:
                _proof(row[key], binding(expected), running=True)
        if row["previous_containers"] is None:
            raise LifecycleError("invalid_lifecycle_state")
        if row["result_binding"] is not None:
            if binding(row["result_binding"]) not in (row["previous"], row["target"]):
                raise LifecycleError("invalid_lifecycle_state")
        if (row["result_binding"] is None) != (row["result_containers"] is None):
            raise LifecycleError("invalid_lifecycle_state")
        if row["phase"] in ("ready_paused", "restored_paused", "resuming", "complete"):
            expected = (row["target"] if row["phase"] == "ready_paused" else
                        row["previous"] if row["phase"] == "restored_paused" else
                        row["result_binding"])
            if expected is None or row["result_binding"] != expected:
                raise LifecycleError("invalid_lifecycle_state")
        return row

    def _save(self, row, phase):
        row["phase"] = phase
        storage._atomic_json(self.path, row)
        if self._load() != row:
            raise LifecycleError("lifecycle_readback_failed")

    @staticmethod
    def _public(row):
        return {"request_id": row["request_id"], "state": row["phase"],
                "generation_id": (row["result_binding"] or row["target"])["generation_id"],
                "dispatch_blocked": (False if row["phase"] == "complete" else
                                     True if row["phase"] in ("ready_paused", "restored_paused") else None),
                "requires_recovery": row["phase"] not in
                ("ready_paused", "restored_paused", "complete")}

    def status(self):
        # Atomic replace provides a coherent snapshot; status does not take the
        # mutation lock, signal workers or infer success from an absent marker.
        if not os.path.lexists(self.path):
            return {"state": "idle"}
        return self._public(self._load())

    def _paused(self, ident):
        if self.driver.paused(ident) is not True:
            raise LifecycleError("maintenance_unverified")

    def _stopped(self, proof):
        if self.driver.stopped(proof) is not True:
            raise LifecycleError("owned_containers_not_stopped")

    def _health(self, expected, ident):
        self._volume()
        self._paused(ident)
        if self.active_generation() != expected["generation_id"]:
            raise LifecycleError("active_generation_mismatch")
        evidence = self.driver.health(expected)
        if (type(evidence) is not dict or set(evidence) !=
                {"runtime", "api_tls_authenticated", "worker_healthy", "maintenance_id"}
                or evidence["api_tls_authenticated"] is not True
                or evidence["worker_healthy"] is not True
                or evidence["maintenance_id"] != ident):
            raise LifecycleError("runtime_health_rejected")
        return _proof(evidence["runtime"], expected, running=True)

    def switch(self, request_id, target):
        ident, target = identifier(request_id), binding(target)
        with storage._store_lock(self.directory):
            self._volume()
            _private_directory(self.receipts)
            receipt = self.receipts / (ident + ".json")
            if os.path.lexists(receipt):
                old = self._load(receipt)
                if old["request_id"] != ident or old["phase"] != "complete":
                    raise LifecycleError("invalid_lifecycle_receipt")
                if old["target"] != target:
                    raise LifecycleError("request_id_conflict")
                return self._public(old)
            if os.path.lexists(self.path):
                old = self._load()
                if old["request_id"] == ident:
                    if old["target"] != target:
                        raise LifecycleError("request_id_conflict")
                    if old["phase"] in ("ready_paused", "restored_paused", "complete"):
                        return self._public(old)
                    raise LifecycleError("lifecycle_recovery_required")
                if old["phase"] != "complete":
                    raise LifecycleError("lifecycle_recovery_required")
                destination = self.receipts / (old["request_id"] + ".json")
                if os.path.lexists(destination):
                    if self._load(destination) != old:
                        raise LifecycleError("invalid_lifecycle_receipt")
                else:
                    if len(list(self.receipts.iterdir())) >= MAX_RECEIPTS:
                        raise LifecycleError("lifecycle_history_capacity")
                    storage._atomic_json(destination, old)
                    if self._load(destination) != old:
                        raise LifecycleError("lifecycle_readback_failed")
                self.path.unlink()
                storage._fsync_directory(self.directory)
            previous = self.driver.snapshot()
            before = binding(previous["binding"])
            previous = _proof(previous, before, running=True)
            if before["volume_sha256"] != target["volume_sha256"]:
                raise LifecycleError("runtime_volume_mismatch")
            if self.active_generation() != before["generation_id"]:
                raise LifecycleError("active_generation_mismatch")
            row = {"schema": 1, "request_id": ident, "phase": "prepared",
                   "previous": before, "target": target, "previous_containers": previous,
                   "result_containers": None, "result_binding": None}
            self._save(row, "prepared")
            self._save(row, "pausing")
            self.driver.pause(ident)
            self._paused(ident)
            self._save(row, "stopping")
            self.driver.stop(previous)
            self._stopped(previous)
            self._volume()
            self._paused(ident)
            self._save(row, "activating")
            self.activate(target["generation_id"])
            if self.active_generation() != target["generation_id"]:
                raise LifecycleError("active_generation_mismatch")
            self._volume()
            self._paused(ident)
            self._stopped(previous)
            self._save(row, "starting")
            self.driver.start(target)
            self._save(row, "checking")
            row["result_containers"] = self._health(target, ident)
            row["result_binding"] = target
            self._save(row, "ready_paused")
            return self._public(row)

    def rollback(self, request_id):
        ident = identifier(request_id)
        with storage._store_lock(self.directory):
            self._volume()
            row = self._load()
            if row["request_id"] != ident:
                raise LifecycleError("maintenance_owned_by_other_request")
            if row["phase"] in ("resuming", "complete"):
                raise LifecycleError("resume_reconciliation_required")
            if row["phase"] == "restored_paused":
                self._health(row["previous"], ident)
                return self._public(row)
            # No automatic rollback on timeout. The adapter must prove the same
            # request's barrier and enumerate current owned containers afresh.
            self._paused(ident)
            current = self.driver.snapshot()
            current_binding = binding(current["binding"])
            if current_binding not in (row["previous"], row["target"]):
                raise LifecycleError("unexpected_runtime_binding")
            current = _proof(current, current_binding, running=current["running"])
            self._save(row, "rolling_back")
            self.driver.stop(current)
            self._stopped(current)
            self._volume()
            self._paused(ident)
            self.restore(row["previous"]["generation_id"])
            if self.active_generation() != row["previous"]["generation_id"]:
                raise LifecycleError("active_generation_mismatch")
            self._stopped(current)
            self.driver.start(row["previous"])
            row["result_containers"] = self._health(row["previous"], ident)
            row["result_binding"] = row["previous"]
            self._save(row, "restored_paused")
            return self._public(row)

    def resume(self, request_id):
        ident = identifier(request_id)
        with storage._store_lock(self.directory):
            self._volume()
            row = self._load()
            if row["request_id"] != ident:
                raise LifecycleError("maintenance_owned_by_other_request")
            if row["phase"] == "complete":
                return self._public(row)
            if row["phase"] not in ("ready_paused", "restored_paused"):
                raise LifecycleError("resume_reconciliation_required")
            proof = self._health(row["result_binding"], ident)
            if proof["containers"] != row["result_containers"]["containers"]:
                raise LifecycleError("runtime_identity_changed")
            self._save(row, "resuming")
            self.driver.resume(ident)
            if self.driver.resumed(ident) is not True:
                raise LifecycleError("resume_unconfirmed")
            self._save(row, "complete")
            return self._public(row)
