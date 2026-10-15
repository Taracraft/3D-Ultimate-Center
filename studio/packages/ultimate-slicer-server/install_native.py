"""Fail-closed first-install tool for the independent native Linux slicer.

No install without independently verified bundle, licensed/hash-pinned engine,
root privileges and an empty dedicated install target. Never touches HA paths.
Does not automatically start a slicing service or execute any print jobs.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile

NAME = "ultimate-slicer-server"
FILE_LIMIT = 80
FILE_SIZE_LIMIT = 8 * 1024 * 1024
ARCHIVE_SIZE_LIMIT = 50 * 1024 * 1024
ENGINE_FILE_LIMIT = 150_000
# Exactly these tiny desktop tooltip-index files are irrelevant to headless slicing.
ENGINE_TOOLTIPS_EXCLUDED = frozenset({
    "resources/tooltip/.md",
    "resources/tooltip/zh_CN/.md",
})
ENGINE_TOTAL_LIMIT = 16 * 1024 * 1024 * 1024
SHA_RE = re.compile(r"[a-f0-9]{64}\Z")
ENGINE_LINE = re.compile(r"([a-f0-9]{64})  ([^\x00-\x1f\x7f]+)\Z")
UNITS = frozenset({
    "ultimate-slicer-server.service",
    "ultimate-slicer-dispatch.service",
    "ultimate-slicer-dispatch.timer",
    "ultimate-slicer-refresh.service",
    "ultimate-slicer-refresh.timer",
})
REQUIRED_SOURCE = frozenset({
    "server.py", "job_control.py", "dispatch-job.sh",
    "refresh-state.sh", "append-slicing-journal.sh",
    "progress-pipe-reader.py", "gcode_artifact_validation.py",
    "materialize-bambu-machine.py", "materialize-bambu-multimaterial.py",
})
INSTALLER_FILE = "installer/install_native.py"
# External commands actually used by the bundled job/refresh scripts, installer
# and independent native systemd units. Missing tools must block installation.
NATIVE_RUNTIME_COMMANDS = frozenset({
    "python3", "jq", "awk", "grep", "find", "sort", "head", "tail",
    "cut", "tr", "du", "id", "unshare", "systemctl", "useradd",
    "userdel", "mkfifo", "cp", "chmod", "mkdir", "mv", "rm",
    "sleep", "wc", "date",
})
NATIVE_ABSOLUTE_EXECUTABLES = (
    "/usr/bin/python3", "/usr/bin/unshare", "/usr/bin/true",
    "/usr/sbin/runuser", "/bin/sh",
)


class NativeInstallError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str:
    calc = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            calc.update(chunk)
    return calc.hexdigest()


def safe_relative(value: str) -> bool:
    if not isinstance(value, str) or "\\" in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    normalized = PurePosixPath(value)
    return (
        bool(value)
        and not normalized.is_absolute()
        and value == normalized.as_posix()
        and all(p not in {".", "..", ""} and not p.startswith(".") for p in normalized.parts)
    )


def inspect_bundle(archive_path: Path, expected_sha256: str) -> tuple[dict, dict[str, bytes]]:
    """Pure read-only archive inspection with external SHA and internal file hashes."""
    if not SHA_RE.fullmatch(expected_sha256):
        raise NativeInstallError("valid externally supplied SHA-256 required")
    if not archive_path.is_file() or archive_path.is_symlink():
        raise NativeInstallError("bundle must be a regular file")
    if archive_path.stat().st_size > ARCHIVE_SIZE_LIMIT:
        raise NativeInstallError("bundle exceeds maximum compressed size")
    if hash_file(archive_path) != expected_sha256:
        raise NativeInstallError("bundle digest does not match external release SHA-256")

    files: dict[str, bytes] = {}
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > FILE_LIMIT:
            raise NativeInstallError("bundle has too many files")
        for member in members:
            prefix = NAME + "/"
            if not member.isfile() or not member.name.startswith(prefix):
                raise NativeInstallError("bundle must contain regular files in package namespace")
            relative = member.name[len(prefix):]
            if not safe_relative(relative) or member.size > FILE_SIZE_LIMIT:
                raise NativeInstallError("bundle contains unsafe name or oversized file")
            if relative in files or member.mode & 0o7000:
                raise NativeInstallError("duplicate bundle file or elevated permissions")
            handle = archive.extractfile(member)
            if handle is None:
                raise NativeInstallError("missing bundle content")
            value = handle.read(FILE_SIZE_LIMIT + 1)
            if len(value) != member.size:
                raise NativeInstallError("bundle file length mismatch")
            files[relative] = value

    raw_manifest = files.pop("source-manifest.json", None)
    if raw_manifest is None:
        raise NativeInstallError("bundle source identity missing")
    try:
        metadata = json.loads(raw_manifest.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise NativeInstallError("invalid bundle source identity") from error

    if metadata.get("package") != NAME or metadata.get("schema") != 1:
        raise NativeInstallError("unexpected bundle format")
    rows = metadata.get("files")
    if not isinstance(rows, list) or len(rows) != len(files):
        raise NativeInstallError("bundle file inventory incomplete")
    verified: set[str] = set()
    for record in rows:
        if not isinstance(record, dict):
            raise NativeInstallError("invalid bundle file entry")
        name = record.get("path")
        if not isinstance(name, str) or not safe_relative(name) or name in verified:
            raise NativeInstallError("invalid or duplicated bundle identity path")
        data = files.get(name)
        if data is None or digest(data) != record.get("sha256") or len(data) != record.get("size_bytes"):
            raise NativeInstallError("bundle has untrusted or missing payload")
        verified.add(name)
    if verified != files.keys() or metadata.get("complete_source_file_count") != len(files):
        raise NativeInstallError("bundle payload differs from pinned inventory")
    paths = set(files)
    if (
        {f"systemd/{unit}" for unit in UNITS} != {p for p in paths if p.startswith("systemd/")}
        or not {f"payload/{name}" for name in REQUIRED_SOURCE}.issubset(paths)
        or INSTALLER_FILE not in paths
        or any(path.startswith(("engines/", "secrets/", "config/")) for path in paths)
    ):
        raise NativeInstallError("bundle has missing components or unexpected private assets")
    for name in UNITS:
        content = files[f"systemd/{name}"]
        if b"/var/lib/homeassistant" in content or b"printer_control_center" in content:
            raise NativeInstallError("native systemd unit depends on private HA host")
        if name.endswith(".service") and not all(
            field in content
            for field in (b"User=ultimate-slicer", b"NoNewPrivileges=yes", b"ProtectSystem=strict")
        ):
            raise NativeInstallError("native systemd unit is not rootless")
    return metadata, files


def verify_engine(engine_root: Path, pinned_manifest: Path) -> list[tuple[str, Path, str]]:
    """No implicit engine download, bundled proprietary executable or unpinned library."""
    if (
        not engine_root.is_dir()
        or engine_root.is_symlink()
        or not pinned_manifest.is_file()
        or pinned_manifest.is_symlink()
    ):
        raise NativeInstallError("independent engine directory and SHA manifest required")
    # Extracted desktop AppImages may contain one non-runtime icon alias.
    # Permit only the exact internal .DirIcon -> BambuStudio.png link.
    # Everything else must be an ordinary, manifest-pinned regular file.
    desktop_icon = engine_root / ".DirIcon"
    for part in engine_root.rglob("*"):
        if part.is_symlink():
            if (
                part != desktop_icon
                or os.readlink(part) != "BambuStudio.png"
                or not (engine_root / "BambuStudio.png").is_file()
                or (engine_root / "BambuStudio.png").is_symlink()
            ):
                raise NativeInstallError("unsafe engine symbolic link")
        elif part.is_file():
            relative = part.relative_to(engine_root).as_posix()
            # Two explicitly known desktop-only Markdown index files are omitted
            # from the headless runtime. Do not allow large hidden payloads to
            # hide behind their permitted names.
            if (
                relative in ENGINE_TOOLTIPS_EXCLUDED
                and (part.stat().st_size > 4096 or not part.is_file())
            ):
                raise NativeInstallError("unsafe excluded engine metadata")
        elif not part.is_dir():
            raise NativeInstallError("engine contains special filesystem entry")
    lines = pinned_manifest.read_text(encoding="utf-8").splitlines()
    if not lines or len(lines) > ENGINE_FILE_LIMIT:
        raise NativeInstallError("invalid engine SHA manifest")
    entries: list[tuple[str, Path, str]] = []
    seen: set[str] = set()
    total = 0
    base = engine_root.resolve(strict=True)
    for line in lines:
        match = ENGINE_LINE.fullmatch(line)
        if not match or not safe_relative(match.group(2)):
            raise NativeInstallError("invalid engine SHA record")
        expected, relative = match.groups()
        if relative in seen:
            raise NativeInstallError("duplicate engine file")
        seen.add(relative)
        path = engine_root / relative
        if not path.is_file() or path.is_symlink() or not path.resolve(strict=True).is_relative_to(base):
            raise NativeInstallError("engine file is not a safe regular file")
        length = path.stat().st_size
        total += length
        if total > ENGINE_TOTAL_LIMIT or hash_file(path) != expected:
            raise NativeInstallError("engine binary or profile checksum differs")
        entries.append((relative, path, expected))
    binaries = [path for relative, path, _ in entries if relative == "bin/bambu-studio"]
    if len(binaries) != 1:
        raise NativeInstallError("verified native Linux ELF slicing engine required")
    with binaries[0].open("rb") as executable:
        if executable.read(4) != b"\x7fELF":
            raise NativeInstallError("verified native Linux ELF slicing engine required")
    # Windows NTFS cannot represent Unix executable mode; the actual Linux
    # installation repeats this check before any privileged file changes.
    if sys.platform == "linux" and not binaries[0].stat().st_mode & 0o111:
        raise NativeInstallError("native slicing engine must be executable")
    for category in ("machine", "process", "filament"):
        if not any(
            relative.startswith(f"resources/profiles/BBL/{category}/")
            and relative.endswith(".json")
            for relative, _, _ in entries
        ):
            raise NativeInstallError("native engine profile contract incomplete")
    # The permitted desktop icon alias is deliberately not copied to the
    # independent headless Linux runtime; its target remains SHA-pinned.
    actual = {
        path.relative_to(base).as_posix()
        for path in engine_root.rglob("*")
        if path.is_file() and not path.is_symlink()
        and path.relative_to(base).as_posix() not in ENGINE_TOOLTIPS_EXCLUDED
    }
    if actual != seen:
        raise NativeInstallError("engine contains unreviewed files")
    return entries


def require_unprivileged_network_namespace() -> None:
    """Probe namespace creation as the actual service account before installing.

    This runs only the no-op true executable inside an isolated user/net
    namespace: never invokes the slicer or touches a printer/network service.
    """
    command = [
        "/usr/sbin/runuser", "--user", "ultimate-slicer", "--",
        "/usr/bin/unshare", "--user", "--map-root-user", "--net", "--",
        "/usr/bin/true",
    ]
    try:
        subprocess.run(
            command, check=True, timeout=12,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise NativeInstallError("unprivileged network namespace not available") from None


def require_native_runtime_dependencies() -> None:
    """Fail before user/files/unit changes if Linux worker prerequisites are absent."""
    missing = sorted(
        command for command in NATIVE_RUNTIME_COMMANDS
        if shutil.which(command) is None
    )
    if missing:
        raise NativeInstallError("missing native runtime command: " + ", ".join(missing))
    if os.name == "posix":
        for binary in NATIVE_ABSOLUTE_EXECUTABLES:
            if not Path(binary).is_file() or not os.access(binary, os.X_OK):
                raise NativeInstallError("missing native system executable: " + binary)


def installation_roots() -> tuple[Path, Path, Path, Path]:
    """Fixed Linux installation roots; never configurable through the CLI."""
    return (
        Path("/opt/ultimate-slicer-server"),
        Path("/etc/ultimate-slicer-server"),
        Path("/var/lib/ultimate-slicer-server"),
        Path("/etc/systemd/system"),
    )


def install_first_time(
    files: dict[str, bytes],
    archive_sha256: str,
    engine_files: list[tuple[str, Path, str]],
) -> dict:
    """Root-only first installation. Existing data or services always block installation."""
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise NativeInstallError("first install requires an explicit Linux root context")
    if os.name == "posix":
        require_native_runtime_dependencies()
    import grp
    import pwd

    code_root, config_root, data_root, service_root = installation_roots()
    targets = [code_root, config_root, data_root]
    targets += [service_root / name for name in UNITS]
    if any(p.exists() or p.is_symlink() for p in targets):
        raise NativeInstallError("installation already present; refuse to overwrite state or service")
    if any(p.is_symlink() for p in (code_root.parent, config_root.parent, data_root.parent, service_root)):
        raise NativeInstallError("installation root points through a symbolic link")

    created: list[Path] = []
    stage: Path | None = None
    user_created = False
    try:
        try:
            user = pwd.getpwnam("ultimate-slicer")
        except KeyError:
            subprocess.run(
                ["useradd", "--system", "--user-group", "--no-create-home",
                 "--home-dir", str(data_root), "--shell", "/usr/sbin/nologin", "ultimate-slicer"],
                check=True,
            )
            user_created = True
            user = pwd.getpwnam("ultimate-slicer")
        if user.pw_uid == 0:
            raise NativeInstallError("native slicing service must never run as root")
        group = grp.getgrnam("ultimate-slicer")
        if group.gr_gid != user.pw_gid:
            raise NativeInstallError("service group does not match dedicated user")
        require_unprivileged_network_namespace()

        stage = Path(tempfile.mkdtemp(prefix=".ultimate-slicer-install-", dir=code_root.parent))
        os.chmod(stage, 0o700)
        for rel, blob in files.items():
            if rel.startswith("payload/"):
                target = stage / rel.removeprefix("payload/")
            elif rel == INSTALLER_FILE:
                continue
            elif rel.startswith("systemd/"):
                continue
            else:
                raise NativeInstallError("unexpected installation payload")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
            executable = target.suffix == ".sh" or target.name == "progress-pipe-reader.py"
            os.chmod(target, 0o755 if executable else 0o644)

        engine = stage / "engines" / "bambu-studio" / "squashfs-root"
        engine.mkdir(parents=True, exist_ok=False)
        for relative, src, pinned_hash in engine_files:
            dest = engine / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest, follow_symlinks=False)
            if hash_file(dest) != pinned_hash:
                raise NativeInstallError("engine changed during staging")
            os.chmod(dest, 0o755 if src.stat().st_mode & 0o111 else 0o644)
        os.chmod(stage, 0o755)
        stage.rename(code_root)
        created.append(code_root)
        stage = None

        config_root.mkdir(mode=0o750)
        created.append(config_root)
        os.chown(config_root, 0, group.gr_gid)
        os.chmod(config_root, 0o750)
        secret = secrets.token_urlsafe(48)
        config = {
            "host": "127.0.0.1",
            "port": 8099,
            "base_dir": str(data_root),
            "source_root": str(code_root),
            "profile_root": str(code_root / "profiles/printers"),
            "engine_root": str(code_root / "engines/bambu-studio/squashfs-root"),
            "token": secret,
        }
        target_config = config_root / "config.json"
        target_config.write_text(json.dumps(config) + "\n", encoding="utf-8")
        os.chmod(target_config, 0o640)
        os.chown(target_config, 0, group.gr_gid)

        data_root.mkdir(mode=0o750)
        created.append(data_root)
        os.chown(data_root, user.pw_uid, group.gr_gid)
        os.chmod(data_root, 0o750)

        for unit in sorted(UNITS):
            target = service_root / unit
            # Exclusive creation prevents replacing a file that appeared after preflight.
            with target.open("xb") as stream:
                created.append(target)
                stream.write(files["systemd/" + unit])
            os.chmod(target, 0o644)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        return {
            "installed": True,
            "archive_sha256": archive_sha256,
            "service_activation": "manual_after_health_and_tls_review",
            "configuration_path": str(config_root / "config.json"),
            "token_exposed": False,
        }
    except BaseException as original_error:
        rollback_errors: list[str] = []
        for path in reversed(created):
            try:
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
            except OSError:
                rollback_errors.append("path")
        if user_created and not rollback_errors:
            try:
                subprocess.run(["userdel", "ultimate-slicer"], check=True)
            except (OSError, subprocess.CalledProcessError):
                rollback_errors.append("account")
        try:
            subprocess.run(["systemctl", "daemon-reload"], check=False)
        except OSError:
            rollback_errors.append("systemd")
        if rollback_errors:
            raise NativeInstallError("native first-install rollback incomplete") from original_error
        raise
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)



def upgrade_backup_root() -> Path:
    """Backup stays on the same filesystem as /opt for atomic rename/restore."""
    return Path("/opt/.ultimate-slicer-server-backups")


def require_native_units_inactive() -> None:
    """Never upgrade code while any native service or timer may hold a job."""
    for name in sorted(UNITS):
        try:
            result = subprocess.run(
                ["systemctl", "is-active", name],
                capture_output=True, text=True, check=False, timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise NativeInstallError("cannot verify native unit idle state") from None
        if result.stdout.strip() != "inactive":
            raise NativeInstallError("all native slicer services and timers must be inactive")


def installed_native_payload_matches(
    code_root: Path,
    files: dict[str, bytes],
    engine_files: list[tuple[str, Path, str]],
) -> bool:
    """Verify an already installed program without modifying its contents."""
    for name, blob in files.items():
        if not name.startswith("payload/"):
            continue
        relative = name.removeprefix("payload/")
        if not safe_relative(relative):
            raise NativeInstallError("invalid installed program path")
        target = code_root / relative
        if target.is_symlink() or not target.is_file():
            return False
        if hash_file(target) != digest(blob):
            return False
    engine_root = code_root / "engines" / "bambu-studio" / "squashfs-root"
    for relative, _source, expected in engine_files:
        if not safe_relative(relative):
            raise NativeInstallError("invalid installed engine path")
        target = engine_root / relative
        if target.is_symlink() or not target.is_file():
            return False
        if hash_file(target) != expected:
            return False
    return True


def upgrade_stopped_native_server(
    files: dict[str, bytes],
    archive_sha256: str,
    engine_files: list[tuple[str, Path, str]],
) -> dict:
    """Atomic code-only upgrade. Leaves token, config, state and units unchanged.

    Only previously installed independent package layouts are accepted. The
    previous /opt tree remains root-only accessible for a manual restoration.
    """
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise NativeInstallError("native upgrade requires Linux root")
    if os.name == "posix":
        require_native_runtime_dependencies()
    import pwd
    code, config, state, unitdir = installation_roots()
    if any(path.is_symlink() for path in (code, config, state, unitdir)):
        raise NativeInstallError("native installation contains linked roots")
    if not all(path.is_dir() for path in (code, config, state, unitdir)):
        raise NativeInstallError("native installation is incomplete")
    token_config = config / "config.json"
    if not token_config.is_file() or token_config.is_symlink():
        raise NativeInstallError("existing API configuration missing")
    # Windows NTFS cannot report trustworthy Unix permission bits in a mocked Linux test.
    # On the actual native Linux host this world-access check remains mandatory.
    if os.name == "posix" and token_config.stat().st_mode & 0o007:
        raise NativeInstallError("existing API configuration exposes data to other users")
    if not (code / "server.py").is_file() or (code / "server.py").is_symlink():
        raise NativeInstallError("old server source missing")
    try:
        user = pwd.getpwnam("ultimate-slicer")
    except KeyError:
        raise NativeInstallError("dedicated native service user missing") from None
    if user.pw_uid == 0:
        raise NativeInstallError("native server must never run as root")
    for unit in sorted(UNITS):
        current = unitdir / unit
        if (
            not current.is_file() or current.is_symlink()
            or current.read_bytes() != files.get("systemd/" + unit)
        ):
            raise NativeInstallError("systemd unit migration requires separate review")
    jobdir = state / "data" / "jobs"
    if jobdir.exists():
        if not jobdir.is_dir() or jobdir.is_symlink():
            raise NativeInstallError("unsafe native job directory")
        for pattern in ("*.queued.json", "*.slicing.json", "*.cancelling.json", "*.held.json"):
            if any(jobdir.glob(pattern)):
                raise NativeInstallError("native jobs pending; upgrade refused")

    require_native_units_inactive()
    require_unprivileged_network_namespace()
    if installed_native_payload_matches(code, files, engine_files):
        return {
            "upgraded": False,
            "unchanged": True,
            "archive_sha256": archive_sha256,
            "backup_created": False,
            "api_secret_preserved": True,
            "job_state_preserved": True,
        }

    stage: Path | None = None
    backup: Path | None = None
    saved: Path | None = None
    try:
        stage = Path(tempfile.mkdtemp(prefix=".ultimate-slicer-upgrade-", dir=code.parent))
        os.chmod(stage, 0o700)
        for relative, content in files.items():
            if relative.startswith("payload/"):
                payload_name = relative.removeprefix("payload/")
                if not safe_relative(payload_name):
                    raise NativeInstallError("unsafe upgrade source path")
                target = stage / payload_name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
                executable = target.suffix == ".sh" or target.name == "progress-pipe-reader.py"
                os.chmod(target, 0o755 if executable else 0o644)
            elif relative == INSTALLER_FILE or relative.startswith("systemd/"):
                continue
            else:
                raise NativeInstallError("unrecognized native upgrade file")

        engine = stage / "engines" / "bambu-studio" / "squashfs-root"
        engine.mkdir(parents=True, exist_ok=False)
        for relative, source, expected in engine_files:
            if not safe_relative(relative):
                raise NativeInstallError("invalid engine upgrade file path")
            target = engine / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target, follow_symlinks=False)
            if hash_file(target) != expected:
                raise NativeInstallError("engine changed during native upgrade")
            os.chmod(target, 0o755 if source.stat().st_mode & 0o111 else 0o644)

        os.chmod(stage, 0o755)
        require_native_units_inactive()
        backup_parent = upgrade_backup_root()
        if backup_parent.is_symlink() or (
            backup_parent.exists() and not backup_parent.is_dir()
        ):
            raise NativeInstallError("upgrade backup location invalid")
        backup_parent.mkdir(mode=0o700, exist_ok=True)
        if backup_parent.stat().st_uid != 0:
            raise NativeInstallError("upgrade backup location is not owned by root")
        os.chmod(backup_parent, 0o700)
        backup = Path(tempfile.mkdtemp(prefix="code-before-", dir=backup_parent))
        os.chmod(backup, 0o700)
        saved = backup / "code"
        code.rename(saved)
        try:
            stage.rename(code)
            stage = None
        except BaseException:
            # Keep the previous runtime available if the new code cannot be published.
            if not code.exists() and saved.exists():
                saved.rename(code)
            raise

        return {
            "upgraded": True,
            "archive_sha256": archive_sha256,
            "previous_code_backup": str(saved),
            "api_secret_preserved": True,
            "job_state_preserved": True,
            "systemd_units_unchanged": True,
            "service_activation": "manual_after_health_and_tls_review",
        }
    finally:
        if stage is not None and stage.exists():
            shutil.rmtree(stage)



def restore_stopped_native_code(previous_code: Path) -> dict:
    """Restore only a protected, prior atomic-upgrade source snapshot.

    Does not touch API credentials, persistent jobs or native unit files. The
    replaced code is retained as an additional root-only backup.
    """
    if sys.platform != "linux" or not hasattr(os, "geteuid") or os.geteuid() != 0:
        raise NativeInstallError("native code restoration requires Linux root")
    code, config, state, unitdir = installation_roots()
    backup_root = upgrade_backup_root()
    if (
        not backup_root.is_dir()
        or backup_root.is_symlink()
        or backup_root.stat().st_uid != 0
        or not isinstance(previous_code, Path)
        or previous_code.is_symlink()
        or not previous_code.is_dir()
        or previous_code.name != "code"
        or previous_code.parent.is_symlink()
    ):
        raise NativeInstallError("approved root-owned code backup required")
    if previous_code.parent.parent.resolve(strict=True) != backup_root.resolve(strict=True):
        raise NativeInstallError("code backup is outside trusted upgrade history")
    for path in (code, config, state, unitdir):
        if not path.is_dir() or path.is_symlink():
            raise NativeInstallError("current native installation incomplete")
    if not (previous_code / "server.py").is_file():
        raise NativeInstallError("restoration source missing native server")
    config_file = config / "config.json"
    if not config_file.is_file() or config_file.is_symlink():
        raise NativeInstallError("native API credentials missing")
    if os.name == "posix" and config_file.stat().st_mode & 0o007:
        raise NativeInstallError("native API credential permissions unsafe")
    jobdir = state / "data" / "jobs"
    if jobdir.exists():
        if not jobdir.is_dir() or jobdir.is_symlink():
            raise NativeInstallError("native job history location unsafe")
        for pattern in ("*.queued.json", "*.slicing.json", "*.cancelling.json", "*.held.json"):
            if any(jobdir.glob(pattern)):
                raise NativeInstallError("native jobs pending; restoration refused")
    require_native_units_inactive()
    require_unprivileged_network_namespace()

    # The filesystem swap is only performed after all guards have passed.
    require_native_units_inactive()
    swap_dir = Path(tempfile.mkdtemp(prefix="code-before-restoration-", dir=backup_root))
    os.chmod(swap_dir, 0o700)
    displaced = swap_dir / "code"
    code.rename(displaced)
    try:
        previous_code.rename(code)
    except BaseException:
        if not code.exists() and displaced.exists():
            displaced.rename(code)
        raise
    return {
        "restored": True,
        "replaced_code_backup": str(displaced),
        "api_secret_preserved": True,
        "job_state_preserved": True,
        "service_activation": "manual_after_health_and_tls_review",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect, first-install, upgrade or restore native slicer code")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--archive-sha256")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true", help="first install; never starts services")
    mode.add_argument("--upgrade", action="store_true", help="atomic code-only upgrade; native units must stay unchanged")
    mode.add_argument("--rollback", action="store_true", help="restore a protected previous program backup")
    mode.add_argument("--check-host", action="store_true", help="read-only native Linux dependency preflight")
    parser.add_argument("--code-backup", type=Path)
    parser.add_argument("--engine-root", type=Path)
    parser.add_argument("--engine-sha256-manifest", type=Path)
    parser.add_argument("--accept-engine-license", action="store_true")
    args = parser.parse_args()
    try:
        if args.check_host:
            if (
                args.archive is not None or args.archive_sha256 is not None
                or args.code_backup is not None or args.engine_root is not None
                or args.engine_sha256_manifest is not None or args.accept_engine_license
            ):
                raise NativeInstallError("host dependency check does not accept installation inputs")
            if sys.platform != "linux":
                raise NativeInstallError("native host dependency check requires Linux")
            require_native_runtime_dependencies()
            print(json.dumps({
                "host_dependencies": "ready",
                "prerequisite_commands": len(NATIVE_RUNTIME_COMMANDS),
                "installation_performed": False,
            }))
            return 0
        if args.rollback:
            if (
                args.code_backup is None or args.archive is not None
                or args.archive_sha256 is not None or args.engine_root is not None
                or args.engine_sha256_manifest is not None or args.accept_engine_license
            ):
                raise NativeInstallError("code rollback requires only --code-backup")
            print(json.dumps(restore_stopped_native_code(args.code_backup)))
            return 0
        if args.code_backup is not None or args.archive is None or args.archive_sha256 is None:
            raise NativeInstallError("an external bundle and SHA-256 are required")
        manifest, files = inspect_bundle(args.archive, args.archive_sha256)
        if not args.install and not args.upgrade:
            print(json.dumps({
                "bundle_verified": True,
                "source_files": len(files),
                "native_deploy_ready": manifest.get("native_deploy_ready") is True,
                "installation_performed": False,
            }))
            return 0
        # Source candidates stay readable for audit, but must never be installed
        # until all independent Linux, license and release checks are approved.
        if manifest.get("native_deploy_ready") is not True:
            raise NativeInstallError("native package not approved for install or upgrade")
        if (
            not args.accept_engine_license
            or args.engine_root is None
            or args.engine_sha256_manifest is None
        ):
            raise NativeInstallError("licensed and independently pinned engine required")
        engine_files = verify_engine(args.engine_root, args.engine_sha256_manifest)
        report = (
            upgrade_stopped_native_server(files, args.archive_sha256, engine_files)
            if args.upgrade
            else install_first_time(files, args.archive_sha256, engine_files)
        )
        print(json.dumps(report))
        return 0
    except (NativeInstallError, OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as exc:
        print(f"Native installer refused: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
