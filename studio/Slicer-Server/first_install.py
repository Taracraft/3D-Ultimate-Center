"""Durable first-install transaction outside runtime data and engine storage.

Only trusted local adapters cross this boundary. Caller input is limited to a request
identifier, a one-way principal digest and an immutable runtime binding.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat

import host_lifecycle as lifecycle
import package_activation as storage

PHASES = frozenset(("prepared", "barrier", "activating", "starting", "checking",
                    "ready_paused", "rolling_back", "rolled_back_absent",
                    "resuming", "complete"))
TERMINAL = frozenset(("rolled_back_absent", "complete"))
MAX_RECEIPTS = 128


class FirstInstallError(ValueError):
    """Stable local error code; never include paths, credentials or subprocess output."""


def _digest(value, code):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise FirstInstallError(code)
    return value


def _store_id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise FirstInstallError("invalid_store_id")
    return value


class FirstInstall:
    """Request-bound initial ACTIVE/runtime creation with explicit absent rollback."""

    def __init__(self, directory, driver, *, verify_volume, verify_store,
                 verify_exclusive_host, active_generation, activate, deactivate):
        self.directory = Path(directory).absolute()
        lifecycle._private_directory(self.directory)
        self.driver = driver
        self.verify_volume = verify_volume
        self.verify_store = verify_store
        self.verify_exclusive_host = verify_exclusive_host
        self.active_generation = active_generation
        self.activate = activate
        self.deactivate = deactivate
        for name in ("installation_state", "bootstrap_runtime", "prepare_first_install",
                     "start", "health", "snapshot", "stop", "stopped", "remove", "clear_first_install",
                     "paused", "resume", "resumed"):
            if not callable(getattr(driver, name, None)):
                raise FirstInstallError("missing_runtime_adapter")
        if not all(callable(item) for item in
                   (verify_volume, verify_store, active_generation, activate, deactivate)):
            raise FirstInstallError("missing_store_adapter")
        if not callable(verify_exclusive_host):
            raise FirstInstallError("missing_host_exclusivity_adapter")
        for name in ("transactions", "receipts"):
            path = self.directory / name
            if not path.exists():
                path.mkdir(mode=0o700)
                storage._fsync_directory(self.directory)
            lifecycle._private_directory(path)
        self.path = self.directory / "FIRST_INSTALL.json"
        self.receipts = self.directory / "receipts"

    def _save(self, row, phase):
        row["phase"] = phase
        storage._atomic_json(self.path, row)
        if self._load() != row:
            raise FirstInstallError("first_install_readback_failed")

    def _load(self, path=None):
        lifecycle._private_directory(self.directory)
        try:
            row = lifecycle._read(self.path if path is None else path)
        except lifecycle.LifecycleError as exc:
            raise FirstInstallError(str(exc)) from None
        expected = {"schema", "request_id", "principal_sha256", "store_id", "phase",
                    "target", "runtime"}
        if (type(row) is not dict or set(row) != expected
                or type(row["schema"]) is not int or row["schema"] != 1
                or type(row["phase"]) is not str or row["phase"] not in PHASES):
            raise FirstInstallError("invalid_first_install_state")
        try:
            lifecycle.identifier(row["request_id"])
            lifecycle.binding(row["target"])
        except lifecycle.LifecycleError:
            raise FirstInstallError("invalid_first_install_state") from None
        _digest(row["principal_sha256"], "invalid_first_install_state")
        _store_id(row["store_id"])
        if row["runtime"] is not None:
            try:
                lifecycle._proof(row["runtime"], row["target"], running=True)
            except lifecycle.LifecycleError:
                raise FirstInstallError("invalid_first_install_state") from None
        if row["phase"] in ("ready_paused", "resuming", "complete") and row["runtime"] is None:
            raise FirstInstallError("invalid_first_install_state")
        if row["phase"] == "rolled_back_absent" and row["runtime"] is not None:
            raise FirstInstallError("invalid_first_install_state")
        return row

    @staticmethod
    def _public(row):
        phase = row["phase"]
        return {"request_id": row["request_id"], "state": phase,
                "generation_id": row["target"]["generation_id"],
                "dispatch_blocked": True if phase == "ready_paused" else
                                    False if phase in TERMINAL else None,
                "requires_recovery": phase not in
                    ("ready_paused", "rolled_back_absent", "complete")}

    def status(self):
        if not os.path.lexists(self.path):
            return {"state": "idle"}
        return self._public(self._load())

    def _volume(self):
        lifecycle._private_directory(self.directory)
        if self.verify_volume() is not True:
            raise FirstInstallError("persistent_volume_unverified")

    def _exclusive(self):
        try:
            result = self.verify_exclusive_host()
        except FirstInstallError:
            raise
        except Exception as exc:
            raise FirstInstallError("host_exclusivity_unknown") from exc
        if result is not True:
            raise FirstInstallError("parallel_slicer_runtime_detected")

    @staticmethod
    def _observation(value, state=None):
        if (type(value) is not dict or set(value) !=
                {"state", "runtime", "installation_permitted"}
                or value["installation_permitted"] is not False
                or value["state"] not in ("empty", "running", "stopped")
                or (value["state"] == "empty") != (value["runtime"] is None)):
            raise FirstInstallError("installation_observation_rejected")
        if state is not None and value["state"] != state:
            raise FirstInstallError("installation_state_mismatch")
        return value

    def _archive_terminal(self, old):
        destination = self.receipts / (old["request_id"] + ".json")
        if os.path.lexists(destination):
            if self._load(destination) != old:
                raise FirstInstallError("invalid_first_install_receipt")
        else:
            if len(list(self.receipts.iterdir())) >= MAX_RECEIPTS:
                raise FirstInstallError("first_install_history_capacity")
            storage._atomic_json(destination, old)
            if self._load(destination) != old:
                raise FirstInstallError("first_install_readback_failed")
        self.path.unlink()
        storage._fsync_directory(self.directory)

    def install(self, request_id, principal_sha256, store_id, target):
        try:
            ident = lifecycle.identifier(request_id)
            target = lifecycle.binding(target)
        except lifecycle.LifecycleError as exc:
            raise FirstInstallError(str(exc)) from None
        principal = _digest(principal_sha256, "invalid_principal")
        store_id = _store_id(store_id)
        with storage._store_lock(self.directory):
            self._exclusive()
            self._volume()
            if self.verify_store(store_id) is not True:
                raise FirstInstallError("persistent_store_unverified")
            receipt = self.receipts / (ident + ".json")
            if os.path.lexists(receipt):
                old = self._load(receipt)
                if (old["principal_sha256"] != principal or old["store_id"] != store_id
                        or old["target"] != target):
                    raise FirstInstallError("request_id_conflict")
                return self._public(old)
            if os.path.lexists(self.path):
                old = self._load()
                if old["request_id"] == ident:
                    if (old["principal_sha256"] != principal or old["store_id"] != store_id
                            or old["target"] != target):
                        raise FirstInstallError("request_id_conflict")
                    if old["phase"] in ("ready_paused", "rolled_back_absent", "complete"):
                        return self._public(old)
                    raise FirstInstallError("first_install_recovery_required")
                if old["phase"] not in TERMINAL:
                    raise FirstInstallError("first_install_recovery_required")
                self._archive_terminal(old)
            if self.active_generation() is not None:
                raise FirstInstallError("active_generation_already_exists")
            self._observation(self.driver.installation_state(), "empty")
            row = {"schema": 1, "request_id": ident, "principal_sha256": principal,
                   "store_id": store_id, "phase": "prepared", "target": target,
                   "runtime": None}
            self._save(row, "prepared")
            barrier = self.driver.prepare_first_install(target, ident)
            if (type(barrier) is not dict or barrier !=
                    {"state": "first_install_maintenance", "request_id": ident,
                     "dispatch_blocked": True, "runtime_absent": True}):
                raise FirstInstallError("first_install_barrier_rejected")
            if self.driver.paused(ident) is not True:
                raise FirstInstallError("maintenance_unverified")
            self._save(row, "barrier")
            self._exclusive()
            self._volume()
            self._observation(self.driver.installation_state(), "empty")
            self._save(row, "activating")
            self.activate(target["generation_id"], "t-" + ident)
            if self.active_generation() != target["generation_id"]:
                raise FirstInstallError("active_generation_mismatch")
            self._save(row, "starting")
            self.driver.start(target)
            self._save(row, "checking")
            evidence = self.driver.health(target)
            if (type(evidence) is not dict or set(evidence) !=
                    {"runtime", "api_tls_authenticated", "worker_healthy", "maintenance_id"}
                    or evidence["api_tls_authenticated"] is not True
                    or evidence["worker_healthy"] is not True
                    or evidence["maintenance_id"] != ident):
                raise FirstInstallError("runtime_health_rejected")
            try:
                row["runtime"] = lifecycle._proof(evidence["runtime"], target, running=True)
            except lifecycle.LifecycleError:
                raise FirstInstallError("runtime_health_rejected") from None
            self._save(row, "ready_paused")
            return self._public(row)

    def _owned(self, row, principal):
        if row["principal_sha256"] != _digest(principal, "invalid_principal"):
            raise FirstInstallError("principal_mismatch")

    def rollback(self, request_id, principal_sha256):
        try:
            ident = lifecycle.identifier(request_id)
        except lifecycle.LifecycleError as exc:
            raise FirstInstallError(str(exc)) from None
        with storage._store_lock(self.directory):
            self._volume()
            row = self._load()
            if self.verify_store(row["store_id"]) is not True:
                raise FirstInstallError("persistent_store_unverified")
            self._owned(row, principal_sha256)
            if row["request_id"] != ident:
                raise FirstInstallError("maintenance_owned_by_other_request")
            if row["phase"] in ("resuming", "complete"):
                raise FirstInstallError("resume_reconciliation_required")
            if row["phase"] == "rolled_back_absent":
                self._observation(self.driver.installation_state(), "empty")
                if self.active_generation() is not None or self.driver.paused(ident):
                    raise FirstInstallError("absent_rollback_unverified")
                return self._public(row)
            if self.driver.paused(ident) is not True:
                raise FirstInstallError("maintenance_unverified")
            current = self.active_generation()
            if current not in (None, row["target"]["generation_id"]):
                raise FirstInstallError("unexpected_active_generation")
            candidate = self.driver.bootstrap_runtime(row["target"])
            proof = None
            if candidate is not None:
                try:
                    proof = lifecycle._proof(candidate, row["target"],
                                             running=candidate.get("running"))
                except (AttributeError, lifecycle.LifecycleError):
                    raise FirstInstallError("runtime_proof_rejected") from None
            self._save(row, "rolling_back")
            if proof is not None:
                self.driver.stop(proof)
                if self.driver.stopped(proof) is not True:
                    raise FirstInstallError("owned_containers_not_stopped")
                self.driver.remove(proof)
            if self.driver.bootstrap_runtime(row["target"]) is not None:
                raise FirstInstallError("container_removal_unverified")
            self.deactivate(row["target"]["generation_id"], "t-" + ident)
            if self.active_generation() is not None:
                raise FirstInstallError("active_absence_unverified")
            self.driver.clear_first_install(ident, row["target"]["generation_id"])
            if self.driver.paused(ident) is True:
                raise FirstInstallError("maintenance_clear_unverified")
            self._observation(self.driver.installation_state(), "empty")
            row["runtime"] = None
            self._save(row, "rolled_back_absent")
            return self._public(row)

    def resume(self, request_id, principal_sha256):
        try:
            ident = lifecycle.identifier(request_id)
        except lifecycle.LifecycleError as exc:
            raise FirstInstallError(str(exc)) from None
        with storage._store_lock(self.directory):
            self._volume()
            row = self._load()
            if self.verify_store(row["store_id"]) is not True:
                raise FirstInstallError("persistent_store_unverified")
            self._owned(row, principal_sha256)
            if row["request_id"] != ident:
                raise FirstInstallError("maintenance_owned_by_other_request")
            if row["phase"] == "complete":
                return self._public(row)
            if row["phase"] != "ready_paused":
                raise FirstInstallError("resume_reconciliation_required")
            evidence = self.driver.health(row["target"])
            try:
                proof = lifecycle._proof(evidence["runtime"], row["target"], running=True)
            except (KeyError, TypeError, lifecycle.LifecycleError):
                raise FirstInstallError("runtime_health_rejected") from None
            if (evidence.get("maintenance_id") != ident
                    or evidence.get("api_tls_authenticated") is not True
                    or evidence.get("worker_healthy") is not True
                    or proof["containers"] != row["runtime"]["containers"]):
                raise FirstInstallError("runtime_health_rejected")
            self._save(row, "resuming")
            self.driver.resume(ident)
            if self.driver.resumed(ident) is not True:
                raise FirstInstallError("resume_unconfirmed")
            self._save(row, "complete")
            return self._public(row)
