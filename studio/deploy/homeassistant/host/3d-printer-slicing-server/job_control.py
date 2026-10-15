"""Cooperative native-job cancellation. Only this supervisor signals its own children."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time

JOB_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z")
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def read_json(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _replace_json_file(source, destination):
    """Publish one already-fsynced JSON file; never repeat the enclosing job.

    Windows can deny rename while another reader/renamer holds the destination.
    Only these Windows errors get a bounded retry (nine attempts, 815 ms total
    backoff). Permanent errors still propagate; never unlink/truncate the target.
    Linux keeps the original single atomic replace without extra locking or I/O.
    """
    delays = (.005, .010, .020, .040, .080, .160, .250, .250)
    for attempt in range(len(delays) + 1):
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            if (sys.platform != "win32" or getattr(error, "winerror", None) not in {5, 32, 33}
                    or attempt == len(delays)):
                raise
            time.sleep(delays[attempt])


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as target:
            json.dump(value, target, ensure_ascii=False)
            target.write("\n")
            target.flush()
            os.fsync(target.fileno())
        _replace_json_file(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def process_identity(pid):
    """Start time and boot ID prevent trusting a stale, reused supervisor PID."""
    try:
        fields = Path(f"/proc/{int(pid)}/stat").read_text().rsplit(") ", 1)[1].split()
        if fields[0] == "Z":
            return None
        return [Path("/proc/sys/kernel/random/boot_id").read_text().strip(), fields[19]]
    except (OSError, ValueError, IndexError):
        return None


class ProcessGroupStillRunning(RuntimeError):
    """The owned group could not be proven stopped within the escalation budget."""


def live_group_members(group_id):
    """Inspect without reaping the leader, whose PID pins this private group ID."""
    members = []
    try:
        for entry in Path("/proc").iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(") ", 1)[1].split()
            except (FileNotFoundError, ProcessLookupError):
                continue  # A process exited during the snapshot.
            if int(fields[2]) == group_id and fields[0] not in {"Z", "X"}:
                members.append(int(entry.name))
    except (OSError, ValueError, IndexError) as exc:
        raise ProcessGroupStillRunning("owned_process_group_unverifiable") from exc
    return members


@contextmanager
def file_lock(path, *, nonblocking=False):
    with path.open("a+b") as handle:
        if os.name == "nt":
            # Only queue/state operations are portable; native dispatch is Linux-only.
            import msvcrt
            # Byte-range locks may extend beyond EOF; never initialize before
            # acquiring ownership, which races with another handle's first lock.
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK if nonblocking else msvcrt.LK_LOCK, 1)
            except OSError as exc:
                raise BlockingIOError(str(exc)) from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0))
            yield


class JobControl:
    def __init__(self, base):
        self.base = Path(base)
        self.jobs = self.base / "data/jobs"
        self.output = self.base / "data/output"
        self.run = self.base / "run"
        self.locks = self.run / "job-locks"
        for path in (self.jobs, self.output, self.run, self.locks):
            path.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def lock(self, job_id):
        if not JOB_ID.fullmatch(job_id):
            raise ValueError("invalid_job_id")
        # Stable lock inode: never unlink these locks during job deletion.
        with file_lock(self.locks / (job_id + ".lock")):
            yield

    def state(self, job_id):
        for status in ("cancelled", "interrupted", "slicing", "queued", "completed", "failed"):
            path = self.jobs / f"{job_id}.{status}.json"
            if path.is_file():
                return status, path, read_json(path, {})
        return "not_found", None, {}

    def request_path(self, job_id):
        return self.run / f"{job_id}-cancel.json"

    def owner_alive(self, job_id):
        owner = read_json(self.run / f"{job_id}-owner.json", {})
        identity = process_identity(owner.get("supervisor_pid", 0))
        return bool(identity and identity == owner.get("identity"))

    def cancellation(self, job_id):
        return read_json(self.request_path(job_id), {})

    def cancel(self, job_id):
        with self.lock(job_id):
            status, path, job = self.state(job_id)
            if status == "not_found":
                return {"error": "job_not_found", "http_status": 404}
            if status == "cancelled":
                return {"job_id": job_id, "status": "cancelled", "cancel_requested": True, "already_cancelled": True}
            if status in TERMINAL:
                return {"error": "job_already_terminal", "job_status": status, "http_status": 409}
            request = self.cancellation(job_id)
            if request:
                return {"job_id": job_id, "status": "cancelling", "cancel_requested": True, "already_requested": True, "requested_at": request.get("requested_at")}
            if status == "slicing" and not self.owner_alive(job_id):
                # Pre-migration or orphaned processes are never killed by guessing a PID.
                return {"error": "job_cancellation_owner_unavailable", "job_status": status, "http_status": 409}
            request = {"job_id": job_id, "requested_at": utcnow(), "reason": "user_requested"}
            atomic_json(self.request_path(job_id), request)
            if status == "queued":
                self._finish_cancelled(job_id, job, request)
                return {"job_id": job_id, "status": "cancelled", "cancel_requested": True, "requested_at": request["requested_at"]}
            return {"job_id": job_id, "status": "cancelling", "cancel_requested": True, "requested_at": request["requested_at"]}

    def cleanup_runtime(self, job_id):
        # Do not glob by prefix: IDs such as "job" and "job-child" coexist.
        removed = 0
        for suffix in ("cancel.json", "owner.json", "progress.pipe", "process.json",
                       "machine.json", "assemble.json", "materials.json", "parts", "xdg"):
            path = self.run / f"{job_id}-{suffix}"
            if path.is_symlink():
                path.unlink()
                removed += 1
            elif path.is_dir():
                shutil.rmtree(path)  # rmtree never follows contained symlinks.
                removed += 1
            elif path.exists():
                path.unlink()
                removed += 1
        return removed

    def _finish_cancelled(self, job_id, job, request):
        """Called with the job lock after the owned process group has stopped."""
        # Keep model uploads and the diagnostic log. Remove every partial print artifact.
        artifact_dir = self.output / job_id
        if artifact_dir.is_symlink():
            artifact_dir.unlink()
        elif artifact_dir.exists():
            shutil.rmtree(artifact_dir)
        self.cleanup_runtime(job_id)
        result = {"job_id": job_id, "status": "cancelled", "cancel_requested": True,
                  "requested_at": request.get("requested_at"), "finished_at": utcnow(),
                  "reason": request.get("reason", "user_requested"), "artifacts_removed": True}
        atomic_json(self.output / f"{job_id}.result.json", result)
        atomic_json(self.output / f"{job_id}.progress.json", {"job_id": job_id, "active": False, "status": "cancelled", "updated_at": result["finished_at"]})
        atomic_json(self.jobs / f"{job_id}.cancelled.json", job)
        for status in ("queued", "slicing", "completed", "failed", "interrupted"):
            (self.jobs / f"{job_id}.{status}.json").unlink(missing_ok=True)
        atomic_json(self.base / "last_job.json", result)

    def maintenance_pending(self):
        """Any marker, including malformed or dangling links, prevents dispatch."""
        return os.path.lexists(self.run / "container-maintenance.json")

    @staticmethod
    def _maintenance_id(value):
        if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
            raise ValueError("invalid_maintenance_id")
        return value

    def _maintenance_record(self):
        path = self.run / "container-maintenance.json"
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_size > 4096 or
                (os.name == "posix" and
                 (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600))):
            raise ValueError("maintenance_reconciliation_required")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                raise ValueError("maintenance_reconciliation_required")
            data = stream.read(4097)
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("maintenance_reconciliation_required")
                value[key] = item
            return value
        try:
            row = json.loads(data, object_pairs_hook=unique)
            if (type(row) is not dict or set(row) != {"schema", "request_id", "state"}
                    or type(row["schema"]) is not int or row["schema"] != 1
                    or row["state"] != "maintenance"):
                raise ValueError()
            self._maintenance_id(row["request_id"])
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise ValueError("maintenance_reconciliation_required") from None
        return row

    def _sync_run(self):
        if os.name == "posix":
            fd = os.open(self.run, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

    def begin_maintenance(self, request_id):
        """Trusted local operation, as the runtime UID; never stop a live job.

        Holding dispatcher.guard makes the no-active-job proof and durable
        dispatch barrier indivisible to every cooperating dispatcher.
        Queued jobs remain intact. API uploads and queue submissions remain
        accepted; they cannot start while the barrier exists.
        """
        request_id = self._maintenance_id(request_id)
        with file_lock(self.run / "dispatcher.guard", nonblocking=True):
            if any(self.jobs.glob("*.slicing.json")):
                raise ValueError("active_job_requires_recovery")
            if os.path.lexists(self.run / "container-recovery.json"):
                raise ValueError("worker_recovery_required")
            if self.maintenance_pending():
                row = self._maintenance_record()
                if row["request_id"] != request_id:
                    raise ValueError("maintenance_owned_by_other_request")
            else:
                row = {"schema": 1, "request_id": request_id, "state": "maintenance"}
                atomic_json(self.run / "container-maintenance.json", row)
            self._sync_run()
            if self._maintenance_record() != row:
                raise ValueError("maintenance_reconciliation_required")
            return {"state": "maintenance", "request_id": request_id,
                    "dispatch_blocked": True, "services_stopped": False}

    def end_maintenance(self, request_id):
        """Explicit trusted resume after host health/mount checks, never automatic."""
        request_id = self._maintenance_id(request_id)
        with file_lock(self.run / "dispatcher.guard", nonblocking=True):
            if not self.maintenance_pending():
                # A lost reply is not proof that this request previously resumed.
                raise ValueError("maintenance_not_present")
            row = self._maintenance_record()
            if row["request_id"] != request_id:
                raise ValueError("maintenance_owned_by_other_request")
            if (any(self.jobs.glob("*.slicing.json")) or
                    os.path.lexists(self.run / "container-recovery.json")):
                raise ValueError("worker_recovery_required")
            (self.run / "container-maintenance.json").unlink()
            self._sync_run()
            return {"state": "resumed", "request_id": request_id,
                    "dispatch_blocked": False}

    def _claim(self):
        for queued in sorted(self.jobs.glob("*.queued.json")):
            job_id = queued.name.removesuffix(".queued.json")
            if not JOB_ID.fullmatch(job_id):
                continue
            with self.lock(job_id):
                if not queued.is_file():
                    continue
                job = read_json(queued)
                if not isinstance(job, dict):
                    atomic_json(self.output / f"{job_id}.result.json", {"job_id": job_id, "status": "failed", "error": "invalid_job_json"})
                    os.replace(queued, self.jobs / f"{job_id}.failed.json")
                    continue
                if job.get("manual_release") is True and not str(job.get("released_at") or "").strip():
                    continue
                slicing = self.jobs / f"{job_id}.slicing.json"
                atomic_json(self.run / f"{job_id}-owner.json", {"supervisor_pid": os.getpid(), "identity": process_identity(os.getpid())})
                os.replace(queued, slicing)
                return job_id, slicing, job
        return None

    def dispatch(self, script, *, term_timeout=5.0, kill_timeout=2.0, poll_interval=.1, before_start=None):
        """Run one job in a private session. No PID is accepted from an API request."""
        if os.name != "posix":
            raise RuntimeError("Native dispatch requires Linux process groups")
        with file_lock(self.run / "dispatcher.guard", nonblocking=True):
            if self.maintenance_pending():
                return {"status": "maintenance"}
            # Never overlap an unmanaged/abandoned slicing job after migration or restart.
            if any(self.jobs.glob("*.slicing.json")):
                return {"status": "blocked", "error": "existing_active_job_requires_recovery"}
            claimed = self._claim()
            if claimed is None:
                return {"status": "idle"}
            job_id, slicing, job = claimed
            env = {**os.environ, "STUDIO_DISPATCH_MANAGED": "1", "STUDIO_JOB_PATH": str(slicing), "STUDIO_WORKER_BASE": str(self.base)}
            process = None
            stop_attempted = False
            interrupted = []
            old_handlers = {}
            if __import__("threading").current_thread() is __import__("threading").main_thread():
                for sig in (signal.SIGTERM, signal.SIGINT):
                    old_handlers[sig] = signal.signal(sig, lambda signum, _frame: interrupted.append(signum))
            try:
                with self.lock(job_id):
                    # Optional container handshake runs after signal handlers exist.
                    # A denied start uses the same cancellation/cleanup contract.
                    if before_start is not None and before_start() is False:
                        interrupted.append(signal.SIGTERM)
                    if interrupted and not self.cancellation(job_id):
                        atomic_json(self.request_path(job_id), {"requested_at": utcnow(), "reason": "worker_shutdown"})
                    if not self.cancellation(job_id):
                        process = subprocess.Popen(["/bin/sh", str(script)], env=env, start_new_session=True)
                if process is not None:
                    while True:
                        if interrupted or self.cancellation(job_id):
                            if interrupted:
                                with self.lock(job_id):
                                    if not self.cancellation(job_id):
                                        atomic_json(self.request_path(job_id), {"requested_at": utcnow(), "reason": "worker_shutdown"})
                            stop_attempted = True
                            self._stop_group(process, term_timeout, kill_timeout)
                            break
                        if os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                            # Reap only after cleaning the whole owned session; this also
                            # prevents a shell that exits early from leaking grandchildren.
                            stop_attempted = True
                            self._stop_group(process, term_timeout, kill_timeout)
                            break
                        time.sleep(poll_interval)
                with self.lock(job_id):
                    request = self.cancellation(job_id)
                    if request:
                        self._finish_cancelled(job_id, job, request)
                        return {"job_id": job_id, "status": "cancelled"}
                    state, _, _ = self.state(job_id)
                    if state == "slicing":
                        result = read_json(self.output / f"{job_id}.result.json", {})
                        state = result.get("status") if isinstance(result, dict) and result.get("job_id") == job_id else None
                        if state not in {"completed", "failed"}:
                            state = "failed"
                            atomic_json(self.output / f"{job_id}.result.json", {"job_id": job_id, "status": state, "error": "dispatcher_interrupted", "exit_code": process.returncode if process else None})
                        os.replace(slicing, self.jobs / f"{job_id}.{state}.json")
                    (self.run / f"{job_id}-owner.json").unlink(missing_ok=True)
                    return {"job_id": job_id, "status": state}
            except ProcessGroupStillRunning as exc:
                # Keep the slicing marker, all artifacts, and the cancellation request.
                # A following dispatcher must stay blocked until explicit recovery.
                with self.lock(job_id):
                    if not self.cancellation(job_id):
                        atomic_json(self.request_path(job_id), {"requested_at": utcnow(), "reason": "worker_group_shutdown_failed"})
                    atomic_json(self.output / f"{job_id}.progress.json", {
                        "job_id": job_id, "active": True, "status": "cancelling",
                        "error": str(exc), "requires_recovery": True, "updated_at": utcnow(),
                    })
                return {"job_id": job_id, "status": "cancelling", "error": str(exc), "requires_recovery": True}
            finally:
                # Exceptions must not leak the native process into another queued job.
                try:
                    if process is not None and not stop_attempted:
                        self._stop_group(process, term_timeout, kill_timeout)
                finally:
                    for sig, handler in old_handlers.items():
                        signal.signal(sig, handler)

    @staticmethod
    def _stop_group(process, term_timeout, kill_timeout):
        # Popen created this process/session here. Never inspect or kill unrelated PIDs.
        if process.returncode is not None:
            raise ProcessGroupStillRunning("owned_process_group_leader_already_reaped")
        # Retain the unreaped leader through both signals and group verification.
        # Waiting only for this leader would permit still-running grandchildren.
        for sig, timeout in ((signal.SIGTERM, term_timeout), (signal.SIGKILL, kill_timeout)):
            try:
                os.killpg(process.pid, sig)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + timeout
            while True:
                if not live_group_members(process.pid):
                    try:
                        process.wait(timeout=max(.001, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired as exc:
                        raise ProcessGroupStillRunning("owned_process_group_leader_unreaped") from exc
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(.05, remaining))
        raise ProcessGroupStillRunning("owned_process_group_still_running")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dispatch", choices=["dispatch"])
    parser.add_argument("--base", type=Path, required=True)
    args = parser.parse_args()
    source_root = Path(os.environ.get("STUDIO_WORKER_SOURCE_ROOT") or args.base)
    try:
        result = JobControl(args.base).dispatch(source_root / "dispatch-job.sh")
    except BlockingIOError:
        result = {"status": "busy"}
    if result.get("job_id"):
        subprocess.run(["/bin/sh", str(source_root / "refresh-state.sh")], timeout=30, check=False)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
