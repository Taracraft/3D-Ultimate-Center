"""Container service candidate: one queue owner and one telemetry writer.

The source preflight remains the default image command. No engine is bundled.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import re
import stat
import importlib.util
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
PAYLOAD = ROOT / "payload"
# Source-tree imports are also supported by offline tests.
sys.path.insert(0, str(ROOT))
from container_runtime import require_isolation, supervise, start_permit, RecoveryRequired

PROFILE_BASE = Path("/var/lib/ultimate-slicer-profiles")
PROFILE_LIMIT = 256
PROFILE_BYTES = 65536
DATA_LAYOUT = ("data", "data/uploads", "data/jobs", "data/output",
               "api", "web", "run", "run/job-locks")
DATA_STATE_BYTES = 4096
SECRET_BYTES = 4096
TLS_BYTES = 1024 * 1024

def _absolute_unlinked(path, label):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError(label + "_absolute_path_required")
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError(label + "_link_rejected")
    return path

def _regular_bytes(path, maximum, label, *, private=False):
    path = _absolute_unlinked(path, label)
    try:
        info = path.lstat()
    except OSError as exc:
        raise ValueError(label + "_file_required") from exc
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_size < 1 or info.st_size > maximum):
        raise ValueError(label + "_regular_bounded_file_required")
    if os.name == "posix":
        if info.st_uid not in {0, os.geteuid()}:
            raise ValueError(label + "_owner_rejected")
        if private:
            if info.st_gid not in {0, os.getegid()} or info.st_mode & 0o027:
                raise ValueError(label + "_permissions_rejected")
        elif info.st_mode & 0o022:
            raise ValueError(label + "_permissions_rejected")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as source:
        actual = os.fstat(source.fileno())
        if (actual.st_ino, actual.st_dev) != (info.st_ino, info.st_dev):
            raise ValueError(label + "_file_changed")
        raw = source.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError(label + "_file_too_large")
    return raw

def _data_directory(path):
    path = _absolute_unlinked(path, "data")
    if not path.is_dir() or not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError("data_directory_required")
    return path

def _data_sync(directory):
    if os.name == "posix":
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

@contextmanager
def _data_lock(base):
    path = base / ".data-init.lock"
    if path.is_symlink():
        raise ValueError("data_lock_rejected")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_BINARY", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1:
            raise ValueError("data_lock_rejected")
        if os.name == "posix":
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt
            if info.st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        yield
    finally:
        os.close(fd)

def _data_state(path):
    raw = _regular_bytes(path, DATA_STATE_BYTES, "data_state", private=True)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("data_state_duplicate_key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    if (not isinstance(value, dict) or set(value) != {"schema", "state", "layout"}
            or type(value["schema"]) is not int or value["schema"] != 1
            or value["state"] not in {"preparing", "ready"}
            or value["layout"] != list(DATA_LAYOUT)):
        raise ValueError("data_state_invalid")
    return value

def persistent_data(base):
    """Validate the complete persistent runtime tree without creating or adopting it."""
    base = _data_directory(base)
    expected = {"DATA_STATE.json", ".data-init.lock", "data", "api", "web", "run"}
    actual = {path.name for path in base.iterdir()}
    if actual - expected - {"last_job.json"} or not expected <= actual:
        raise ValueError("data_unrecognized_store")
    if "last_job.json" in actual:
        # dispatch-job.sh publishes this terminal result after the first job.
        # It is owned metadata, not a reason to stop the next dispatcher.
        last = json.loads(_regular_bytes(base / "last_job.json", 65536,
                                         "last_job", private=True))
        if (not isinstance(last, dict) or not isinstance(last.get("job_id"), str)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", last["job_id"]) is None
                or last.get("status") not in {"completed", "failed", "cancelled"}):
            raise ValueError("last_job_invalid")
    lock = (base / ".data-init.lock").lstat()
    if not stat.S_ISREG(lock.st_mode) or lock.st_nlink != 1 or lock.st_size > 1:
        raise ValueError("data_lock_rejected")
    state = _data_state(base / "DATA_STATE.json")
    if state["state"] != "ready":
        raise ValueError("data_recovery_required")
    for relative in DATA_LAYOUT:
        directory = _data_directory(base / relative)
        if os.name == "posix":
            info = directory.stat()
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError("data_permissions_rejected")
    return base

def initialize_data(base, *, maintenance_request_id=None):
    """One-shot initialization; optionally install a durable dispatch barrier.

    The local host orchestrator supplies this validated request ID before it
    starts the API or worker. Maintenance is written by the canonical JobControl
    implementation so its dispatcher lock and queue semantics remain shared.
    """
    if (maintenance_request_id is not None
            and (type(maintenance_request_id) is not str
                 or re.fullmatch(r"[a-f0-9]{32}", maintenance_request_id) is None)):
        raise ValueError("invalid_maintenance_id")
    base = _data_directory(base)
    with _data_lock(base):
        if (base / "DATA_STATE.json").exists():
            persistent_data(base)
            if maintenance_request_id is not None:
                canonical().JobControl(base).begin_maintenance(maintenance_request_id)
            return {"initialized": False, "state": "ready",
                    "dispatch_blocked": maintenance_request_id is not None}
        if {path.name for path in base.iterdir()} != {".data-init.lock"}:
            raise ValueError("data_foreign_contents")
        state = {"schema": 1, "state": "preparing", "layout": list(DATA_LAYOUT)}
        encode = lambda value: (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
        _profile_write(base / "DATA_STATE.json", encode(state))
        _data_sync(base)
        for relative in DATA_LAYOUT:
            directory = base / relative
            directory.mkdir(mode=0o700)
            if os.name == "posix":
                os.chmod(directory, 0o700)
        # Flush final directory contents, children before parents. A directory
        # synced before its children were created does not persist those entries.
        for relative in sorted(DATA_LAYOUT, key=lambda value: len(Path(value).parts), reverse=True):
            _data_sync(base / relative)
        _data_sync(base)
        state["state"] = "ready"
        _profile_write(base / ".data-ready.tmp", encode(state))
        os.replace(base / ".data-ready.tmp", base / "DATA_STATE.json")
        _data_sync(base)
        persistent_data(base)
        if maintenance_request_id is not None:
            canonical().JobControl(base).begin_maintenance(maintenance_request_id)
        return {"initialized": True, "state": "ready",
                "dispatch_blocked": maintenance_request_id is not None}

def recover_data_layout(base, *, verified_legacy_error=False):
    """Recover only the proven first-job metadata failure with no active owner.

    The host installer must first verify the stopped owned worker and its exact
    legacy traceback. Both kernel file locks independently reject a live worker.
    Unknown recovery errors and unfinished jobs stay blocked.
    """
    if verified_legacy_error is not True:
        raise ValueError("legacy_layout_failure_proof_required")
    base = persistent_data(base)
    jc = canonical()
    control = jc.JobControl(base)
    marker = control.run / "container-recovery.json"
    journal = control.run / "data-layout-recovery.json"
    with jc.file_lock(control.run / "container-service.guard", nonblocking=True):
        with jc.file_lock(control.run / "dispatcher.guard", nonblocking=True):
            if not marker.exists():
                return {"recovered": False, "state": "no_recovery_marker"}
            recovery_raw = _regular_bytes(marker, 4096, "recovery", private=True)
            recovery = json.loads(recovery_raw)
            if (not isinstance(recovery, dict) or recovery.get("requires_recovery") is not True
                    or recovery.get("error") != "RecoveryRequired"
                    or recovery.get("reason") not in {None, "supervisor_failed:1"}):
                raise ValueError("unrecognized_recovery_error")
            for status in ("slicing", "cancelling", "interrupted"):
                if any(control.jobs.glob("*." + status + ".json")):
                    raise ValueError("unfinished_job_requires_recovery")
            last_raw = _regular_bytes(base / "last_job.json", 65536, "last_job", private=True)
            last = json.loads(last_raw)
            job_id, state = last["job_id"], last["status"]
            terminal = control.jobs / (job_id + "." + state + ".json")
            _regular_bytes(terminal, 4 * 1024 * 1024, "terminal_job", private=True)
            result_raw = _regular_bytes(control.output / (job_id + ".result.json"), 65536,
                                        "terminal_result", private=True)
            if json.loads(result_raw) != last or journal.exists():
                raise ValueError("terminal_result_reconciliation_required")
            jc.atomic_json(journal, {"schema": 1, "recovery": recovery,
                "job_id": job_id, "terminal_status": state,
                "last_result_sha256": hashlib.sha256(last_raw).hexdigest(),
                "recovered_at": jc.utcnow()})
            # Preserve evidence before clearing exactly the checked marker.
            if _regular_bytes(marker, 4096, "recovery", private=True) != recovery_raw:
                raise ValueError("recovery_marker_changed")
            marker.unlink()
            _data_sync(control.run)
    return {"recovered": True, "state": "metadata_layout_reconciled"}

def _profile_directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("profile_absolute_path_required")
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("profile_link_rejected")
    if not path.is_dir():
        raise ValueError("profile_directory_required")
    return path

def _profile_json(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > PROFILE_BYTES:
        raise ValueError("profile_regular_bounded_file_required")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
    with os.fdopen(fd, "rb") as source:
        actual = os.fstat(source.fileno())
        if (actual.st_ino, actual.st_dev) != (info.st_ino, info.st_dev):
            raise ValueError("profile_file_changed")
        raw = source.read(PROFILE_BYTES + 1)
    if len(raw) > PROFILE_BYTES:
        raise ValueError("profile_file_too_large")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("profile_duplicate_key")
            result[key] = value
        return result
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("profile_nonfinite")))
    if not isinstance(value, dict):
        raise ValueError("profile_object_required")
    return value, raw

def _profile_files(directory):
    directory = _profile_directory(directory)
    result = {}
    total = 0
    for path in directory.iterdir():
        if len(result) >= PROFILE_LIMIT:
            raise ValueError("profile_count_limit")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}\.json", path.name):
            raise ValueError("profile_filename_rejected")
        value, raw = _profile_json(path)
        if value.get("id") != path.stem:
            raise ValueError("profile_identifier_mismatch")
        total += len(raw)
        if total > 8 * 1024 * 1024:
            raise ValueError("profile_total_limit")
        result[path.name] = raw
    if not result:
        raise ValueError("profile_empty_store")
    return result

def _profile_sync(directory):
    if os.name == "posix":
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

def _profile_write(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(raw)
        target.flush()
        os.fsync(target.fileno())

@contextmanager
def _profile_lock(base):
    path = base / ".profile-init.lock"
    if path.is_symlink():
        raise ValueError("profile_lock_rejected")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_BINARY", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1:
            raise ValueError("profile_lock_rejected")
        if os.name == "posix":
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            import msvcrt
            if info.st_size == 0:
                os.write(fd, b"0")
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        yield
    finally:
        os.close(fd)

def persistent_profiles(profile_base=PROFILE_BASE):
    """Validate a prepared read-only mount; never fall back to image profiles."""
    base = _profile_directory(profile_base)
    if {p.name for p in base.iterdir()} != {"PROFILE_STATE.json", "printers", ".profile-init.lock"}:
        raise ValueError("profile_unrecognized_store")
    lock = (base / ".profile-init.lock").lstat()
    if not stat.S_ISREG(lock.st_mode) or lock.st_nlink != 1 or lock.st_size > 1:
        raise ValueError("profile_lock_rejected")
    state, _ = _profile_json(base / "PROFILE_STATE.json")
    if (set(state) != {"schema", "state", "seed_sha256"} or state["schema"] != 1
            or state["state"] != "ready" or not isinstance(state["seed_sha256"], dict)
            or not state["seed_sha256"] or len(state["seed_sha256"]) > PROFILE_LIMIT):
        raise ValueError("profile_recovery_required")
    profiles = _profile_files(base / "printers")
    for name, digest in state["seed_sha256"].items():
        if (name not in profiles or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("profile_seed_record_invalid")
    # Digests describe the original seed, not a mandate to overwrite user edits.
    return base / "printers"

def initialize_profiles(profile_base=PROFILE_BASE, *, seed=None):
    """Explicit one-shot initialization on an already provisioned, stopped host."""
    base = _profile_directory(profile_base)
    with _profile_lock(base):
        if (base / "PROFILE_STATE.json").exists():
            persistent_profiles(base)
            return {"initialized": False, "state": "ready"}
        if {p.name for p in base.iterdir()} != {".profile-init.lock"}:
            raise ValueError("profile_foreign_contents")
        files = _profile_files(seed if seed is not None else PAYLOAD / "profiles/printers")
        state = {"schema": 1, "state": "preparing",
                 "seed_sha256": {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
        encode = lambda value: (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
        _profile_write(base / "PROFILE_STATE.json", encode(state))
        _profile_sync(base)
        directory = base / "printers"
        directory.mkdir(mode=0o700)
        for name, raw in files.items():
            _profile_write(directory / name, raw)
        _profile_sync(directory)
        state["state"] = "ready"
        _profile_write(base / ".profile-ready.tmp", encode(state))
        os.replace(base / ".profile-ready.tmp", base / "PROFILE_STATE.json")
        _profile_sync(base)
        persistent_profiles(base)
        return {"initialized": True, "state": "ready"}

def canonical():
    spec = importlib.util.spec_from_file_location("container_job_control", PAYLOAD / "job_control.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def emit(event, **values):
    print(json.dumps({"event": event, **values}, sort_keys=True), flush=True)

def configure_environment(base, profile_base=PROFILE_BASE):
    base = persistent_data(base)
    profiles = persistent_profiles(profile_base)
    os.environ.update(STUDIO_WORKER_BASE=str(base), STUDIO_WORKER_SOURCE_ROOT=str(PAYLOAD),
                      STUDIO_WORKER_PROFILE_ROOT=str(profiles),
                      STUDIO_WORKER_H2S_PROFILE=str(profiles / "bambu_lab_h2s_04.json"),
                      STUDIO_WORKER_X1C_PROFILE=str(profiles / "bambu_lab_x1c_04.json" if (profiles / "bambu_lab_x1c_04.json").is_file() else PAYLOAD / "bambu_lab_x1c_04.json"),
                      STUDIO_BAMBU_ROOT="/engine/bambu_studio", STUDIO_WORKER_ISOLATION="container")

def terminal_requires_recovery(result):
    return (not isinstance(result, dict) or result.get("requires_recovery") is True
            or result.get("status") not in {"idle", "maintenance", "completed", "failed", "cancelled"})

def dispatch_child(base, result_path):
    jc = canonical()
    permitted = False
    # Idle/blocked dispatches do not enter JobControl's signal-handler scope.
    # These handlers make their readiness acknowledgement safe too.
    old = {s: signal.signal(s, lambda *_: None) for s in (signal.SIGTERM, signal.SIGINT)}
    def before_start():
        nonlocal permitted
        require_isolation()
        permitted = True
        return start_permit()
    try:
        result = jc.JobControl(base).dispatch(PAYLOAD / "dispatch-job.sh", before_start=before_start)
        if not permitted:
            start_permit()  # No dispatcher exists in this branch.
        jc.atomic_json(result_path, result)
    finally:
        for s, handler in old.items():
            signal.signal(s, handler)

def run_worker(base, *, interval=1.0, refresh_interval=5.0, profile_base=PROFILE_BASE):
    if interval <= 0 or refresh_interval <= 0:
        raise ValueError("positive_intervals_required")
    require_isolation()
    if shutil.which("jq") is None:
        raise RuntimeError("jq_dependency_missing")
    jc = canonical()
    control = jc.JobControl(base)
    stop = threading.Event()
    telemetry_stop = threading.Event()
    failures = []
    recovery = control.run / "container-recovery.json"
    result_path = control.run / "container-dispatch-result.json"
    heartbeat = control.run / "container-worker.json"
    identity = jc.process_identity(os.getpid())
    old = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGTERM, signal.SIGINT)}
    thread = None
    # Hold across all jobs and telemetry cycles; restart cannot overlap.
    try:
        with jc.file_lock(control.run / "container-service.guard", nonblocking=True):
            if recovery.exists() or any(control.jobs.glob("*.slicing.json")):
                raise RecoveryRequired("retained_state_requires_recovery")
            def status(state):
                jc.atomic_json(heartbeat, {"status": state, "pid": os.getpid(),
                    "identity": identity, "updated_at_epoch": time.time(),
                    "container_deploy_ready": False, "maintenance": control.maintenance_pending()})
            def refresh():
                try:
                    with jc.file_lock(control.run / "container-telemetry.guard", nonblocking=True):
                        while not telemetry_stop.is_set():
                            child = subprocess.Popen(["/bin/sh", "-e", str(PAYLOAD / "refresh-state.sh")],
                                                     stdout=subprocess.DEVNULL, start_new_session=True)
                            deadline = time.monotonic() + 30
                            timed_out = False
                            try:
                                while os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
                                    if time.monotonic() >= deadline:
                                        timed_out = True
                                        break
                                    if telemetry_stop.wait(.05):
                                        break
                            finally:
                                jc.JobControl._stop_group(child, 2, 2)
                            if not telemetry_stop.is_set() and (timed_out or child.returncode != 0):
                                raise RuntimeError("telemetry_refresh_failed")
                            status("stopping" if stop.is_set() else "running")
                            telemetry_stop.wait(refresh_interval)
                except BaseException as exc:
                    failures.append(type(exc).__name__)
                    stop.set()
            status("starting")
            thread = threading.Thread(target=refresh, name="container-telemetry", daemon=True)
            thread.start()
            emit("worker-started", pid=os.getpid(), container_deploy_ready=False)
            try:
                while not stop.is_set():
                    result_path.unlink(missing_ok=True)
                    supervise([sys.executable, str(Path(__file__).resolve()), "dispatch",
                               "--base", str(base), "--profiles", str(profile_base)], stop=stop, stdout=sys.stdout,
                              stderr=sys.stderr, handshake=True)
                    if result_path.exists():
                        result = json.loads(result_path.read_text())
                        if terminal_requires_recovery(result):
                            raise RecoveryRequired("canonical_result_requires_recovery")
                    elif not stop.is_set():
                        raise RecoveryRequired("canonical_result_missing")
                    stop.wait(interval)
                if failures:
                    raise RecoveryRequired("telemetry_failed")
            except BaseException as exc:
                # Only a controlled recovery can clear this latch. Never silently
                # advance to the next queued job after an unknown child outcome.
                reason = str(exc)
                if re.fullmatch(r"[a-z0-9_:.-]{1,120}", reason) is None:
                    reason = type(exc).__name__
                jc.atomic_json(recovery, {"requires_recovery": True, "error": type(exc).__name__,
                                          "reason": reason, "updated_at": jc.utcnow()})
                emit("worker-recovery-required", error=type(exc).__name__, reason=reason)
                raise
            finally:
                telemetry_stop.set()
                if thread is not None:
                    thread.join(35)
                    if thread.is_alive():
                        jc.atomic_json(recovery, {"requires_recovery": True, "error": "telemetry_shutdown_timeout"})
                        raise RecoveryRequired("telemetry_shutdown_timeout")
                status("stopped")
                emit("worker-stopped", recovery_required=recovery.exists())
    finally:
        for s, handler in old.items():
            signal.signal(s, handler)

def api_configuration(base, token_file, cert, key, profile_base=PROFILE_BASE):
    base = persistent_data(base)
    try:
        token = _regular_bytes(token_file, SECRET_BYTES, "api_secret", private=True).decode("ascii")
    except UnicodeError as exc:
        raise ValueError("invalid_api_secret") from exc
    if token.endswith("\r\n"):
        token = token[:-2]
    elif token.endswith("\n"):
        token = token[:-1]
    if (not 32 <= len(token) <= 256 or token != token.strip()
            or any(ord(c) < 33 or ord(c) > 126 for c in token)):
        raise ValueError("invalid_api_secret")
    if not Path(cert).exists() or not Path(key).exists():
        raise ValueError("tls_files_required")
    _regular_bytes(cert, TLS_BYTES, "tls_certificate")
    _regular_bytes(key, TLS_BYTES, "tls_private_key", private=True)
    return {"base_dir": str(base), "source_root": str(PAYLOAD),
            "profile_root": str(persistent_profiles(profile_base)), "persistent_profiles": True,
            "engine_root": "/engine/bambu_studio",
            "token": token, "host": "0.0.0.0", "port": 8099,
            "tls_certfile": str(cert), "tls_keyfile": str(key)}

def run_api(base, token_file, cert, key, profile_base=PROFILE_BASE):
    config = api_configuration(base, token_file, cert, key, profile_base)
    # Secret-bearing derived config exists only on the private container tmpfs.
    path = Path("/tmp/studio-api-config.json")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as out:
        json.dump(config, out)
    os.execv(sys.executable, [sys.executable, str(PAYLOAD / "server.py"), str(path)])

def check_worker(base):
    jc = canonical()
    value = json.loads((base / "run/container-worker.json").read_text())
    if (value.get("status") != "running" or time.time() - value["updated_at_epoch"] > 40
            or jc.process_identity(value["pid"]) != value["identity"]
            or (base / "run/container-recovery.json").exists()):
        raise ValueError("worker_not_healthy")
    emit("worker-healthy")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["api", "worker", "dispatch", "worker-check", "init-data", "init-profiles", "recover-data-layout",
        "maintenance-begin", "maintenance-end", "maintenance-status"])
    parser.add_argument("--request-id", help="Trusted installer maintenance correlation ID")
    parser.add_argument("--verified-legacy-error", action="store_true",
                        help="Host verified the exact stopped-worker metadata traceback")
    parser.add_argument("--profiles", type=Path, default=PROFILE_BASE)
    parser.add_argument("--base", type=Path, default=Path("/var/lib/ultimate-slicer"))
    parser.add_argument("--token-file", type=Path, default=Path("/run/secrets/api-token"))
    parser.add_argument("--cert", type=Path, default=Path("/run/tls/server.crt"))
    parser.add_argument("--key", type=Path, default=Path("/run/tls/server.key"))
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == "recover-data-layout":
        emit("data-layout-recovery", **recover_data_layout(args.base,
             verified_legacy_error=args.verified_legacy_error))
        return
    if args.command == "init-data":
        request_id = os.environ.get("STUDIO_BOOTSTRAP_REQUEST_ID") or None
        emit("data-ready", **initialize_data(args.base,
                                              maintenance_request_id=request_id))
        return
    if args.command == "init-profiles":
        emit("profiles-ready", **initialize_profiles(args.profiles))
        return
    if args.command.startswith("maintenance-"):
        # Validate the owned initialized data tree; do not initialize/adopt data.
        base = persistent_data(args.base)
        control = canonical().JobControl(base)
        if args.command == "maintenance-status":
            emit("maintenance-status", dispatch_blocked=control.maintenance_pending(),
                 services_stopped=False)
        else:
            operation = (control.begin_maintenance if args.command == "maintenance-begin"
                         else control.end_maintenance)
            emit(args.command, **operation(args.request_id))
        return
    configure_environment(args.base, args.profiles)
    if args.command == "api":
        run_api(args.base, args.token_file, args.cert, args.key, args.profiles)
    elif args.command == "worker":
        run_worker(args.base, profile_base=args.profiles)
    elif args.command == "dispatch":
        dispatch_child(args.base, args.base / "run/container-dispatch-result.json")
    else:
        check_worker(args.base)

if __name__ == "__main__":
    main()
