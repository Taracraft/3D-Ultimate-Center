"""Synthetic container lifecycle acceptance. No engine, real queue or API starts."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
from container_runtime import require_isolation, supervise, start_permit, RecoveryRequired

ROOT = Path(__file__).resolve().parent

def canonical():
    spec = importlib.util.spec_from_file_location("probe_job_control", ROOT / "payload/job_control.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def emit(value):
    print(json.dumps(value, sort_keys=True), flush=True)

def run():
    evidence = require_isolation()
    jc = canonical()
    stop = threading.Event()
    old = {sig: signal.signal(sig, lambda *_: stop.set()) for sig in (signal.SIGTERM, signal.SIGINT)}
    # Only a newly created temporary tree is writable. No caller-selected queue.
    with tempfile.TemporaryDirectory(prefix="studio-container-probe-") as directory:
        base = Path(directory)
        control = jc.JobControl(base)
        job_id = "synthetic-probe"
        jc.atomic_json(control.jobs / (job_id + ".queued.json"), {"job_id": job_id})
        artifact = control.output / job_id
        artifact.mkdir()
        (artifact / "partial.gcode").write_text("synthetic, never printable")
        script = base / "dispatch-job.sh"
        script.write_text('exec "' + sys.executable + '" "' + str(Path(__file__).resolve()) + '" fixture\n')
        result_file = base / "result.json"
        stdout_path = base / "supervisor.log"
        stderr_path = base / "supervisor.err"
        errors = []
        wrapper = []
        command = [sys.executable, str(Path(__file__).resolve()), "supervisor", str(base)]
        def work():
            try:
                with stdout_path.open("w") as out, stderr_path.open("w") as err:
                    wrapper.append(supervise(command, stop=stop, stdout=out, stderr=err,
                                             shutdown_timeout=12, handshake=True))
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        deadline = time.monotonic() + 12
        ready = base / "run/fixture.json"
        try:
            while not ready.exists():
                if errors or not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError("synthetic_start_failed")
                time.sleep(.05)
            fixture = json.loads(ready.read_text())
            owner = json.loads((control.run / (job_id + "-owner.json")).read_text())
            if not control.owner_alive(job_id):
                raise RuntimeError("owner_not_visible")
            # An overlapping dispatcher must not start another process.
            try:
                control.dispatch(script)
            except BlockingIOError:
                pass
            else:
                raise RuntimeError("duplicate_dispatcher_not_rejected")
            emit({"event": "ready", "owner": owner, "fixture": fixture,
                  "isolation": evidence, "duplicate_dispatcher_rejected": True})
            # Host acceptance harness sends SIGTERM only after observing from anchor.
            deadline = time.monotonic() + 30
            while not stop.wait(.05):
                if time.monotonic() >= deadline:
                    raise RuntimeError("external_shutdown_signal_missing")
            thread.join(15)
            if thread.is_alive() or errors:
                raise RuntimeError("supervisor_not_cleanly_stopped")
            result = json.loads(result_file.read_text())
            if result.get("status") != "cancelled":
                raise RuntimeError("synthetic_job_not_cancelled")
            terminal = json.loads((control.output / (job_id + ".result.json")).read_text())
            if terminal.get("reason") != "worker_shutdown" or artifact.exists():
                raise RuntimeError("shutdown_cleanup_failed")
            for pid in fixture.values():
                if jc.process_identity(pid) is not None:
                    raise RuntimeError("synthetic_descendant_still_alive")
            if control.owner_alive(job_id) or list(control.jobs.glob("*.slicing.json")):
                raise RuntimeError("stale_owner_or_slicing_marker")
            # An abandoned marker must prevent any next job after restart.
            jc.atomic_json(control.jobs / "abandoned.slicing.json", {})
            blocked = control.dispatch(script)
            if blocked.get("error") != "existing_active_job_requires_recovery":
                raise RuntimeError("orphan_not_blocked")
            emit({"event": "passed", "synthetic_only": True, "shutdown_reason": terminal["reason"],
                  "descendants_stopped": True, "partial_artifacts_removed": True,
                  "orphan_restart_blocked": True, "wrapper": wrapper[0],
                  "container_deploy_ready": False})
        finally:
            stop.set()
            thread.join(15)
            for sig, handler in old.items():
                signal.signal(sig, handler)
            if thread.is_alive() or errors:
                # Do not claim cleanup or run another job; Docker harness removes
                # its test container and reports this run as failed.
                raise RuntimeError("probe_requires_container_recovery")

def startup_checks():
    """Deterministic early stop, missing readiness and invalid permit tests."""
    require_isolation()
    jc = canonical()
    reports = []
    for scenario in ("early-stop", "missing-ready", "premature-exit"):
        with tempfile.TemporaryDirectory(prefix="studio-start-probe-") as directory:
            base = Path(directory)
            control = jc.JobControl(base)
            jc.atomic_json(control.jobs / "early.queued.json", {"job_id": "early"})
            # This synthetic script must never run in any startup-failure case.
            (base / "dispatch-job.sh").write_text('echo unexpected > "' + str(base / "unexpected") + '"\n')
            stop = threading.Event()
            env = {**os.environ, "STUDIO_SYNTHETIC_START_SCENARIO": scenario}
            timer = threading.Timer(.1, stop.set) if scenario == "early-stop" else None
            if timer:
                timer.start()
            error = None
            result = None
            try:
                with (base / "stdout").open("w") as out, (base / "stderr").open("w") as err:
                    result = supervise([sys.executable, str(Path(__file__).resolve()), "startup-child", str(base)],
                                       stop=stop, stdout=out, stderr=err, env=env,
                                       handshake=True, startup_timeout=.7, shutdown_timeout=3)
            except RecoveryRequired as exc:
                error = exc
                # This mode is a synthetic sleeper, never a job supervisor.
                # Let it exit itself and reap it; do not kill arbitrary PIDs.
                if exc.supervisor is not None:
                    exc.supervisor.wait(timeout=3)
            finally:
                if timer:
                    timer.cancel()
                    timer.join()
            if (base / "unexpected").exists():
                raise RuntimeError("startup_failure_executed_dispatcher")
            if scenario == "early-stop":
                if error or result["status"] != "stopped":
                    raise RuntimeError("early_stop_failed")
                terminal = json.loads((control.output / "early.result.json").read_text())
                if terminal.get("reason") != "worker_shutdown" or control.state("early")[0] != "cancelled":
                    raise RuntimeError("early_stop_not_persisted")
                if list(control.jobs.glob("*.slicing.json")):
                    raise RuntimeError("early_stop_left_active_marker")
            else:
                expected = "supervisor_startup_timeout" if scenario == "missing-ready" else "supervisor_exited_before_ready"
                if error is None or str(error) != expected:
                    raise RuntimeError("startup_failure_not_reported:" + str(error))
                if control.state("early")[0] != "queued":
                    raise RuntimeError("startup_failure_changed_queue")
            reports.append({"scenario": scenario, "passed": True, "dispatcher_not_started": True})
    emit({"event": "startup-checks-passed", "checks": reports, "synthetic_only": True,
          "container_deploy_ready": False})

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if mode == "fixture":
        base = Path(os.environ["STUDIO_WORKER_BASE"])
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child = subprocess.Popen([sys.executable, "-c",
                                  "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(120)"])
        canonical().atomic_json(base / "run/fixture.json", {"parent": os.getpid(), "child": child.pid})
        while True:
            time.sleep(1)
    elif mode == "supervisor":
        base = Path(sys.argv[2])
        jc = canonical()
        result = jc.JobControl(base).dispatch(base / "dispatch-job.sh", term_timeout=.4, kill_timeout=2, before_start=start_permit)
        jc.atomic_json(base / "result.json", result)
    elif mode == "startup-child":
        scenario = os.environ["STUDIO_SYNTHETIC_START_SCENARIO"]
        if scenario == "missing-ready":
            time.sleep(1.2)
        elif scenario == "premature-exit":
            return
        elif scenario == "early-stop":
            time.sleep(.3)  # Parent stop is intentionally earlier than readiness.
            base = Path(sys.argv[2])
            jc = canonical()
            result = jc.JobControl(base).dispatch(base / "dispatch-job.sh", before_start=start_permit)
            jc.atomic_json(base / "result.json", result)
        else:
            raise SystemExit("invalid synthetic scenario")
    elif mode == "startup-checks":
        startup_checks()
    elif mode == "probe":
        run()
    else:
        raise SystemExit("unsupported probe mode")

if __name__ == "__main__":
    main()
