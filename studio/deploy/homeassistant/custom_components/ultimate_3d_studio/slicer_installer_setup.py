"""Persistent guided HA setup controller for the restricted installer."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

from .slicer_installer_backend import InstallerBackend, InstallerBackendError

STATE_FILE = "installer-setup.json"
MAX_STATE = 8192
ACTIONS = frozenset(("preflight", "initialize", "stage", "retry", "activate", "status",
                     "cancel", "recover", "rollback", "resume"))


RECOVERY_KEY = re.compile(r"recover_(?:stage|retry|activate)_(?:abort|adopt|rollback)")


class InstallerSetupError(ValueError):
    """Stable guided-flow error."""


def _id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        raise InstallerSetupError("invalid_request_id")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InstallerSetupError("invalid_setup_state")
        result[key] = value
    return result


def _empty(host_id, principal):
    return {"schema": 1, "host_id": host_id,
            "principal_sha256": hashlib.sha256(principal.encode("utf-8")).hexdigest(),
            "requests": {}, "last_result": None}


class GuidedInstallerSetup:
    """Generate operation identities server-side and persist before dispatch."""

    def __init__(self, backend, directory):
        if type(backend) is not InstallerBackend:
            raise InstallerSetupError("invalid_backend")
        status = backend.credential_status()
        if status.get("credential_stored") is not True:
            raise InstallerSetupError("installer_pairing_required")
        self.backend = backend
        self.directory = Path(directory)
        if not self.directory.exists():
            self.directory.mkdir(mode=0o700, parents=False)
        if not self.directory.is_absolute() or self.directory.is_symlink():
            raise InstallerSetupError("unsafe_setup_state")
        info = self.directory.stat()
        if not stat.S_ISDIR(info.st_mode) or (os.name != "nt" and info.st_mode & 0o077):
            raise InstallerSetupError("unsafe_setup_state")
        self.path = self.directory / STATE_FILE
        self.initial = _empty(status["host_id"], status["principal"])
        if not self.path.exists():
            self._write(self.initial)
        self._read()

    def _read(self):
        if self.path.is_symlink():
            raise InstallerSetupError("unsafe_setup_state")
        data = self.path.read_bytes()
        if not 1 <= len(data) <= MAX_STATE:
            raise InstallerSetupError("invalid_setup_state")
        try:
            value = json.loads(data, object_pairs_hook=_pairs)
        except (ValueError, UnicodeError, RecursionError):
            raise InstallerSetupError("invalid_setup_state") from None
        if (type(value) is not dict or set(value) != set(self.initial)
                or value["schema"] != 1 or value["host_id"] != self.initial["host_id"]
                or value["principal_sha256"] != self.initial["principal_sha256"]
                or type(value["requests"]) is not dict or len(value["requests"]) > 16
                or value["last_result"] is not None and type(value["last_result"]) is not dict):
            raise InstallerSetupError("invalid_setup_state")
        for action, ident in value["requests"].items():
            if (action not in ACTIONS - {"preflight", "status", "cancel", "recover"}
                    and RECOVERY_KEY.fullmatch(action) is None):
                raise InstallerSetupError("invalid_setup_state")
            _id(ident)
        return value

    def _write(self, value):
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
        if len(data) > MAX_STATE:
            raise InstallerSetupError("invalid_setup_state")
        temp = self.directory / ("." + STATE_FILE + "." + secrets.token_hex(16) + ".tmp")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data); stream.flush()
                if os.name != "nt": os.fchmod(stream.fileno(), 0o600)
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
            if os.name != "nt":
                dfd = os.open(self.directory, os.O_RDONLY)
                try: os.fsync(dfd)
                finally: os.close(dfd)
        finally:
            temp.unlink(missing_ok=True)

    def _request_id(self, state, action):
        if action not in state["requests"]:
            state["requests"][action] = secrets.token_hex(16)
            self._write(state)
        return state["requests"][action]

    def _target(self, state, action):
        if action in ("stage", "retry", "initialize", "activate"):
            if action == "activate":
                source = "retry" if "retry" in state["requests"] else "stage"
            elif action == "retry":
                source = "stage"
            else:
                source = action
        else:
            source = {"status": "activate", "cancel":
                      ("retry" if "retry" in state["requests"] else "stage"),
                      "rollback": "activate", "resume": "activate"}.get(action)
        if source is None or source not in state["requests"]:
            raise InstallerSetupError("setup_step_missing")
        return state["requests"][source]

    def run(self, action, *, target_action=None, recovery_action=None):
        if action not in ACTIONS:
            raise InstallerSetupError("unknown_setup_action")
        state = self._read()
        request = {"protocol": 1, "operation": action}
        if action == "recover":
            if (target_action not in ("stage", "retry", "activate")
                    or recovery_action not in ("abort", "adopt", "rollback")
                    or target_action in ("stage", "retry") and recovery_action != "abort"):
                raise InstallerSetupError("invalid_recovery_action")
            key = "recover_" + target_action + "_" + recovery_action
            request["request_id"] = self._request_id(state, key)
            if target_action not in state["requests"]:
                raise InstallerSetupError("setup_step_missing")
            request["target"] = state["requests"][target_action]
            request["action"] = recovery_action
        else:
            if target_action is not None or recovery_action is not None:
                raise InstallerSetupError("invalid_setup_action")
            if action in ("initialize", "stage", "retry", "activate"):
                request["request_id"] = self._request_id(state, action)
            if action in ("retry", "activate", "status", "cancel", "rollback", "resume"):
                request["target"] = self._target(state, action)
        try:
            result = self.backend.request(request)
        except InstallerBackendError:
            result = {"ok": False, "error": "installer_unavailable"}
        # Backend already rejects secrets and non-JSON responses.
        state = self._read()
        state["last_result"] = result
        self._write(state)
        return result
    def public_status(self):
        state = self._read()
        return {"paired": True, "host_id": state["host_id"],
                "requests": dict(state["requests"]), "last_result": state["last_result"]}
