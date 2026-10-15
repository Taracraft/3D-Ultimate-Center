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

DATA_INSTALLERS = "installer_sessions"
CONTROL_ACTIONS = frozenset(("connect", "preflight", "status", "cancel"))
RECOVERY_ACTIONS = {
    "recover_stage": ("stage", "abort"),
    "recover_retry": ("retry", "abort"),
    "recover_activation": ("activate", "adopt"),
    "recover_rollback": ("activate", "rollback"),
}
MUTATION_ACTIONS = frozenset(("install", "initialize", "stage", "retry", "activate",
                             "rollback", "resume", *RECOVERY_ACTIONS))
ACTIONS = CONTROL_ACTIONS | MUTATION_ACTIONS
STATES = frozenset(("paired", "available", "blocked", "initialized", "running", "prepared",
                    "activated", "ready_paused", "restored_paused", "complete", "cancel_requested",
                    "cancelled", "failed", "aborted", "adopted", "recovered", "rolled_back",
                    "rolled_back_absent", "busy", "unknown"))
ERRORS = frozenset(("installer_unavailable", "installer_not_provisioned", "installer_busy",
                   "installer_closed", "installer_pairing_required", "endpoint_changed",
                   "unknown_setup_action", "setup_step_missing", "invalid_setup_state",
                   "unsafe_setup_state", "engine_releases_pending", "package_rejected",
                   "storage_or_activation_rejected", "insufficient_space", "not_cancellable",
                   "not_retryable", "recovery_required", "not_recoverable", "forbidden",
                   "response_unavailable", "operation_failed", "installer_failed",
                   "runtime_adapter_required", "runtime_rollback_or_resume_required",
                   "host_reconciliation_required", "persistent_volume_unverified",
                   "unsupported_platform", "unsupported_host", "unexpected_installer_state"))


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
                 controller_factory=_create_controller):
        self.hass = hass
        self.storage = Path(storage)
        self._endpoint_loader = endpoint_loader
        self._controller_factory = controller_factory
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

    async def _perform(self, action):
        try:
            await self._connect()
            if action == "connect":
                result = {"ok": True, "state": "paired"}
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
            hass, hass.config.path(DOMAIN + "_installer", identity))
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
