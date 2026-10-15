"""Authenticated, fixed-operation installer core; see RESTRICTED_INSTALLER.md.

No HTTP listener, Docker socket, shell, engine or service is started here.
Host adapters and credentials are trusted local provisioning, never request data.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import stat

import engine_catalog as catalog
import package_activation as activation
import package_staging as staging

MAX_REQUEST_BYTES = 8192
MAX_RECORDS = 128
SCOPES = frozenset(("inspect", "install", "recover"))
READ_FIELDS = {"preflight": set(), "status": {"target"}}
WRITE_FIELDS = {
    "initialize": set(), "stage": set(), "retry": {"target"},
    "activate": {"target"}, "recover": {"target", "action"},
}
PUBLIC_FIELDS = ("request_id", "operation", "state", "error", "generation_id",
                 "transaction_id", "previous_generation_id", "dispatch_blocked", "requires_recovery")
MARGIN = 64 * 1024**2


class InstallerError(ValueError):
    """Only stable public codes."""


@dataclass(frozen=True, repr=False)
class Credential:
    principal: str
    token_sha256: bytes
    scopes: frozenset[str]


@dataclass(frozen=True)
class HostPolicy:
    system: str
    architecture: str
    mode: str
    installer_available: bool
    runtime_available: bool
    store: Path
    control: Path


def _id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise InstallerError("invalid_request_id")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InstallerError("invalid_request")
        result[key] = value
    return result


def _json(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("ascii")


def _private_directory(path):
    activation._safe_path(path)
    activation._private_owner(path, writable=True)


def _state_file(path):
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise InstallerError("unsafe_control_state")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise InstallerError("unsafe_control_state")
    if os.name != "nt" and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
        raise InstallerError("unsafe_control_state")
    return activation._read_json(path, maximum=65536)


def _credentials_snapshot(value, *, allow_empty=False):
    # A provider must return one immutable, bounded snapshot, never a generator.
    if type(value) is not tuple or len(value) > 128 or (not value and not allow_empty):
        raise InstallerError("invalid_credentials")
    if any(
        type(c) is not Credential or type(c.principal) is not str
        or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", c.principal) is None
        or type(c.token_sha256) is not bytes or len(c.token_sha256) != 32
        or type(c.scopes) is not frozenset or not c.scopes or not c.scopes <= SCOPES
        for c in value
    ):
        raise InstallerError("invalid_credentials")
    if (len({c.token_sha256 for c in value}) != len(value)
            or len({c.principal for c in value}) != len(value)):
        raise InstallerError("invalid_credentials")
    return value


class Installer:
    """Backend command boundary for a separately secured transport.

    verify_volume must independently prove the configured persistent volume,
    including before first initialization. workers_stopped must actually stop
    and confirm this installation's workers; a request cannot provide it.
    """

    def __init__(self, policy, credentials, catalog_bytes, *, verify_volume,
                 workers_stopped, credential_provider=None, runtime=None):
        self.policy = policy
        self.control = Path(policy.control).absolute()
        self.store = Path(policy.store).absolute()
        if (self.control == self.store or self.control in self.store.parents
                or self.store in self.control.parents):
            raise InstallerError("control_store_overlap")
        _private_directory(self.control)
        self.credentials = tuple(credentials)
        self.credential_provider = credential_provider
        if credential_provider is None:
            _credentials_snapshot(self.credentials)
        elif not callable(credential_provider) or self.credentials:
            raise InstallerError("invalid_credentials")
        else:
            self._current_credentials()
        self.catalog = catalog.load_catalog_bytes(catalog_bytes)
        self.catalog_sha256 = hashlib.sha256(catalog_bytes).hexdigest()
        if not callable(verify_volume) or not callable(workers_stopped):
            raise InstallerError("missing_host_adapter")
        self.verify_volume = verify_volume
        self.workers_stopped = workers_stopped
        self.runtime = runtime
        if runtime is not None:
            runtime.validate_installer(self.store, self.control)
        for name in ("records", "transactions", "cancel"):
            path = self.control / name
            if not path.exists():
                path.mkdir(mode=0o700)
            _private_directory(path)
        lock = self.control / "transactions/install.lock"
        if lock.exists() and (lock.is_symlink() or not lock.is_file()):
            raise InstallerError("unsafe_control_state")

    def _current_credentials(self):
        if self.credential_provider is None:
            return self.credentials
        try:
            return _credentials_snapshot(self.credential_provider(), allow_empty=True)
        except Exception:
            # Never cache or fall back to a previously accepted snapshot.
            raise InstallerError("credentials_unavailable") from None

    def _authenticate(self, header, secure_channel):
        # secure_channel comes from the transport's verified connection context,
        # never X-Forwarded-* or a JSON field supplied by the caller.
        if secure_channel is not True:
            raise InstallerError("secure_transport_required")
        if (type(header) is not str or len(header) > 160
                or re.fullmatch(r"Bearer [A-Za-z0-9_-]{43,128}", header) is None):
            raise InstallerError("authentication_failed")
        digest = hashlib.sha256(header[7:].encode("ascii")).digest()
        matched = None
        for credential in self._current_credentials():
            if secrets.compare_digest(digest, credential.token_sha256):
                matched = credential
        if matched is None:
            raise InstallerError("authentication_failed")
        return matched

    def _parse(self, body):
        if type(body) is not bytes or len(body) > MAX_REQUEST_BYTES:
            raise InstallerError("request_too_large")
        try:
            request = json.loads(body, object_pairs_hook=_pairs)
        except (ValueError, UnicodeError, RecursionError):
            raise InstallerError("invalid_request") from None
        if type(request) is not dict:
            raise InstallerError("invalid_request")
        operation = request.get("operation")
        if type(operation) is not str:
            raise InstallerError("invalid_request")
        fields = READ_FIELDS.get(operation, WRITE_FIELDS.get(operation))
        if operation in ("cancel", "rollback", "resume"):
            fields = {"target"}
        if fields is None:
            raise InstallerError("unknown_operation")
        required = {"protocol", "operation"} | fields
        if operation in WRITE_FIELDS:
            required.add("request_id")
        if (set(request) != required or type(request["protocol"]) is not int
                or request["protocol"] != 1):
            raise InstallerError("invalid_request")
        for key in ("request_id", "target"):
            if key in request:
                _id(request[key])
        if operation == "recover" and request["action"] not in ("abort", "adopt", "rollback"):
            raise InstallerError("invalid_request")
        return request

    def dispatch(self, authorization, body, *, secure_channel=False):
        """Return sanitized data; never log authorization or raw input/exceptions."""
        try:
            credential = self._authenticate(authorization, secure_channel)
            request = self._parse(body)
            operation = request["operation"]
            scope = ("inspect" if operation in READ_FIELDS else
                     "recover" if operation in ("recover", "rollback", "resume") else "install")
            if scope not in credential.scopes:
                raise InstallerError("forbidden")
            _private_directory(self.control)
            if operation == "preflight":
                result = self._preflight()
            elif operation == "status":
                result = self._public(self._record(request["target"], credential))
            elif operation in ("rollback", "resume"):
                result = self._runtime_action(operation, request["target"], credential)
            elif operation == "cancel":
                record = self._record(request["target"], credential)
                if record["operation"] not in ("stage", "retry") or record["state"] != "running":
                    raise InstallerError("not_cancellable")
                activation._atomic_json(self.control / "cancel" / (request["target"] + ".json"),
                                        {"cancelled": True})
                result = {"request_id": request["target"], "state": "cancel_requested"}
            else:
                result = self._mutate(request, credential)
            return {"ok": True, **result}
        except InstallerError as exc:
            return {"ok": False, "error": str(exc)}
        except activation.ActivationError:
            return {"ok": False, "error": "storage_or_activation_rejected"}
        except (catalog.CatalogError, staging.StagingError):
            return {"ok": False, "error": "package_rejected"}
        except Exception:
            return {"ok": False, "error": "installer_failed"}


    def _runtime_action(self, operation, ident, credential):
        if self.runtime is None:
            raise InstallerError("runtime_adapter_required")
        self._require_host("recover")
        with activation._store_lock(self.control):
            row = self._record(ident, credential)
            if row.get("operation") != "activate" or row.get("runtime_managed") is not True:
                raise InstallerError("not_runtime_managed")
            if row["state"] not in (
                    "running", "ready_paused", "restored_paused",
                    "rolled_back_absent", "complete"):
                raise InstallerError("host_reconciliation_required")
            # Lifecycle persists intent and serializes the exact original request.
            # A lost reply leaves its journal authoritative; never infer resume.
            callback = self.runtime.rollback if operation == "rollback" else self.runtime.resume
            principal_sha256 = hashlib.sha256(credential.principal.encode("utf-8")).hexdigest()
            result = callback(ident, self._binding(), principal_sha256)
            if result.get("request_id") != ident:
                raise InstallerError("request_id_conflict")
            row.update(result)
            self._save(row)
            return self._public(row)

    def _preflight(self):
        p = self.policy
        reasons = []
        if p.system != "linux" or p.architecture != "amd64":
            reasons.append("unsupported_platform")
        if p.mode not in ("managed_docker", "supervisor_app"):
            reasons.append("unsupported_host")
        if p.installer_available is not True:
            reasons.append("installer_pairing_required")
        if p.runtime_available is not True:
            reasons.append("runtime_adapter_required")
        if self.verify_volume() is not True:
            reasons.append("persistent_volume_unverified")
        if self.catalog.pending:
            reasons.append("engine_releases_pending")
        return {"protocol": 1, "state": "blocked" if reasons else "available",
                "reasons": reasons, "host_mode": p.mode if p.mode in
                ("managed_docker", "supervisor_app") else "unsupported",
                "engines": sorted(catalog.ENTRYPOINTS), "container_deploy_ready": False}

    def _require_host(self, operation):
        result = self._preflight()
        reasons = result["reasons"]
        if operation in ("initialize", "recover"):
            reasons = [r for r in reasons if r != "engine_releases_pending"]
        if reasons:
            raise InstallerError(reasons[0])
        activation._safe_path(self.store.parent)
        activation._private_owner(self.store.parent, writable=True)

    def _record(self, ident, credential):
        path = self.control / "records" / (_id(ident) + ".json")
        if not path.exists():
            raise InstallerError("unknown_request")
        row = _state_file(path)
        if row.get("principal") != credential.principal:
            raise InstallerError("forbidden")
        return row

    @staticmethod
    def _public(row):
        return {key: row[key] for key in PUBLIC_FIELDS if key in row}

    def _save(self, row):
        activation._atomic_json(self.control / "records" / (row["request_id"] + ".json"), row)

    def _binding(self):
        if not (self.control / "BINDING.json").exists():
            raise InstallerError("storage_not_initialized")
        binding = _state_file(self.control / "BINDING.json")
        if (set(binding) != {"store_id", "store_path"}
                or binding["store_path"] != str(self.store)):
            raise InstallerError("binding_mismatch")
        activation.verify_store(self.store, binding["store_id"])
        return binding["store_id"]

    def _mutate(self, request, credential):
        self._require_host(request["operation"])
        with activation._store_lock(self.control):
            ident = request["request_id"]
            fingerprint = hashlib.sha256(_json(request)).hexdigest()
            path = self.control / "records" / (ident + ".json")
            if path.exists():
                old = self._record(ident, credential)
                if old["fingerprint"] != fingerprint:
                    raise InstallerError("request_id_conflict")
                if old["state"] == "running":
                    raise InstallerError("recovery_required")
                return self._public(old)
            existing = list((self.control / "records").glob("*.json"))
            if len(existing) >= MAX_RECORDS:
                raise InstallerError("history_capacity")
            running = [_state_file(p) for p in existing if _state_file(p).get("state")
                       in ("running", "ready_paused", "restored_paused")]
            if running and (request["operation"] != "recover" or len(running) != 1
                            or running[0]["request_id"] != request["target"]):
                raise InstallerError("recovery_required")
            if request["operation"] == "recover":
                target = self._record(request["target"], credential)
                if target["state"] != "running":
                    raise InstallerError("not_recoverable")
            row = {"request_id": ident, "operation": request["operation"],
                   "principal": credential.principal, "fingerprint": fingerprint,
                   "catalog_sha256": self.catalog_sha256, "state": "running"}
            self._save(row)
            try:
                self._execute(request, credential, row)
            except Exception:
                # A crash/uncertain activation remains running until explicit recovery.
                # Stage failures are safe to retry, but never delete retained candidates.
                if row.get("phase") not in ("initializing_store", "activating"):
                    row["state"] = "cancelled" if self._cancelled(ident) else "failed"
                    row["error"] = "operation_failed"
                    self._save(row)
                raise
            self._save(row)
            return self._public(row)

    def _cancelled(self, ident):
        return (self.control / "cancel" / (ident + ".json")).exists()

    def _execute(self, request, credential, row):
        operation = request["operation"]
        if operation == "initialize":
            binding = self.control / "BINDING.json"
            if binding.exists():
                self._binding()
            else:
                row["phase"] = "initializing_store"
                self._save(row)
                marker = activation.initialize_store(self.store)
                activation._atomic_json(binding, {"store_id": marker["store_id"],
                                                  "store_path": str(self.store)})
            row["state"] = "initialized"
            return
        store_id = self._binding()
        if operation in ("stage", "retry"):
            if operation == "retry":
                previous = self._record(request["target"], credential)
                if (previous["operation"] not in ("stage", "retry")
                        or previous["state"] not in ("failed", "cancelled", "aborted")):
                    raise InstallerError("not_retryable")
            parent = self.store / "transactions" / ("prepare-" + row["request_id"])
            parent.mkdir(mode=0o700)
            required = sum(r.download_bytes + 2 * r.installed_bytes
                           for r in self.catalog.releases) + MARGIN
            if shutil.disk_usage(self.store).free < required:
                raise InstallerError("insufficient_space")
            candidates = {}
            for engine in sorted(catalog.ENTRYPOINTS):
                if self._cancelled(row["request_id"]):
                    raise InstallerError("cancelled")
                release = self.catalog.select(engine, system="linux", architecture="amd64")
                prepared = staging.prepare_release(release, parent,
                                                   cancelled=lambda: self._cancelled(row["request_id"]))
                candidates[engine] = str(prepared)
                row["candidates"] = candidates.copy()
                self._save(row)
            if self._cancelled(row["request_id"]):
                raise InstallerError("cancelled")
            row["state"] = "prepared"
        elif operation == "activate":
            source = self._record(request["target"], credential)
            if (source["state"] != "prepared" or source["operation"] not in ("stage", "retry")
                    or source["catalog_sha256"] != self.catalog_sha256):
                raise InstallerError("candidate_not_current")
            candidates = source.get("candidates", {})
            if set(candidates) != set(catalog.ENTRYPOINTS):
                raise InstallerError("candidate_not_current")
            expected_parent = self.store / "transactions" / ("prepare-" + request["target"])
            for engine, candidate in candidates.items():
                path = Path(candidate)
                if path.parent != expected_parent:
                    raise InstallerError("candidate_not_current")
                # A valid READY.json alone never grants catalog approval.
                if activation._candidate(path) != self.catalog.select(
                        engine, system="linux", architecture="amd64"):
                    raise InstallerError("candidate_not_current")
            releases = {engine: self.catalog.select(engine, system="linux", architecture="amd64")
                        for engine in catalog.ENTRYPOINTS}
            row["expected_generation_id"] = activation._generation_document(releases)["generation_id"]
            current = activation.active_generation(self.store, store_id)
            row["previous_generation_id"] = current["generation_id"] if current else None
            row["phase"] = "activating"
            row["runtime_managed"] = self.runtime is not None
            self._save(row)
            if self.runtime is not None:
                principal_sha256 = hashlib.sha256(
                    credential.principal.encode("utf-8")).hexdigest()
                row.update(self.runtime.switch(
                    row["request_id"], store_id, candidates,
                    row["expected_generation_id"], principal_sha256))
            else:
                row.update(activation.activate_generation(self.store, store_id, candidates,
                                                           self._stop_checked))
                row["state"] = "activated"
        elif operation == "recover":
            target = self._record(request["target"], credential)
            action = request["action"]
            if target.get("runtime_managed") is True:
                raise InstallerError("runtime_rollback_or_resume_required")
            if target["operation"] in ("stage", "retry") and action == "abort":
                target["state"] = "aborted"
            elif target["operation"] == "activate":
                orphans = activation._active_transactions(self.store)
                if len(orphans) == 1 and orphans[0].get("generation_id") == target.get("expected_generation_id"):
                    recovered = activation.recover_transaction(
                        self.store, store_id, orphans[0]["transaction_id"], action,
                        self._stop_checked)
                    target.update(recovered)
                elif not orphans:
                    if self._stop_checked() is not True:
                        raise InstallerError("workers_not_stopped")
                    current = activation.active_generation(self.store, store_id)
                    active_id = current["generation_id"] if current else None
                    if action == "adopt" and active_id == target.get("expected_generation_id"):
                        target["state"] = "adopted"
                        target["generation_id"] = active_id
                    elif action == "abort" and active_id == target.get("previous_generation_id"):
                        target["state"] = "aborted"
                    else:
                        raise InstallerError("host_reconciliation_required")
                else:
                    raise InstallerError("host_reconciliation_required")
            else:
                raise InstallerError("host_reconciliation_required")
            self._save(target)
            row["state"] = "recovered"

    def _stop_checked(self):
        if self.workers_stopped() is not True:
            return False
        if self.verify_volume() is not True:
            raise InstallerError("persistent_volume_unverified")
        self._binding()
        return True
