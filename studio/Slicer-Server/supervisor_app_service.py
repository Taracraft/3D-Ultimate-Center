"""Supervisor app lifecycle with a separately confined, network-denied worker.

Only the initial process handles ownership preparation. API, worker and manager
then run as UID/GID 65532 without Linux capabilities. Startup never creates jobs,
starts a printer or weakens TLS; missing administrator-supplied credentials block
startup. The existing persistent store and canonical worker lifecycle are reused.
"""
from __future__ import annotations

import ctypes as C
import errno
import json
import os
from pathlib import Path
import re
import runpy
import signal
import ssl
import stat
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from supervisor_worker_policy import (CANARY, CANARY_BYTES, PROFILE, PolicyError,
                                      apply, install_process_baseline, kernel_status, libc, seal_api_process)

STATE = Path("/data/state")
PROFILES = Path("/data/profiles")
PRIVATE = Path("/data/private/controller")
USER_ID = 65532
OPTIONS = Path("/data/options.json")
OPTION_LIMIT = 16384
TLS_LIMIT = 1024 * 1024


class AppConfigurationError(ValueError):
    pass


def require(condition: bool, code: str) -> None:
    if not condition:
        raise AppConfigurationError(code)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "app_duplicate_option")
        result[key] = value
    return result


def parse_options(raw: bytes) -> dict:
    require(type(raw) is bytes and 0 < len(raw) <= OPTION_LIMIT, "app_options_size_invalid")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError):
        raise AppConfigurationError("app_options_json_invalid") from None
    require(type(value) is dict and set(value) == {"api_secret", "certfile", "keyfile"},
            "app_options_schema_invalid")
    secret = value["api_secret"]
    require(type(secret) is str and 32 <= len(secret) <= 256
            and all(33 <= ord(c) <= 126 for c in secret), "app_api_secret_required")
    for field in ("certfile", "keyfile"):
        name = value[field]
        require(type(name) is str and len(name) <= 128 and name not in {".", ".."}
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", name) is not None,
                "app_tls_filename_invalid")
    require(value["certfile"] != value["keyfile"], "app_tls_files_must_differ")
    return value


def _unlinked(path: Path) -> None:
    require(path.is_absolute() and ".." not in path.parts, "app_path_invalid")
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            require(not part.is_symlink(), "app_path_linked")


def _read(path: Path, limit: int, *, private=False) -> bytes:
    _unlinked(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and 0 < info.st_size <= limit and info.st_uid in {0, USER_ID},
            "app_input_file_invalid")
    require(not info.st_mode & 0o022, "app_input_file_writable")
    if private:
        require(not info.st_mode & 0o027, "app_private_file_permissions_invalid")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino) == (info.st_dev, info.st_ino), "app_input_changed")
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    require(len(raw) == info.st_size and len(raw) <= limit
            and (before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "app_input_changed")
    return raw


def _directory(path: Path, owner: int, mode: int) -> None:
    _unlinked(path)
    if path.exists():
        info = path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == owner
                and stat.S_IMODE(info.st_mode) == mode, "app_directory_identity_invalid")
    else:
        path.mkdir(mode=mode)
        # Finalize permissions while the creator still owns this new directory.
        # No CAP_FOWNER is needed after transferring it to the service user.
        os.chmod(path, mode)
        os.chown(path, owner, owner)


