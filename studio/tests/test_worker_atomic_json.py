"""Exercise the actual worker writer with temporary data, not production jobs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import errno
import importlib.util
import json
from pathlib import Path
import sys
import threading
from unittest.mock import patch

import pytest

WORKER = Path(__file__).resolve().parents[1] / "deploy/homeassistant/host/3d-printer-slicing-server"
spec = importlib.util.spec_from_file_location("atomic_json_worker_under_test", WORKER / "job_control.py")
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def windows_error(code):
    error = PermissionError(errno.EACCES, "synthetic write contention")
    error.winerror = code
    return error


@pytest.mark.parametrize("code", [5, 32, 33])
@pytest.mark.parametrize("failures", [1, 3, 8])
def test_transient_windows_conflict_reuses_fsynced_temp_and_publishes_once(tmp_path, code, failures):
    path = tmp_path / "last_job.json"
    old = b'{"job_id":"old"}\n'
    path.write_bytes(old)
    value = {"job_id":"new", "status":"cancelled", "label":"Prüfung"}
    replace = worker.os.replace
    source_names = []
    def contention(source, destination):
        source_names.append(str(source))
        assert path.read_bytes() == old
        assert Path(source).parent == path.parent
        assert json.loads(Path(source).read_text(encoding="utf-8")) == value
        if len(source_names) <= failures:
            raise windows_error(code)
        return replace(source, destination)
    with patch.object(worker.sys, "platform", "win32"), \
         patch.object(worker.os, "replace", side_effect=contention) as replaced, \
         patch.object(worker.time, "sleep") as waited, \
         patch.object(worker.json, "dump", wraps=worker.json.dump) as dumped, \
         patch.object(worker.os, "fsync", wraps=worker.os.fsync) as synced:
        worker.atomic_json(path, value)
    assert replaced.call_count == failures + 1
    assert waited.call_count == failures
    assert sum(call.args[0] for call in waited.call_args_list) <= .816
    assert dumped.call_count == synced.call_count == 1
    assert len(set(source_names)) == 1
    assert json.loads(path.read_text(encoding="utf-8")) == value
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("code", [5, 32, 33])
def test_persistent_denial_is_bounded_preserves_original_and_propagates(tmp_path, code):
    path = tmp_path / "last_job.json"
    old = b'{"job_id":"keep"}\n'
    path.write_bytes(old)
    error = windows_error(code)
    with patch.object(worker.sys, "platform", "win32"), \
         patch.object(worker.os, "replace", side_effect=error) as replace, \
         patch.object(worker.time, "sleep") as sleep:
        with pytest.raises(PermissionError) as caught:
            worker.atomic_json(path, {"job_id":"new"})
    assert caught.value is error
    assert replace.call_count == 9 and sleep.call_count == 8
    assert sum(call.args[0] for call in sleep.call_args_list) == pytest.approx(.815)
    assert path.read_bytes() == old and not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("platform,code", [("linux",5),("darwin",32),("win32",2),("win32",19),("win32",112),("win32",None)])
def test_other_errors_and_other_platforms_are_never_retried(tmp_path, platform, code):
    path = tmp_path / "last_job.json"
    path.write_bytes(b"old")
    error = windows_error(code)
    with patch.object(worker.sys,"platform",platform), \
         patch.object(worker.os,"replace",side_effect=error) as replace, \
         patch.object(worker.time,"sleep") as sleep:
        with pytest.raises(PermissionError) as caught:
            worker.atomic_json(path, {"new":True})
    assert caught.value is error
    assert replace.call_count == 1 and not sleep.called
    assert path.read_bytes() == b"old" and not list(tmp_path.glob("*.tmp"))


def test_serialization_failure_never_retries_or_replaces(tmp_path):
    path = tmp_path / "last_job.json"
    path.write_bytes(b"old")
    with patch.object(worker.os,"replace") as replace, patch.object(worker.time,"sleep") as sleep:
        with pytest.raises(TypeError):worker.atomic_json(path, {"bad":object()})
    assert not replace.called and not sleep.called
    assert path.read_bytes() == b"old" and not list(tmp_path.glob("*.tmp"))


def test_fsync_failure_never_retries_or_publishes(tmp_path):
    path = tmp_path / "last_job.json"
    path.write_bytes(b"old")
    with patch.object(worker.os,"fsync",side_effect=OSError(errno.ENOSPC,"test disk full")), \
         patch.object(worker.os,"replace") as replace, patch.object(worker.time,"sleep") as sleep:
        with pytest.raises(OSError):worker.atomic_json(path, {"new":True})
    assert not replace.called and not sleep.called
    assert path.read_bytes() == b"old" and not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("platform",["linux","win32"])
def test_uncontended_publish_is_one_replace_with_no_backoff(tmp_path, platform):
    path = tmp_path / "last_job.json"
    with patch.object(worker.sys,"platform",platform), \
         patch.object(worker.os,"replace",wraps=worker.os.replace) as replace, \
         patch.object(worker.time,"sleep") as sleep:
        worker.atomic_json(path, {"new":True})
    assert replace.call_count == 1 and not sleep.called
    assert json.loads(path.read_text()) == {"new":True}


@pytest.mark.parametrize("round_number",range(5))
def test_concurrent_cancelled_jobs_keep_all_terminal_states(tmp_path, round_number):
    control = worker.JobControl(tmp_path)
    last = tmp_path / "last_job.json"
    last.write_text('{"job_id":"initial"}')
    ids = [f"atomic-{round_number}-{i}" for i in range(30)]
    for job_id in ids:
        (control.jobs / f"{job_id}.queued.json").write_text(json.dumps({"job_id":job_id,"manual_release":True}))
    gate = threading.Barrier(8)
    def cancel_batch(index):
        gate.wait(timeout=5)
        for job_id in ids[index::6]:
            assert control.cancel(job_id)["status"] == "cancelled"
    def polling():
        gate.wait(timeout=5)
        for _ in range(120):
            # Readers assert parseability on every successful open. Windows can
            # legitimately reject a concurrent open, but never return torn JSON.
            try:
                value = json.loads(last.read_text(encoding="utf-8"))
            except PermissionError:
                continue
            assert value["job_id"] in {*ids,"initial"}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures=[pool.submit(cancel_batch,i) for i in range(6)] + [pool.submit(polling) for _ in range(2)]
        for future in futures:future.result(timeout=15)
    assert json.loads(last.read_text())["job_id"] in ids
    assert not list(control.jobs.glob("*.queued.json"))
    for job_id in ids:
        assert control.state(job_id)[0] == "cancelled"
        assert worker.read_json(control.output / f"{job_id}.result.json")["status"] == "cancelled"
    assert not list(tmp_path.rglob("*.tmp"))
