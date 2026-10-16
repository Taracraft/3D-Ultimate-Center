"""Lazy, non-blocking HA binding for the existing restricted installer.

Import/setup never connects to a host or installs anything. Explicit options
flow actions use fixed provisioned pins and the existing peer-verified client.
"""
from __future__ import annotations

import asyncio
from functools import partial
import hashlib
import os
from pathlib import Path
import stat

from .const import DOMAIN
from .slicer_installer_backend import InstallerBackend, InstallerCredentialStore
from .slicer_installer_endpoint import load_provisioned_installer_endpoint
from .slicer_installer_setup import GuidedInstallerSetup
from .slicer_connection_handoff import ConnectionHandoffError, read_connection_offer

DATA_INSTALLERS = "installer_sessions"
CONTROL_ACTIONS = frozenset(("connect", "preflight", "status", "cancel"))
RECOVERY_ACTIONS = {
    "recover_stage": ("stage", "abort"),
    "recover_retry": ("retry", "abort"),
    "recover_activation": ("activate", "adopt"),
    "recover_rollback": ("activate", "rollback"),
}
MUTATION_ACTIONS = frozenset(("install", "initialize", "stage", "retry", "activate",
                             "rollback", "resume", "configure_connection", *RECOVERY_ACTIONS))
ACTIONS = CONTROL_ACTIONS | MUTATION_ACTIONS
STATES = frozenset(("paired", "available", "blocked", "initialized", "running", "prepared",
                    "activated", "ready_paused", "restored_paused", "complete", "cancel_requested",
                    "cancelled", "failed", "aborted", "adopted", "recovered", "rolled_back",
                    "rolled_back_absent", "busy", "unknown", "connection_verified"))
ERRORS = frozenset(("installer_unavailable", "installer_not_provisioned", "installer_busy",
                   "installer_closed", "installer_pairing_required", "endpoint_changed",
                   "unknown_setup_action", "setup_step_missing", "invalid_setup_state",
                   "unsafe_setup_state", "engine_releases_pending", "package_rejected",
                   "storage_or_activation_rejected", "insufficient_space", "not_cancellable",
                   "not_retryable", "recovery_required", "not_recoverable", "forbidden",
                   "response_unavailable", "operation_failed", "installer_failed",
                   "runtime_adapter_required", "runtime_rollback_or_resume_required",
                   "host_reconciliation_required", "persistent_volume_unverified",
                   "unsupported_platform", "unsupported_host", "unexpected_installer_state",
                   "connection_handoff_missing", "invalid_connection_handoff",
                   "unsafe_connection_handoff", "connection_handoff_changed",
                   "connection_configuration_changed", "connection_not_verified",
                   "slicer_certificate_error", "slicer_auth_required", "slicer_unavailable",
                   "slicer_incompatible", "slicer_redirect_refused"))


def safe_result(value):
    """Whitelist UI fields and values; never expose raw host errors or credentials."""
    if type(value) is not dict or type(value.get("ok")) is not bool:
        return {"ok": False, "state": "unknown", "error": "installer_failed"}
    result = {"ok": value["ok"]}
    state = value.get("state")
    result["state"] = state if type(state) is str and state in STATES else "unknown"
    if not value["ok"]:
        error = value.get("error")
        result["error"] = error if type(error) is str and error in ERRORS else "installer_failed"
    reasons = value.get("reasons")
    if type(reasons) is list:
        result["reasons"] = sorted({x for x in reasons if type(x) is str and x in ERRORS})
    if value.get("outcome") == "unknown":
        result["outcome"] = "unknown"
    return result


def _private_storage(root):
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("unsafe_setup_state")
    for path in reversed((root, *root.parents)):
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError("unsafe_setup_state")
    # Only the fixed integration-owned hierarchy is created by the caller.
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != "nt":
        info = root.stat()
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("unsafe_setup_state")
    return root


def _create_controller(storage, endpoint):
    root = _private_storage(storage)
    store = InstallerCredentialStore(root / "credential",
                                    expected_host_id=endpoint.host_id,
                                    server_uid=endpoint.server_uid)
    # Corruption is not absence: never silently replace a bad credential.
    if store.path.exists() or store.path.is_symlink():
        store.load()
    else:
        store.adopt_handoff(endpoint.handoff_directory)
    backend = InstallerBackend(store, endpoint.socket_directory,
                               server_uid=endpoint.server_uid, timeout=10.0)
    return GuidedInstallerSetup(backend, root / "setup")


