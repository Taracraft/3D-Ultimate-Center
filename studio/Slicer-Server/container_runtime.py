"""Fail-closed Linux container checks and one owned supervisor lifecycle."""
from __future__ import annotations
import os
from pathlib import Path
import signal
import select
import subprocess
import time

class IsolationError(RuntimeError):
    pass

class RecoveryRequired(RuntimeError):
    pass

def observe():
    status = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        key, _, value = line.partition(":")
        status[key] = value.strip()
    return {
        "uids": [int(value) for value in status["Uid"].split()],
        "capabilities": {key: int(status[key], 16) for key in
                         ("CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb")},
        "no_new_privileges": int(status["NoNewPrivs"]),
        "seccomp": int(status["Seccomp"]),
        "interfaces": sorted(p.name for p in Path("/sys/class/net").iterdir()),
        "net_self": os.readlink("/proc/self/ns/net"),
        "net_anchor": os.readlink("/proc/1/ns/net"),
        "pid_self": os.readlink("/proc/self/ns/pid"),
        "pid_anchor": os.readlink("/proc/1/ns/pid"),
    }

def validate(state):
    """Check kernel evidence, never an environment variable claiming isolation.

    This is a necessary runtime contract, not proof of a trusted Docker daemon,
    filesystem immutability, seccomp policy contents, or engine safety.
    """
    if len(state["uids"]) != 4 or any(uid <= 0 for uid in state["uids"]):
        raise IsolationError("nonroot_required")
    required = {"CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb"}
    if set(state["capabilities"]) != required or any(state["capabilities"].values()):
        raise IsolationError("zero_capabilities_required")
    if state["no_new_privileges"] != 1 or state["seccomp"] != 2:
        raise IsolationError("kernel_protection_required")
    if state["interfaces"] != ["lo"]:
        raise IsolationError("network_none_required")
    if not state["net_self"] or not state["net_anchor"] or state["net_self"] == state["net_anchor"]:
        raise IsolationError("separate_anchor_network_required")
    if not state["pid_self"] or state["pid_self"] != state["pid_anchor"]:
        raise IsolationError("shared_pid_visibility_required")
    return state

def require_isolation():
    try:
        return validate(observe())
    except (OSError, KeyError, ValueError) as exc:
        raise IsolationError("kernel_evidence_unavailable") from exc

def start_permit(timeout=10.0):
    """Child callback: call only after the canonical signal handlers are ready."""
    ready = int(os.environ.pop("STUDIO_READY_FD"))
    permit = int(os.environ.pop("STUDIO_PERMIT_FD"))
    try:
        os.write(ready, b"R")
        if not select.select([permit], [], [], timeout)[0]:
            raise RecoveryRequired("start_permission_timeout")
        token = os.read(permit, 1)
        if token not in (b"G", b"S"):
            raise RecoveryRequired("invalid_start_permission")
        return token == b"G"
    finally:
        os.close(ready)
        os.close(permit)

def supervise(command, *, stop, stdout, stderr, env=None, shutdown_timeout=45.0,
              handshake=False, startup_timeout=10.0):
    """Own one child; optionally require readiness before any stop signal.

    With handshake=True the child must call start_permit from the canonical
    before_start callback. Stop before readiness sends a deny token, not a
    signal to an unprepared interpreter. Timeout/failure requires recovery.
    The caller must also inspect the canonical job result before another job.
    """
    if shutdown_timeout <= 0 or startup_timeout <= 0:
        raise ValueError("timeouts_must_be_positive")
    require_isolation()
    if stop.is_set():
        return {"status": "stopped_before_start", "returncode": None}
    fds = []
    child = None
    ready = not handshake
    deadline = None
    startup_deadline = time.monotonic() + startup_timeout if handshake else None
    try:
        options = {"stdout": stdout, "stderr": stderr, "env": env}
        if handshake:
            ready_r, ready_w = os.pipe()
            fds.extend((ready_r, ready_w))
            permit_r, permit_w = os.pipe()
            fds.extend((permit_r, permit_w))
            os.set_blocking(ready_r, False)
            options["pass_fds"] = (ready_w, permit_r)
            options["env"] = {**(os.environ if env is None else env),
                              "STUDIO_READY_FD": str(ready_w), "STUDIO_PERMIT_FD": str(permit_r)}
        child = subprocess.Popen(command, **options)
        if handshake:
            for fd in (ready_w, permit_r):
                os.close(fd)
                fds.remove(fd)
        while True:
            code = child.poll()
            if code is not None:
                if code != 0:
                    raise RecoveryRequired("supervisor_failed:" + str(code))
                if not ready:
                    raise RecoveryRequired("supervisor_exited_before_ready")
                return {"status": "stopped" if deadline is not None else "exited", "returncode": code}
            if not ready:
                try:
                    token = os.read(ready_r, 1)
                except BlockingIOError:
                    token = None
                if token is not None:
                    if token != b"R":
                        raise RecoveryRequired("invalid_supervisor_readiness")
                    denied = stop.is_set()
                    os.write(permit_w, b"S" if denied else b"G")
                    os.close(permit_w)
                    fds.remove(permit_w)
                    ready = True
                    if denied:
                        deadline = time.monotonic() + shutdown_timeout
                elif time.monotonic() >= startup_deadline:
                    raise RecoveryRequired("supervisor_startup_timeout")
            if ready and stop.is_set() and deadline is None:
                child.send_signal(signal.SIGTERM)
                deadline = time.monotonic() + shutdown_timeout
            if deadline is not None and time.monotonic() >= deadline:
                raise RecoveryRequired("supervisor_shutdown_timeout")
            time.sleep(.05)
    except RecoveryRequired as error:
        error.supervisor = child
        raise
    finally:
        for fd in fds:
            os.close(fd)


def exec_isolated(command):
    """Execute only after independently observing the worker kernel contract."""
    if not command:
        raise ValueError("command_required")
    require_isolation()
    os.execvp(command[0], command)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3 or sys.argv[1] != "exec":
        raise SystemExit("usage: container_runtime.py exec COMMAND [ARG...]")
    exec_isolated(sys.argv[2:])