def _write_private(path: Path, raw: bytes) -> None:
    require(path.parent == PRIVATE and type(raw) is bytes and 0 < len(raw) <= TLS_LIMIT,
            "app_private_output_invalid")
    _unlinked(path)
    if path.exists():
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                and info.st_uid == USER_ID and stat.S_IMODE(info.st_mode) == 0o600,
                "app_private_output_identity_changed")
    temp = path.with_name(path.name + ".pending")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            if os.geteuid() == 0:
                os.fchown(handle.fileno(), USER_ID, USER_ID)
        os.replace(temp, path)
        descriptor = os.open(PRIVATE, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def drop_privileges() -> None:
    import resource
    lib = libc()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if os.geteuid() == 0:
        last_cap = int(Path("/proc/sys/kernel/cap_last_cap").read_text())
        require(0 <= last_cap <= 63, "app_capability_range_unknown")
        for capability in range(last_cap + 1):
            result = lib.prctl(24, capability, 0, 0, 0)  # PR_CAPBSET_DROP
            require(result == 0, "app_capability_drop_failed")
        os.setgroups([])
        os.setresgid(USER_ID, USER_ID, USER_ID)
        os.setresuid(USER_ID, USER_ID, USER_ID)
    require(lib.prctl(38, 1, 0, 0, 0) == 0, "app_no_new_privileges_failed")
    state = kernel_status()
    require(state["uids"] == [USER_ID] * 4 and not any(state["caps"].values())
            and state["no_new_privileges"] == 1, "app_privilege_drop_not_observed")


def _environment() -> dict[str, str]:
    # In particular, do not pass SUPERVISOR_TOKEN or administrator options to
    # the worker, its helpers or the API. Paths below contain no secret values.
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
            "HOME": "/tmp", "TMPDIR": "/tmp", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1", "PYTHONNOUSERSITE": "1", "STUDIO_RUNTIME_ISOLATION": PROFILE}


def prepare() -> int:
    import fcntl
    require(os.geteuid() == 0, "app_initial_owner_required")
    seal_api_process()
    options_raw = _read(OPTIONS, OPTION_LIMIT)
    options = parse_options(options_raw)
    certificate = _read(Path("/ssl") / options["certfile"], TLS_LIMIT)
    key = _read(Path("/ssl") / options["keyfile"], TLS_LIMIT, private=True)
    # Validate the supplied pair before creating or modifying runtime data.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(str(Path('/ssl') / options['certfile']),
                            str(Path('/ssl') / options['keyfile']))
    require(_read(OPTIONS, OPTION_LIMIT) == options_raw
            and _read(Path('/ssl') / options['certfile'], TLS_LIMIT) == certificate
            and _read(Path('/ssl') / options['keyfile'], TLS_LIMIT, private=True) == key,
            "app_configuration_changed")
    _directory(Path('/data'), 0, 0o755)
    _directory(Path('/data/private'), 0, 0o755)
    _directory(PRIVATE, USER_ID, 0o700)
    _directory(STATE, USER_ID, 0o700)
    _directory(PROFILES, USER_ID, 0o700)
    if CANARY.exists():
        info = CANARY.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o444 and CANARY.read_bytes() == CANARY_BYTES,
                "app_canary_identity_changed")
    else:
        fd = os.open(CANARY, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(CANARY_BYTES);handle.flush();os.fsync(handle.fileno())
        CANARY.chmod(0o444)
    guard = Path('/data/private/app.guard')
    _unlinked(guard)
    fd = os.open(guard, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    info = os.fstat(fd)
    require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
            and stat.S_IMODE(info.st_mode) == 0o600, 'app_guard_identity_invalid')
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    require(not (PRIVATE/'app-recovery.json').exists(), 'app_recovery_required')
    _write_private(PRIVATE/'api-token', options['api_secret'].encode('ascii'))
    _write_private(PRIVATE/'server.crt', certificate)
    _write_private(PRIVATE/'server.key', key)
    return fd


def api() -> None:
    install_process_baseline()
    drop_privileges()
    seal_api_process()
    os.environ.clear();os.environ.update(_environment())
    import container_service as service
    service.configure_environment(STATE, PROFILES)
    config = service.api_configuration(STATE, PRIVATE/'api-token',
                                       PRIVATE/'server.crt', PRIVATE/'server.key', PROFILES)
    _write_private(PRIVATE/'api-config.json', json.dumps(config, separators=(',', ':')).encode())
    # runpy intentionally avoids exec: Linux exec resets the nondumpable flag.
    require(libc().prctl(3, 0, 0, 0, 0) == 0, 'app_api_process_not_sealed')
    sys.path.insert(0, str(service.PAYLOAD))
    sys.argv = [str(service.PAYLOAD/'server.py'), str(PRIVATE/'api-config.json')]
    runpy.run_path(sys.argv[0], run_name='__main__')


def worker() -> None:
    install_process_baseline()
    drop_privileges()
    os.environ.clear();os.environ.update(_environment())
    apply()
    import container_service as service
    service.configure_environment(STATE, PROFILES)
    service.run_worker(STATE, profile_base=PROFILES)


def initialize() -> None:
    install_process_baseline()
    drop_privileges()
    os.environ.clear();os.environ.update(_environment())
    import container_service as service
    service.initialize_data(STATE)
    service.initialize_profiles(PROFILES)


def _stop(children: list[subprocess.Popen]) -> None:
    for child in children:
        if child.poll() is None:
            # The worker owns its children and their readiness/stop handshake.
            # A group SIGTERM here can kill an unready dispatch child and latch
            # recovery during an otherwise orderly application shutdown.
            child.send_signal(signal.SIGTERM)
    deadline = time.monotonic() + 45
    for child in children:
        if child.poll() is None:
            try:
                child.wait(max(0.1, deadline-time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(5)


def start() -> None:
    os.umask(0o077)
    install_process_baseline()
    guard = prepare()
    env = _environment()
    command = [sys.executable, "-I", str(Path(__file__).resolve())]
    initialized = subprocess.run(command+['init'], env=env, close_fds=True, timeout=30)
    require(initialized.returncode == 0, 'app_store_initialization_failed')
    children = []
    stop = threading.Event()
    old = {s: signal.signal(s, lambda *_: stop.set()) for s in (signal.SIGTERM, signal.SIGINT)}
    failure = None
    try:
        children.append(subprocess.Popen(command+['api'], env=env, close_fds=True, start_new_session=True))
        children.append(subprocess.Popen(command+['worker'], env=env, close_fds=True, start_new_session=True))
        drop_privileges()
        seal_api_process()
        while not stop.wait(.2):
            if any(child.poll() is not None for child in children):
                failure = 'app_owned_process_exited'
                break
    except BaseException:
        failure = 'app_supervision_failed'
        raise
    finally:
        _stop(children)
        if failure:
            _write_private(PRIVATE/'app-recovery.json', json.dumps({'schema': 1,
                'recovery_required': True, 'error': failure}).encode())
        for sig, handler in old.items():
            signal.signal(sig, handler)
        os.close(guard)
    require(failure is None, failure or 'app_operation_failed')


def main() -> None:
    try:
        require(len(sys.argv) == 2 and sys.argv[1] in {'start', 'api', 'worker', 'init'},
                'app_command_invalid')
        {'start': start, 'api': api, 'worker': worker, 'init': initialize}[sys.argv[1]]()
    except (AppConfigurationError, PolicyError) as error:
        print('Ultimate Slicer App: '+str(error), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception:
        # Avoid exposing configuration values, file contents, or exception reprs.
        print('Ultimate Slicer App: app_operation_failed', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
