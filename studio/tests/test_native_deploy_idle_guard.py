"""Fail-closed deployment checks, only temporary roots and command doubles."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import os
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_guard_fixture", ROOT / "tests/test_native_deploy_supervisor.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
deployment = fixture.deployment


def change_supervisor(target):
    old = b"VALUE = 1\n"
    (target / "job_control.py").write_bytes(old)
    return old


def unchanged(target, old, result, calls):
    assert result.returncode != 0, result.stdout + result.stderr
    assert (target / "job_control.py").read_bytes() == old
    assert not (target / "backups").exists()
    assert not any(c["args"][0] == "restart" for c in calls)
    assert "Deployment/Verifikation erfolgreich." not in result.stdout


@pytest.mark.parametrize("problem", ["missing", "file", "symlink", "data_symlink"])
def test_unknown_or_linked_job_directory_is_not_empty(deployment, problem):
    _, target, _, run = deployment
    old = change_supervisor(target)
    jobs = target / "data/jobs"
    jobs.rmdir()
    if problem == "file": jobs.write_text("not a queue directory")
    elif problem == "symlink":
        outside = target.parent / "outside-jobs"
        outside.mkdir()
        jobs.symlink_to(outside, target_is_directory=True)
    elif problem == "data_symlink":
        (target / "data").rmdir()
        outside = target.parent / "outside-data"
        (outside / "jobs").mkdir(parents=True)
        (target / "data").symlink_to(outside, target_is_directory=True)
    result, calls = run()
    unchanged(target, old, result, calls)
    assert not calls


@pytest.mark.parametrize("kind", ["file", "dangling_link", "directory"])
def test_any_dispatcher_lock_representation_blocks_update(deployment, kind):
    _, target, _, run = deployment
    old = change_supervisor(target)
    lock = target / "run/dispatcher.lock"
    lock.parent.mkdir()
    if kind == "file": lock.write_text("locked")
    elif kind == "directory": lock.mkdir()
    else: lock.symlink_to(target / "not-existing-lock")
    result, calls = run()
    unchanged(target, old, result, calls)
    assert not calls


@pytest.mark.parametrize("suffix", ["queued", "slicing"])
@pytest.mark.parametrize("kind", ["directory", "dangling_link"])
def test_nonregular_job_marker_is_not_treated_as_idle(deployment, suffix, kind):
    _, target, _, run = deployment
    old = change_supervisor(target)
    marker = target / "data/jobs" / ("synthetic." + suffix + ".json")
    if kind == "directory": marker.mkdir()
    else: marker.symlink_to(target / "missing-job")
    result, calls = run()
    unchanged(target, old, result, calls)
    assert not calls


@pytest.mark.parametrize("phase", ["before_stop", "after_stop"])
def test_find_failure_cannot_become_zero_jobs(deployment, phase):
    _, target, _, run = deployment
    old = change_supervisor(target)
    commands = target.parent / "doubles"
    # The only delegated find calls remain inside the temporary fixture root.
    real_find = shutil.which("find")
    shim = commands / "find"
    shim.write_text(f"#!{sys.executable} -S\n" +
        "import json,os,subprocess,sys\nfrom pathlib import Path\n" +
        "target=Path(os.environ['FIXTURE_TARGET'])\n" +
        "log=Path(os.environ['FIXTURE_OPERATIONS'])\n" +
        "calls=[json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []\n" +
        "stopped=any(c['args'][0]=='stop' for c in calls)\n" +
        f"fail={phase!r}=='before_stop' or stopped\n" +
        "if str(target/'data/jobs') in sys.argv and fail: sys.exit(13)\n" +
        f"sys.exit(subprocess.call([{real_find!r},*sys.argv[1:]]))\n")
    shim.chmod(0o755)
    result, calls = run()
    unchanged(target, old, result, calls)
    if phase == "before_stop": assert not calls
    else: assert any(c["args"][0] == "start" for c in calls)


@pytest.mark.parametrize("timer", ["dispatch", "refresh"])
def test_timer_stop_failure_aborts_before_backup_or_copy(deployment, timer):
    _, target, _, run = deployment
    old = change_supervisor(target)
    shim = target.parent / "doubles/systemctl"
    text = shim.read_text()
    anchor = "    if args[0]=='is-active': print('active')"
    assert text.count(anchor) == 1
    text = text.replace(anchor, anchor +
        f"\n    if args[0]=='stop' and args[-1]=='3d-printer-slicing-{timer}.timer':sys.exit(1)")
    shim.write_text(text)
    result, calls = run()
    unchanged(target, old, result, calls)
    assert any(c["args"][0] == "start" for c in calls)


def test_unchanged_package_does_not_invent_a_queue_check(deployment):
    _, _, _, run = deployment
    result, calls = run()
    assert result.returncode == 0 and not calls
    assert "Aktive/wartende Jobs vor Änderung: 0/0." not in result.stdout


@pytest.mark.parametrize("state", ["", "failed", "activating", "deactivating", "unknown"])
def test_unknown_or_transitional_timer_state_blocks_before_stop(deployment, state):
    _, target, _, run = deployment
    old = change_supervisor(target)
    shim = target.parent / "doubles/systemctl"
    text = shim.read_text()
    anchor = "    if args[0]=='is-active': print('active')"
    assert text.count(anchor) == 1
    shim.write_text(text.replace(anchor, f"    if args[0]=='is-active': print({state!r})"))
    result, calls = run()
    unchanged(target, old, result, calls)
    assert calls and all(c["args"][0] == "is-active" for c in calls)