class InstallerSession:
    """One lazy session per ConfigEntry; RPC work is never run on HA's event loop."""

    def __init__(self, hass, storage, *, endpoint_loader=load_provisioned_installer_endpoint,
                 controller_factory=_create_controller, entry=None, connection_probe=None):
        self.hass = hass
        self.storage = Path(storage)
        self._endpoint_loader = endpoint_loader
        self._controller_factory = controller_factory
        self._entry = entry
        self._connection_probe = connection_probe
        self._pending_connection = None
        self._endpoint = None
        self._controller = None
        self._connecting = asyncio.Lock()
        self._active = None
        self._active_action = None
        self._tasks = set()
        self._closed = False
        self._last = {"ok": False, "state": "unknown", "error": "installer_not_provisioned"}

    def snapshot(self):
        return {"paired": self._controller is not None,
                "busy": self._active is not None and not self._active.done(),
                "operation": self._active_action,
                "result": safe_result(self._last)}

    def _open_controller(self):
        endpoint = self._endpoint_loader()
        controller = self._controller_factory(self.storage, endpoint)
        if self._endpoint_loader() != endpoint:
            raise ValueError("endpoint_changed")
        return endpoint, controller

    async def _connect(self):
        async with self._connecting:
            if self._closed:
                raise ValueError("installer_closed")
            if self._controller is None:
                endpoint, controller = await self.hass.async_add_executor_job(self._open_controller)
                if self._closed:
                    raise ValueError("installer_closed")
                self._endpoint, self._controller = endpoint, controller

    def _request_checked(self, action, kwargs):
        if self._endpoint_loader() != self._endpoint:
            raise ValueError("endpoint_changed")
        result = self._controller.run(action, **kwargs)
        if self._endpoint_loader() != self._endpoint:
            return {"ok": False, "error": "endpoint_changed", "outcome": "unknown"}
        return result

    async def _request(self, action, **kwargs):
        return await self.hass.async_add_executor_job(partial(self._request_checked, action, kwargs))

    def _connection_fingerprint(self):
        if self._entry is None:
            raise ConnectionHandoffError("connection_not_verified")
        # Only conflicting changes to the connection itself block application;
        # other current options are merged at the final native OptionsFlow step.
        import json
        values = {**self._entry.data, **self._entry.options}
        selected = {key: values.get(key) for key in
                    ("slicer_enabled", "slicer_base_url", "slicer_api_secret")}
        raw = json.dumps(selected, sort_keys=True, allow_nan=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _read_connection_checked(self):
        if self._endpoint_loader() != self._endpoint:
            raise ConnectionHandoffError("endpoint_changed")
        credential = self._controller.backend.credential_status()
        if (credential.get("credential_stored") is not True
                or credential.get("host_id") != self._endpoint.host_id):
            raise ConnectionHandoffError("installer_pairing_required")
        offer = read_connection_offer(
            self._endpoint.handoff_directory, server_uid=self._endpoint.server_uid,
            expected_host_id=self._endpoint.host_id, expected_principal=credential.get("principal"))
        if self._endpoint_loader() != self._endpoint:
            raise ConnectionHandoffError("endpoint_changed")
        return offer

    async def _prepare_connection(self):
        self._pending_connection = None
        fingerprint = self._connection_fingerprint()
        offer = await self.hass.async_add_executor_job(self._read_connection_checked)
        if self._connection_probe is None:
            # These modules are already loaded by the integration's config flow.
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            from .slicer_connection_probe import async_probe_slicer_connection
            checked = await async_probe_slicer_connection(
                async_get_clientsession(self.hass), offer.base_url, offer.api_secret)
        else:
            checked = await self._connection_probe(self.hass, offer.base_url, offer.api_secret)
        if type(checked) is not dict or checked.get("status") != "ready":
            raise ConnectionHandoffError("slicer_incompatible")
        after = await self.hass.async_add_executor_job(self._read_connection_checked)
        if not offer.same_file(after):
            raise ConnectionHandoffError("connection_handoff_changed")
        if self._closed or self._connection_fingerprint() != fingerprint:
            raise ConnectionHandoffError("connection_configuration_changed")
        self._pending_connection = (offer, fingerprint)
        return {"ok": True, "state": "connection_verified"}

    async def async_connection_options(self, entry):
        """Private result for OptionsFlow only; no secret is returned by async_run/snapshot.

        Home Assistant persists options via the native flow completion. The
        protected host offer is retained, not deleted on an in-memory acknowledgement.
        """
        pending = self._pending_connection
        try:
            if (self._closed or entry is not self._entry or pending is None
                    or self._active is not None and not self._active.done()):
                raise ConnectionHandoffError("connection_not_verified")
            offer, fingerprint = pending
            after = await self.hass.async_add_executor_job(self._read_connection_checked)
            if self._closed or self._pending_connection is not pending or not offer.same_file(after):
                raise ConnectionHandoffError("connection_handoff_changed")
            if self._connection_fingerprint() != fingerprint:
                raise ConnectionHandoffError("connection_configuration_changed")
            result = {**entry.options, "slicer_enabled": True,
                      "slicer_base_url": offer.base_url, "slicer_api_secret": offer.api_secret}
            self._pending_connection = None
            return result
        except Exception as error:
            self._pending_connection = None
            key = str(error)
            self._last = {"ok": False, "state": "unknown",
                          "error": key if key in ERRORS else "connection_not_verified"}
            return None

    async def _perform(self, action):
        try:
            await self._connect()
            if action == "connect":
                result = {"ok": True, "state": "paired"}
            elif action == "configure_connection":
                result = await self._prepare_connection()
            elif action == "install":
                result = await self._request("preflight")
                if result.get("ok") is True and result.get("state") == "available":
                    for operation, expected in (("initialize", "initialized"),
                                                ("stage", "prepared"),
                                                ("activate", "ready_paused")):
                        if self._closed:
                            raise ValueError("installer_closed")
                        result = await self._request(operation)
                        if result.get("ok") is not True:
                            break
                        if result.get("state") != expected:
                            result = {"ok": False, "error": "unexpected_installer_state",
                                      "outcome": "unknown"}
                            break
                # Resume remains an explicit separate action; no queued job is released.
            elif action in RECOVERY_ACTIONS:
                target, recovery = RECOVERY_ACTIONS[action]
                result = await self._request("recover", target_action=target,
                                             recovery_action=recovery)
            else:
                result = await self._request(action)
            result = safe_result(result)
        except Exception as error:
            key = str(error)
            result = {"ok": False, "state": "unknown",
                      "error": key if key in ERRORS else "installer_unavailable"}
        self._last = result
        return safe_result(result)

    async def async_run(self, action):
        if type(action) is not str or action not in ACTIONS:
            return {"ok": False, "state": "unknown", "error": "unknown_setup_action"}
        if self._closed:
            return {"ok": False, "state": "unknown", "error": "installer_closed"}
        if action in MUTATION_ACTIONS and self._active is not None and not self._active.done():
            return {"ok": False, "state": "busy", "error": "installer_busy"}
        if action in MUTATION_ACTIONS:
            self._pending_connection = None
        task = self.hass.async_create_task(self._perform(action))
        self._tasks.add(task)
        if action in MUTATION_ACTIONS:
            self._active = task
            self._active_action = action
        task.add_done_callback(self._tasks.discard)
        # Closing a browser flow must not cancel an executor thread or replay a mutation.
        return await asyncio.shield(task)

    async def async_close(self):
        self._closed = True
        self._pending_connection = None
        tasks = tuple(self._tasks)
        if tasks:
            await asyncio.shield(asyncio.gather(*tasks, return_exceptions=True))
        self._controller = None
        self._endpoint = None


def register_installer_session(hass, entry):
    sessions = hass.data.setdefault(DOMAIN, {}).setdefault(DATA_INSTALLERS, {})
    if entry.entry_id not in sessions:
        identity = hashlib.sha256(entry.entry_id.encode("utf-8")).hexdigest()
        sessions[entry.entry_id] = InstallerSession(
            hass, hass.config.path(DOMAIN + "_installer", identity), entry=entry)
    return sessions[entry.entry_id]


def get_installer_session(hass, entry):
    return hass.data.get(DOMAIN, {}).get(DATA_INSTALLERS, {}).get(entry.entry_id)


async def async_remove_installer_session(hass, entry):
    sessions = hass.data.get(DOMAIN, {}).get(DATA_INSTALLERS, {})
    current = sessions.get(entry.entry_id)
    if current is not None:
        await current.async_close()
        if sessions.get(entry.entry_id) is current:
            sessions.pop(entry.entry_id, None)
