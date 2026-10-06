"""Run the real deploy script only against synthetic roots and command doubles.

Never invoke host services, network clients, slicers or printer commands. The
production root guard is retained. Runtime tests therefore require Linux/root;
the source-contract tests run on Windows as well.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCRIPT = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server/deploy-native-slicer.sh"
SCRIPT = Path(os.environ.get("NATIVE_DEPLOY_SOURCE", str(DEFAULT_SCRIPT)))
LINUX_ROOT = sys.platform == "linux" and getattr(os, "geteuid", lambda: -1)() == 0
RUNTIME = ["bambu_lab_h2s_04.json", "server.py", "job_control.py", "dispatch-job.sh",
           "progress-pipe-reader.py", "refresh-state.sh", "append-slicing-journal.sh"]
PROFILES = ["profiles/printers/bambu_lab_a1_04.json", "profiles/printers/bambu_lab_h2s_04.json"]
UNITS = ["3d-printer-slicing-server.service", "3d-printer-slicing-dispatch.service",
         "3d-printer-slicing-dispatch.timer", "3d-printer-slicing-refresh.service",
         "3d-printer-slicing-refresh.timer"]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_profile_files_are_owned_by_install_backup_and_rollback_loops():
    script = SCRIPT.read_text(encoding="utf-8")
    entries = re.search(r"PROFILE_FILES=\((.*?)\)", script, re.S).group(1).split()
    assert entries == PROFILES
    assert script.count('for file in "${PROFILE_FILES[@]}"; do') >= 4
    assert 'install -m 0644 "$SOURCE_DIR/$file"' in script


def test_supervisor_is_owned_by_install_backup_and_rollback_loops():
    script = SCRIPT.read_text(encoding="utf-8")
    entries = re.search(r"RUNTIME_FILES=\((.*?)\)", script, re.S).group(1).split()
    assert entries.count("job_control.py") == 1
    assert script.count('for file in "${RUNTIME_FILES[@]}"; do') >= 4


def test_supervisor_is_syntax_checked_before_any_deployment():
    script = SCRIPT.read_text(encoding="utf-8")
    check = '"$SOURCE_DIR/job_control.py"'
    assert check in script
    assert script.index(check) < script.index('say "[4/8]')


def test_supervisor_change_requires_reload_of_the_worker_process():
    script = SCRIPT.read_text(encoding="utf-8")
    change_detection = script.split('say "[4/8] Änderungen ermitteln"', 1)[1].split('for unit in', 1)[0]
    assert '[ "$file" = "job_control.py" ]' in change_detection
    assert "SERVER_RESTART_NEEDED=1" in change_detection


def test_source_dependency_check_and_two_live_hash_checks_are_mandatory():
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'if ! verify_dependencies source; then' in script
    assert script.count('if ! verify_live_hashes; then') == 2
    main = script.split('say "[7/8] Dateien atomar installieren"', 1)[1]
    assert main.index('if ! verify_live_hashes; then') < main.index('systemctl restart ')
    assert main.rindex('if ! verify_live_hashes; then') > main.index('runtime_summary == true')


@pytest.fixture
def deployment(tmp_path):
    if not LINUX_ROOT:
        pytest.skip("Isolated deployment lifecycle requires Linux/root; never use real host services")
    for command in ["bash", "jq", "install", "sha256sum", "python3"]:
        if not shutil.which(command):
            pytest.fail(f"Required isolated-test program missing: {command}")
    source, target, units, doubles = [tmp_path / name for name in ["source", "target", "units", "doubles"]]
    for path in [source, target / "data/jobs", units, doubles, source / "systemd",
                 source / "profiles/printers", target / "profiles/printers"]:
        path.mkdir(parents=True, exist_ok=True)
    current = {}
    for name in RUNTIME:
        data = b"VALUE = 2\n" if name.endswith(".py") else b"{}\n" if name.endswith(".json") else b"#!/bin/sh\nexit 0\n"
        (source / name).write_bytes(data)
        current[name] = data
        (target / name).write_bytes(data)
    for name in PROFILES:
        data = ('{"profile":"' + Path(name).stem + '"}\n').encode()
        (source / name).write_bytes(data)
        (target / name).write_bytes(data)
        current[name] = data
    for name in UNITS:
        data = b"[Unit]\nDescription=Synthetic deployment fixture\n"
        (source / "systemd" / name).write_bytes(data)
        (units / name).write_bytes(data)
    dependency = b"PINNED_DEPENDENCY = True\n"
    (target / "existing_dependency.py").write_bytes(dependency)
    (target / "config.json").write_text('{"token":""}', encoding="utf-8")
    (source / "SHA256SUMS").write_text("".join(
        f"{sha((source / name).read_bytes())}  {name}\n"
        for name in [n for n in RUNTIME if n != "job_control.py"] + PROFILES + ["systemd/" + n for n in UNITS]
    ), encoding="utf-8")
    (source / "DEPENDENCY-SHA256SUMS").write_text(
        f"{sha(dependency)}  existing_dependency.py\n{sha(current['job_control.py'])}  job_control.py\n", encoding="utf-8")
    original = SCRIPT.read_text(encoding="utf-8")
    target_line = 'TARGET_BASE="/var/lib/homeassistant/3d-printer-slicing-server"'
    units_line = 'UNIT_DIR="/etc/systemd/system"'
    assert original.count(target_line) == original.count(units_line) == 1
    # Only the two destination constants are rebound to independent test roots.
    # Source logic, root checks, hash checks, backups and rollback are unchanged.
    rebound = original.replace(target_line, f'TARGET_BASE="{target}"').replace(units_line, f'UNIT_DIR="{units}"')
    actual = source / "deploy-native-slicer.sh"
    actual.write_text(rebound, encoding="utf-8")
    assert 'TARGET_BASE="/var/lib/' not in rebound and 'UNIT_DIR="/etc/' not in rebound
    operations = tmp_path / "operations.jsonl"
    shim = r'''import hashlib,json,os,subprocess,sys
from pathlib import Path
name=Path(sys.argv[0]).name
args=sys.argv[1:]
target=Path(os.environ['FIXTURE_TARGET'])
log=Path(os.environ['FIXTURE_OPERATIONS'])
if name == 'systemctl':
    helper=target/'job_control.py'
    record={'args':args, 'helper_sha256':hashlib.sha256(helper.read_bytes()).hexdigest() if helper.is_file() else None}
    with log.open('a') as f:f.write(json.dumps(record)+'\n')
    if args[0]=='is-active': print('active')
    if args[0]=='restart' and os.environ.get('FAIL_RESTART_ONCE')=='1':
        marker=target/'restart-failed-once'
        if not marker.exists(): marker.touch();sys.exit(1)
elif name == 'curl':
    url=args[-1]
    if url.endswith('/info'):print(json.dumps({'version':'0.1.0-alpha5','api_version':2,'status':'ready'}))
    elif url.endswith('/capabilities'):
        if os.environ.get('CORRUPT_AT_HEALTH')=='1':
            with (target/'job_control.py').open('ab') as f:f.write(b'# mutated during health\n')
        print(json.dumps({'live_progress':True,'progress_source':'bambu_cli_pipe','progress_history':True,'progress_eta':True,'job_detail':True,'engine_result':True,'runtime_summary':True}))
    else:sys.exit(97)
elif name == 'install':
    result=subprocess.run([os.environ['REAL_INSTALL'],*args],check=False)
    if result.returncode:sys.exit(result.returncode)
    if os.environ.get('CORRUPT_INSTALL')=='1' and Path(args[-1]).name.startswith('.v6-new-job_control.py.'):
        with Path(args[-1]).open('ab') as f:f.write(b'# corrupted copy\n')
else:sys.exit(98)
'''
    for command in ["systemctl", "curl", "install"]:
        path = doubles / command
        path.write_text(f"#!{sys.executable} -S\n" + shim, encoding="utf-8")
        path.chmod(0o755)
    env = {**os.environ, "PATH": str(doubles) + os.pathsep + os.environ["PATH"],
           "FIXTURE_TARGET": str(target), "FIXTURE_OPERATIONS": str(operations),
           "REAL_INSTALL": shutil.which("install"), "V6_KEEP_SHELL_OPEN": "0"}
    for command in ["systemctl", "curl", "install"]:
        assert Path(shutil.which(command, path=env["PATH"])) == doubles / command
    def run(**options):
        process = subprocess.Popen([shutil.which("bash"), str(actual)], cwd=source,
                                   env={**env, **options}, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=40)
        except subprocess.TimeoutExpired:
            # Terminate only the process group created for this isolated test.
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate(timeout=5)
            pytest.fail("Isolated deploy fixture exceeded its deadline: " + stdout[-2500:] + stderr[-1000:])
        result = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        calls = [json.loads(line) for line in operations.read_text().splitlines()] if operations.exists() else []
        return result, calls
    return source, target, units, run


def test_missing_supervisor_is_installed_and_verified_before_restart(deployment):
    source, target, _, run = deployment
    (target / "job_control.py").unlink()
    result, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "job_control.py").read_bytes() == (source / "job_control.py").read_bytes()
    restarts = [c for c in calls if c["args"][0] == "restart"]
    assert len(restarts) == 1 and restarts[0]["helper_sha256"] == sha((source / "job_control.py").read_bytes())
    backup = next((target / "backups").iterdir())
    assert "runtime/job_control.py" in (backup / "MISSING-BEFORE.txt").read_text()


def test_supervisor_only_change_restarts_and_backs_up_old_bytes(deployment):
    source, target, _, run = deployment
    old = b"VALUE = 1\n"
    (target / "job_control.py").write_bytes(old)
    result, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "job_control.py").read_bytes() == (source / "job_control.py").read_bytes()
    assert len([c for c in calls if c["args"][0] == "restart"]) == 1
    assert next((target / "backups").glob("*/runtime/job_control.py")).read_bytes() == old


@pytest.mark.parametrize("problem", ["missing", "checksum", "syntax"])
def test_invalid_packaged_supervisor_fails_before_service_changes(deployment, problem):
    source, target, _, run = deployment
    old = (target / "job_control.py").read_bytes()
    if problem == "missing":
        (source / "job_control.py").unlink()
    elif problem == "checksum":
        (source / "job_control.py").write_bytes(b"VALUE = 999\n")
    else:
        (source / "job_control.py").write_bytes(b"invalid python !\n")
        manifest = source / "DEPENDENCY-SHA256SUMS"
        manifest.write_text(manifest.read_text().replace(sha(old), sha(b"invalid python !\n")))
    result, calls = run()
    assert result.returncode != 0
    assert not calls and not (target / "backups").exists()
    assert (target / "job_control.py").read_bytes() == old


@pytest.mark.parametrize("problem", ["missing", "different", "symlink"])
def test_existing_dependency_is_never_replaced_by_a_packaged_copy(deployment, problem):
    source, target, _, run = deployment
    dependency = target / "existing_dependency.py"
    (source / dependency.name).write_bytes(dependency.read_bytes())
    dependency.unlink()
    if problem == "different": dependency.write_bytes(b"changed dependency\n")
    if problem == "symlink": dependency.symlink_to(source / dependency.name)
    result, calls = run()
    assert result.returncode != 0 and not calls
    assert not (target / "backups").exists()
    if problem == "missing": assert not dependency.exists()
    if problem == "different": assert dependency.read_bytes() == b"changed dependency\n"
    if problem == "symlink": assert dependency.is_symlink()


@pytest.mark.parametrize("problem", ["missing_manifest", "empty_manifest", "missing_helper", "duplicate", "traversal", "extra_field"])
def test_incomplete_or_malformed_dependency_manifests_fail_closed(deployment, problem):
    source, target, _, run = deployment
    manifest = source / "DEPENDENCY-SHA256SUMS"
    lines = manifest.read_text().splitlines(True)
    if problem == "missing_manifest": manifest.unlink()
    elif problem == "empty_manifest": manifest.write_text("")
    elif problem == "missing_helper": manifest.write_text(lines[0])
    elif problem == "duplicate": manifest.write_text("".join(lines) + lines[-1])
    elif problem == "traversal": manifest.write_text("".join(lines).replace("existing_dependency.py", "../existing_dependency.py"))
    elif problem == "extra_field": manifest.write_text("".join(lines).replace("existing_dependency.py", "existing_dependency.py extra"))
    result, calls = run()
    assert result.returncode != 0 and not calls
    assert not (target / "backups").exists()


@pytest.mark.parametrize("helper_existed", [False, True])
def test_failed_restart_restores_previous_supervisor_presence_and_bytes(deployment, helper_existed):
    source, target, _, run = deployment
    old = b"VALUE = 1\n"
    helper = target / "job_control.py"
    if helper_existed: helper.write_bytes(old)
    else: helper.unlink()
    result, calls = run(FAIL_RESTART_ONCE="1")
    assert result.returncode != 0
    assert len([c for c in calls if c["args"][0] == "restart"]) == 2
    if helper_existed: assert helper.read_bytes() == old
    else: assert not helper.exists()
    assert sum(c["args"][0] == "start" for c in calls) == 2


def test_corrupted_installed_supervisor_never_reaches_candidate_restart(deployment):
    source, target, _, run = deployment
    old = b"VALUE = 1\n"
    (target / "job_control.py").write_bytes(old)
    result, calls = run(CORRUPT_INSTALL="1")
    assert result.returncode != 0
    assert (target / "job_control.py").read_bytes() == old
    restarts = [c for c in calls if c["args"][0] == "restart"]
    assert len(restarts) == 1 and restarts[0]["helper_sha256"] == sha(old)


def test_hash_drift_during_health_cannot_be_reported_as_success(deployment):
    source, target, _, run = deployment
    old = b"VALUE = 1\n"
    (target / "job_control.py").write_bytes(old)
    result, calls = run(CORRUPT_AT_HEALTH="1")
    assert result.returncode != 0
    assert (target / "job_control.py").read_bytes() == old
    assert "Deployment/Verifikation erfolgreich." not in result.stdout
    assert len([c for c in calls if c["args"][0] == "restart"]) == 2


def test_missing_profile_is_installed_as_0644_and_recorded_missing(deployment):
    source, target, _, run = deployment
    name = PROFILES[0]
    (target / name).unlink()
    result, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert not [c for c in calls if c["args"][0] == "restart"]
    assert (target / name).read_bytes() == (source / name).read_bytes()
    assert (target / name).stat().st_mode & 0o777 == 0o644
    backup = next((target / "backups").iterdir())
    assert f"profile/{name}" in (backup / "MISSING-BEFORE.txt").read_text()


def test_changed_profile_is_backed_up_and_replaced_without_worker_restart(deployment):
    source, target, _, run = deployment
    name = PROFILES[1]
    old = b'{"profile":"old"}\n'
    (target / name).write_bytes(old)
    result, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert not [c for c in calls if c["args"][0] == "restart"]
    assert next((target / "backups").glob(f"*/{name}")).read_bytes() == old
    assert (target / name).read_bytes() == (source / name).read_bytes()


def test_extra_or_linked_source_profile_fails_before_service_changes(deployment):
    source, target, _, run = deployment
    extra = source / "profiles/printers/unreviewed.json"
    extra.write_text("{}")
    result, calls = run()
    assert result.returncode != 0
    assert not calls and not (target / "backups").exists()


def test_identical_package_is_read_only_except_local_logs(deployment):
    source, target, _, run = deployment
    before = {name: (target / name).read_bytes() for name in RUNTIME + PROFILES}
    result, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert not calls and not (target / "backups").exists()
    assert before == {name: (target / name).read_bytes() for name in RUNTIME + PROFILES}


@pytest.mark.parametrize("marker", ["queued", "slicing", "dispatcher"])
def test_busy_worker_blocks_even_a_supervisor_only_update(deployment, marker):
    source, target, _, run = deployment
    old = b"VALUE = 1\n"
    (target / "job_control.py").write_bytes(old)
    if marker == "dispatcher": (target / "run/dispatcher.lock").mkdir(parents=True)
    else: (target / "data/jobs" / f"synthetic.{marker}.json").write_text("{}")
    result, calls = run()
    assert result.returncode != 0 and not calls
    assert (target / "job_control.py").read_bytes() == old
    assert not (target / "backups").exists()
