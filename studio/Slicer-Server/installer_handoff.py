"""Protected local token delivery; never a remote enrollment endpoint."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat

import package_activation as activation
import pairing_registry as pairing
from installer_transport import _directory, _identity, _linux, _uid

TOKEN_FILE = "installer-token.json"
MAX_HANDOFF = 2048


class HandoffError(ValueError):
    """Stable delivery error; no token or path in the message."""


@dataclass(frozen=True, repr=False)
class Handoff:
    host_id: str
    principal: str
    token: str


def _read(directory, *, server_uid, client_uid, host_id):
    root = _directory(directory, server_uid)
    path = root / TOKEN_FILE
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != client_uid or stat.S_IMODE(info.st_mode) != 0o400
            or not 1 <= info.st_size <= MAX_HANDOFF):
        raise HandoffError("unsafe_handoff")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        current = os.fstat(stream.fileno())
        if (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino):
            raise HandoffError("handoff_changed")
        data = stream.read(MAX_HANDOFF + 1)
    if len(data) > MAX_HANDOFF:
        raise HandoffError("unsafe_handoff")
    try:
        value = json.loads(data, object_pairs_hook=pairing._pairs)
        if (type(value) is not dict or set(value) != {"host_id", "principal", "token"}
                or value["host_id"] != host_id or type(value["token"]) is not str
                or re.fullmatch(r"[A-Za-z0-9_-]{64}", value["token"]) is None):
            raise ValueError()
        pairing._principal(value["principal"])
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise HandoffError("invalid_handoff") from None
    return Handoff(**value)


def read_handoff(directory, *, server_uid, expected_host_id):
    """Read as the receiving Linux identity; host identity is pinned externally."""
    _linux()
    return _read(directory, server_uid=_uid(server_uid), client_uid=os.geteuid(),
                 host_id=_identity(expected_host_id))


def _publish_handoff(registry, principal, scopes, directory, *, client_uid, client_gid,
                    rotate=False):
    """Trusted local admin only. Failure attempts revocation, never returns a token."""
    _linux()
    if type(registry) is not pairing.Registry or type(rotate) is not bool:
        raise HandoffError("invalid_handoff_configuration")
    pairing._principal(principal)
    pairing._scopes(scopes)
    uid, gid = _uid(client_uid), _uid(client_gid)
    root = _directory(directory, os.geteuid())
    if root.stat().st_gid != gid:
        raise HandoffError("handoff_group_mismatch")
    target = root / TOKEN_FILE
    if target.exists() or target.is_symlink():
        previous = _read(root, server_uid=os.geteuid(), client_uid=uid, host_id=registry.host_id)
        if not rotate or previous.principal != principal:
            raise HandoffError("handoff_occupied")
    elif rotate:
        raise HandoffError("handoff_missing")
    # Registry commits are durable before publishing a secret. A lost publication
    # must revoke that principal; no automatic rollback to old credentials.
    try:
        token = (registry.rotate(principal, scopes=scopes) if rotate
                 else registry.issue(principal, scopes))
    except Exception:
        # Commit may already be visible, but no token was returned. Do not
        # revoke a possibly concurrent administrator's credential on a guess.
        raise HandoffError("credential_commit_unconfirmed") from None
    temp = root / (".handoff-" + secrets.token_hex(16) + ".tmp")
    try:
        data = json.dumps({"host_id": registry.host_id, "principal": principal, "token": token},
                          sort_keys=True, separators=(",", ":")).encode("ascii")
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fchown(stream.fileno(), uid, gid)
            os.fchmod(stream.fileno(), 0o400)
            os.fsync(stream.fileno())
        # Local admins must serialize enrollment operations for a recipient.
        os.replace(temp, target)
        activation._fsync_directory(root)
        delivered = _read(root, server_uid=os.geteuid(), client_uid=uid, host_id=registry.host_id)
        if not secrets.compare_digest(delivered.token, token):
            raise HandoffError("handoff_changed")
        digest = hashlib.sha256(token.encode("ascii")).digest()
        if not any(c.principal == principal and secrets.compare_digest(c.token_sha256, digest)
                   for c in registry.snapshot()):
            raise HandoffError("handoff_not_current")
    except Exception:
        try:
            registry.revoke(principal)
        except Exception:
            raise HandoffError("delivery_failed_revoke_unconfirmed") from None
        raise HandoffError("delivery_failed_revoked") from None
    finally:
        temp.unlink(missing_ok=True)
    return {"host_id": registry.host_id, "principal": principal, "delivered": True}

def publish_handoff(registry, principal, scopes, directory, *, client_uid, client_gid,
                    rotate=False):
    """Serialize publication across processes before changing registry credentials."""
    _linux()
    root = _directory(directory, os.geteuid())
    fd = pairing._open(root / ".handoff.lock", os.O_RDWR | os.O_CREAT)
    try:
        import fcntl
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise HandoffError("handoff_busy") from None
        try:
            return _publish_handoff(registry, principal, scopes, root,
                                    client_uid=client_uid, client_gid=client_gid,
                                    rotate=rotate)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)
