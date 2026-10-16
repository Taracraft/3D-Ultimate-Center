"""Supervisor-owned app provisioning, independent of the legacy Core-mount installer.

The shipped app release is deliberately absent until its actual runtime, engine
and isolation evidence exists. This module never starts/stops a service, changes
app options, reads credentials, or falls back to shell, Docker or host mounts.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import json
import re

from .const import DOMAIN

REPOSITORY_URL = "https://github.com/Taracraft/3D-Ultimate-Slicer-Server"
DATA_SESSION = "supervisor_app_session"
ACTIONS = frozenset({"status", "install"})
ERRORS = frozenset({"forbidden", "supervisor_unavailable", "app_release_unavailable",
    "app_release_changed", "app_reference_invalid", "app_not_available", "app_identity_changed",
    "app_policy_mismatch", "app_version_mismatch", "app_response_invalid", "app_confirmation_required",
    "app_busy", "app_closed", "app_operation_failed", "app_reconciliation_required", "app_storage_failed"})


class AppError(ValueError):
    """A fixed, non-sensitive diagnostic code."""


def require(condition, code):
    if not condition:
        raise AppError(code)


@dataclass(frozen=True)
class AppRelease:
    """Reviewed source-owned identity, never populated from a browser or discovery.

    evidence_sha256 references a separate release review, not a signature or an
    assertion that this controller has verified the runtime image itself.
    """
    repository: str
    slug: str
    version: str
    evidence_sha256: str

    def __post_init__(self):
        require(type(self.repository) is str and re.fullmatch(r"[0-9a-f]{8}", self.repository)
                and self.repository != "0" * 8, "app_reference_invalid")
        require(self.slug == self.repository + "_ultimate_slicer_server", "app_reference_invalid")
        require(type(self.version) is str and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", self.version)
                and len(self.version) <= 64, "app_reference_invalid")
        require(type(self.evidence_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", self.evidence_sha256)
                and self.evidence_sha256 != "0" * 64, "app_reference_invalid")

    @property
    def identity(self):
        return hashlib.sha256(json.dumps([self.repository, self.slug, self.version,
            self.evidence_sha256], separators=(",", ":")).encode()).hexdigest()


# An image inventory without engines is not a reviewed Supervisor app release.
# Add a real source-owned reference only with its package/isolation/release review.
SHIPPED_RELEASE: AppRelease | None = None


def shipped_release():
    return SHIPPED_RELEASE


def supervisor_available(hass):
    return "hassio" in getattr(getattr(hass, "config", None), "components", set())


def failure(code):
    return {"ok": False, "state": "blocked", "error": code if code in ERRORS else "app_operation_failed"}


class SupervisorBackend:
    """Narrow adapter over the existing HA-owned Supervisor client, no own token.

    Uses the non-v2 store/addons API through aiohasupervisor. Model fields and
    methods follow the official client. Credentials/options/hostnames are not
    returned to the flow and are not logged here.
    """
    def __init__(self, client):
        self.client = client

    @staticmethod
    def _identity(info, release):
        require(info.slug == release.slug and info.repository == release.repository,
                "app_identity_changed")
        require(info.available is True, "app_not_available")
        require(info.build is False and info.detached is False, "app_policy_mismatch")
        for field in ("host_network", "host_pid", "full_access", "docker_api",
                      "homeassistant_api", "supervisor_api", "auth_api"):
            require(getattr(info, field) is False, "app_policy_mismatch")
        require(info.apparmor in {"default", "profile"}, "app_policy_mismatch")
        require(set(info.arch) == {"amd64"}, "app_policy_mismatch")

    async def inspect(self, release):
        repository = await self.client.store.repository_info(release.repository)
        require(repository.slug == release.repository and repository.source in
                {REPOSITORY_URL, REPOSITORY_URL + ".git"}, "app_identity_changed")
        store = await self.client.store.addon_info(release.slug)
        self._identity(store, release)
        require(store.version_latest == release.version, "app_version_mismatch")
        require(type(store.installed) is bool, "app_response_invalid")
        if not store.installed:
            return {"ok": True, "state": "not_installed"}
        installed = await self.client.addons.addon_info(release.slug)
        self._identity(installed, release)
        require(installed.version == release.version, "app_version_mismatch")
        require(installed.protected is True and installed.privileged == [], "app_policy_mismatch")
        require(installed.boot == "manual" and installed.boot_config == "manual_only"
                and installed.auto_update is False, "app_policy_mismatch")
        for field in ("host_ipc", "host_uts", "host_dbus", "kernel_modules", "full_access"):
            require(getattr(installed, field) is False, "app_policy_mismatch")
        state = {"stopped": "installed_stopped", "started": "running_unverified",
                 "startup": "running_unverified"}.get(installed.state)
        require(state is not None, "app_response_invalid")
        return {"ok": True, "state": state}

    async def install(self, release):
        # Official install endpoint installs but does not issue start. It has no
        # exact-version argument; inspect both sides and never auto-start on drift.
        await self.client.store.install_addon(release.slug)


def framework_backend(hass):
    from homeassistant.components.hassio import get_supervisor_client
    return SupervisorBackend(get_supervisor_client(hass))


def framework_journal(hass):
    from homeassistant.helpers.storage import Store
    return Store(hass, 1, DOMAIN + ".supervisor_app_install")


class SupervisorAppSession:
    """One serialized install owner, independent of a browser flow observer.

    A durable pending intent is saved before the Supervisor mutation. A timeout,
    cancellation at shutdown or unverified response cannot silently become a new
    install attempt after restart. Reconciliation is explicit and not implemented
    as a dangerous 'clear pending' button.
    """
    def __init__(self, hass, *, release_provider=shipped_release,
                 backend_factory=framework_backend, journal_factory=framework_journal,
                 read_timeout=20, install_timeout=600):
        self.hass = hass
        self._release_provider = release_provider
        self._backend_factory = backend_factory
        self._journal_factory = journal_factory
        self._read_timeout = read_timeout
        self._install_timeout = install_timeout
        self._backend = self._journal = None
        self._active = None
        self._closed = False
        self._last = failure("app_release_unavailable")

    @property
    def busy(self):
        return self._active is not None and not self._active.done()

    def snapshot(self):
        return {"busy": self.busy, "result": dict(self._last)}

    def invalidate(self):
        self._closed = True

    async def _admin(self, user_id):
        require(type(user_id) is str and bool(user_id), "forbidden")
        user = await self.hass.auth.async_get_user(user_id)
        require(user is not None and user.is_admin is True and user.is_active is True, "forbidden")

    def _current(self, release):
        require(not self._closed, "app_closed")
        require(supervisor_available(self.hass), "supervisor_unavailable")
        require(self._release_provider() == release, "app_release_changed")

    async def _inspect(self, release):
        async with asyncio.timeout(self._read_timeout):
            result = await self._backend.inspect(release)
        self._current(release)
        require(type(result) is dict and result.get("ok") is True and result.get("state") in
                {"not_installed", "installed_stopped", "running_unverified"}, "app_response_invalid")
        return {"ok": True, "state": result["state"]}

    async def _load_record(self, release):
        try:
            record = await self._journal.async_load()
        except Exception:
            raise AppError("app_storage_failed") from None
        if record is None:
            return None
        require(type(record) is dict and set(record) == {"schema", "release", "state"}
                and type(record["schema"]) is int and record["schema"] == 1
                and record["release"] == release.identity
                and record["state"] in {"pending", "installed_stopped"}, "app_reconciliation_required")
        require(record["state"] != "pending", "app_reconciliation_required")
        return record

    async def _save(self, release, state):
        try:
            await self._journal.async_save({"schema": 1, "release": release.identity, "state": state})
        except Exception:
            raise AppError("app_storage_failed") from None

    async def _perform(self, action, user_id):
        mutation_started = False
        try:
            await self._admin(user_id)
            require(not self._closed, "app_closed")
            require(supervisor_available(self.hass), "supervisor_unavailable")
            release = self._release_provider()
            require(release is not None, "app_release_unavailable")
            require(type(release) is AppRelease, "app_reference_invalid")
            if self._backend is None:
                self._backend = self._backend_factory(self.hass)
                self._journal = self._journal_factory(self.hass)
            prior = await self._load_record(release)
            observed = await self._inspect(release)
            if action == "status":
                result = observed
            elif observed["state"] != "not_installed":
                # Never restart/overwrite an already installed instance.
                result = observed
            else:
                require(prior is None, "app_reconciliation_required")
                await self._save(release, "pending")
                self._current(release)
                observed = await self._inspect(release)
                require(observed["state"] == "not_installed", "app_reconciliation_required")
                # The awaited store read may outlive the user's admin role.
                # Recheck authorization immediately before dispatch, then guard
                # a concurrent unload/release change during that user lookup.
                await self._admin(user_id)
                self._current(release)
                mutation_started = True
                async with asyncio.timeout(self._install_timeout):
                    await self._backend.install(release)
                observed = await self._inspect(release)
                require(observed["state"] == "installed_stopped", "app_reconciliation_required")
                await self._save(release, "installed_stopped")
                result = observed
        except asyncio.CancelledError:
            self._last = failure("app_reconciliation_required" if mutation_started else "app_closed")
            raise
        except Exception as error:
            code = str(error) if type(error) is AppError else "app_operation_failed"
            result = failure("app_reconciliation_required" if mutation_started else code)
        self._last = result
        return dict(result)

    async def async_run(self, action, user_id, *, confirmed=False):
        if type(action) is not str or action not in ACTIONS:
            return failure("app_operation_failed")
        if self._closed:
            return failure("app_closed")
        if action == "install" and confirmed is not True:
            return failure("app_confirmation_required")
        if self.busy:
            return failure("app_busy")
        task = self.hass.async_create_task(self._perform(action, user_id))
        self._active = task
        # Keep the owner alive even when a browser's progress observer is cancelled.
        return await asyncio.shield(task)


def get_supervisor_session(hass, entry):
    domain = hass.data.setdefault(DOMAIN, {})
    old = domain.get(DATA_SESSION)
    if old is not None and (not old._closed or old.busy):
        return old
    session = SupervisorAppSession(hass)
    domain[DATA_SESSION] = session
    entry.async_on_unload(session.invalidate)
    return session
