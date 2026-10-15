"""Fixed local Docker adapter for the transactional host lifecycle.

No request may provide a command, path, environment variable or callback.  The
trusted host entrypoint constructs :class:`FixedDockerConfig` from provisioned
local state and passes only lifecycle bindings to this adapter.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import ssl
import stat
import subprocess
import threading
import time
import urllib.request


MAX_OUTPUT = 128 * 1024
MAX_HTTP = 64 * 1024
SERVICES = frozenset(("api", "worker"))
HEX64 = re.compile(r"[a-f0-9]{64}")
GENERATION = re.compile(r"g-[a-f0-9]{64}")
RUNTIME_UID = 65532


class DockerAdapterError(RuntimeError):
    """Stable error code; never include command output, paths or secrets."""


@dataclass(frozen=True)
class Result:
    returncode: int
    stdout: bytes
    stderr: bytes


def _regular(path: Path, *, private=False) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise DockerAdapterError("invalid_local_path")
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise DockerAdapterError("linked_local_path")
    try:
        info = path.lstat()
    except OSError as exc:
        raise DockerAdapterError("local_file_required") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise DockerAdapterError("regular_local_file_required")
    if os.name == "posix":
        allowed = (0, os.geteuid(), RUNTIME_UID) if private else (0, os.geteuid())
        if info.st_uid not in allowed:
            raise DockerAdapterError("local_owner_rejected")
        if private and info.st_mode & 0o077:
            raise DockerAdapterError("private_local_file_required")
        if not private and info.st_mode & 0o022:
            raise DockerAdapterError("writable_local_file_rejected")
    return path


def _directory(path: Path, *, writable=False) -> Path:
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise DockerAdapterError("invalid_local_path")
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise DockerAdapterError("linked_local_path")
    if not path.is_dir():
        raise DockerAdapterError("local_directory_required")
    if os.name == "posix":
        info = path.stat()
        if info.st_uid not in (0, os.geteuid()) or (writable and info.st_mode & 0o002):
            raise DockerAdapterError("local_directory_permissions")
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(_regular(path).read_bytes()).hexdigest()


class BoundedRunner:
    """Run one argv vector without a shell and drain output within a hard bound."""

    def __init__(self, maximum=MAX_OUTPUT):
        if type(maximum) is not int or not 1024 <= maximum <= MAX_OUTPUT:
            raise ValueError("invalid_output_limit")
        self.maximum = maximum

    def __call__(self, argv, *, env, timeout):
        if (type(argv) is not tuple or not argv or any(type(x) is not str for x in argv)
                or type(env) is not dict or type(timeout) not in (int, float)
                or not 0 < timeout <= 300):
            raise DockerAdapterError("invalid_local_command")
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env, shell=False,
                                   start_new_session=True)
        buffers = [bytearray(), bytearray()]
        overflow = threading.Event()

        def drain(stream, target):
            while True:
                chunk = stream.read(8192)
                if not chunk:
                    return
                if len(target) < self.maximum + 1:
                    target.extend(chunk[: self.maximum + 1 - len(target)])
                if len(target) > self.maximum:
                    overflow.set()

        threads = [threading.Thread(target=drain, args=(stream, buffers[index]), daemon=True)
                   for index, stream in enumerate((process.stdout, process.stderr))]
        for thread in threads:
            thread.start()
        deadline = time.monotonic() + timeout
        timed_out = False
        while process.poll() is None and not overflow.is_set():
            if time.monotonic() >= deadline:
                timed_out = True
                break
            time.sleep(.02)
        if timed_out or overflow.is_set():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (AttributeError, OSError):
                process.kill()
        process.wait()
        for thread in threads:
            thread.join(timeout=2)
        for stream in (process.stdout, process.stderr):
            stream.close()
        if any(thread.is_alive() for thread in threads):
            raise DockerAdapterError("docker_output_drain_failed")
        if timed_out:
            raise DockerAdapterError("docker_command_timeout")
        if overflow.is_set():
            raise DockerAdapterError("docker_output_limit")
        return Result(process.returncode, bytes(buffers[0]), bytes(buffers[1]))


@dataclass(frozen=True)
class FixedDockerConfig:
    docker: str
    compose: Path
    compose_sha256: str
    project: str
    image_id: str
    store: Path
    data: Path
    profiles: Path
    token: Path
    tls: Path
    bind: str
    port: int
    api_host: str
    volume_sha256: str

    def validate(self):
        if self.docker != "/usr/bin/docker":
            raise DockerAdapterError("fixed_docker_binary_required")
        compose = _regular(self.compose)
        if not HEX64.fullmatch(self.compose_sha256) or _sha(compose) != self.compose_sha256:
            raise DockerAdapterError("compose_digest_mismatch")
        if re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,62}", self.project or "") is None:
            raise DockerAdapterError("invalid_project_name")
        if not self.image_id.startswith("sha256:") or not HEX64.fullmatch(self.image_id[7:]):
            raise DockerAdapterError("immutable_image_required")
        for path in (self.store, self.data, self.profiles, self.tls):
            _directory(path)
        _regular(self.token, private=True)
        if self.bind not in ("127.0.0.1", "::1"):
            raise DockerAdapterError("fixed_bind_required")
        if type(self.port) is not int or not 1024 <= self.port <= 65535:
            raise DockerAdapterError("invalid_api_port")
        if re.fullmatch(r"[A-Za-z0-9.-]{1,253}", self.api_host or "") is None:
            raise DockerAdapterError("invalid_api_host")
        if not HEX64.fullmatch(self.volume_sha256):
            raise DockerAdapterError("invalid_volume_binding")
        return self


def _json(data: bytes):
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError):
        raise DockerAdapterError("invalid_docker_response") from None


class DockerHostAdapter:
    """Trusted local implementation of the host_lifecycle driver contract."""

    def __init__(self, config: FixedDockerConfig, *, runner=None, api_probe=None):
        self.config = config.validate()
        self.runner = runner or BoundedRunner()
        self.api_probe = api_probe or self._probe_api

    def _env(self, generation_id, *, require_engine=True):
        if (GENERATION.fullmatch(generation_id or "") is None
                or type(require_engine) is not bool):
            raise DockerAdapterError("invalid_generation")
        engine = self.config.store / "generations" / generation_id
        if require_engine:
            _directory(engine)
        return {**os.environ, "SLICER_IMAGE": self.config.image_id,
                "SLICER_DATA": str(self.config.data), "SLICER_ENGINE": str(engine),
                "SLICER_TOKEN": str(self.config.token), "SLICER_TLS": str(self.config.tls),
                "SLICER_PROFILES": str(self.config.profiles), "SLICER_BIND": self.config.bind,
                "SLICER_PORT": str(self.config.port)}

    def _run(self, argv, *, generation_id, timeout=30, ok=(0,), extra_env=None,
             require_engine=True):
        if _sha(self.config.compose) != self.config.compose_sha256:
            raise DockerAdapterError("compose_digest_mismatch")
        env = (dict(os.environ) if generation_id is None else
               self._env(generation_id, require_engine=require_engine))
        if extra_env is not None:
            if (type(extra_env) is not dict
                    or set(extra_env) != {"SLICER_BOOTSTRAP_REQUEST_ID"}
                    or type(extra_env["SLICER_BOOTSTRAP_REQUEST_ID"]) is not str
                    or re.fullmatch(r"[a-f0-9]{32}",
                                    extra_env["SLICER_BOOTSTRAP_REQUEST_ID"]) is None):
                raise DockerAdapterError("invalid_bootstrap_request")
            env.update(extra_env)
        result = self.runner(tuple(argv), env=env, timeout=timeout)
        if type(result) is not Result or result.returncode not in ok:
            raise DockerAdapterError("docker_command_failed")
        return result.stdout
    def _inventory(self, generation_id=None):
        output = self._run((self.config.docker, "container", "ls", "--all", "--no-trunc",
            "--filter", "label=com.docker.compose.project=" + self.config.project,
            "--format", '{{.ID}} {{.Label "com.docker.compose.service"}}'),
            generation_id=generation_id)
        found = {}
        identities = set()
        try:
            lines = output.decode("ascii", "strict").splitlines()
        except UnicodeError:
            raise DockerAdapterError("invalid_container_inventory") from None
        for raw in lines:
            fields = raw.split(" ")
            if (len(fields) != 2 or HEX64.fullmatch(fields[0]) is None
                    or re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,62}", fields[1]) is None):
                raise DockerAdapterError("invalid_container_inventory")
            ident, service = fields
            if service in found or ident in identities:
                raise DockerAdapterError("duplicate_owned_container")
            found[service] = ident
            identities.add(ident)
        return found

    def _list(self, generation_id):
        found = {k: v for k, v in self._inventory(generation_id).items() if k in SERVICES}
        if set(found) != SERVICES:
            raise DockerAdapterError("partial_runtime_reconciliation_required")
        return found

    def installation_state(self):
        """Observe bootstrap vs existing runtime without requiring ACTIVE.

        This is not an installation permit. Provisioning must additionally
        validate storage, journals, credentials and image readiness under its
        own mutation lock and repeat this observation immediately before use.
        Even an empty result cannot prove that a prior installation never existed.
        No start, stop, exec, download or filesystem mutation occurs here.
        """
        self.config.validate()
        active = self._active_record(optional=True)
        inventory = self._inventory()
        if set(inventory) - SERVICES:
            raise DockerAdapterError("unexpected_project_containers")
        if inventory and set(inventory) != SERVICES:
            raise DockerAdapterError("partial_runtime_reconciliation_required")
        if bool(inventory) != (active is not None):
            raise DockerAdapterError("runtime_store_reconciliation_required")
        proof = None
        if inventory:
            generation = active["generation_id"]
            rows = self._inspect(inventory, generation)
            proof = self._verify(rows, generation, running=self._pair_running(rows))
        # Detect changes across the read sequence. This deliberately remains a
        # point-in-time observation, never a substitute for installation locking.
        if self._inventory() != inventory or self._active_record(optional=True) != active:
            raise DockerAdapterError("installation_observation_changed")
        return {"state": ("empty" if proof is None else
                          "running" if proof["running"] else "stopped"),
                "runtime": proof, "installation_permitted": False}

    def _inspect(self, ids, generation_id):
        if type(ids) is not dict or set(ids) != SERVICES or any(
                HEX64.fullmatch(value or "") is None for value in ids.values()):
            raise DockerAdapterError("invalid_container_identity")
        raw = self._run((self.config.docker, "container", "inspect", ids["api"], ids["worker"]),
                        generation_id=generation_id)
        rows = _json(raw)
        if type(rows) is not list or len(rows) != 2:
            raise DockerAdapterError("invalid_docker_response")
        by_service = {}
        for row in rows:
            try:
                ident = row["Id"]
                labels = row["Config"]["Labels"]
                service = labels["com.docker.compose.service"]
            except (KeyError, TypeError):
                raise DockerAdapterError("invalid_docker_response") from None
            if (service not in SERVICES or labels.get("com.docker.compose.project") != self.config.project
                    or ident != ids[service] or service in by_service):
                raise DockerAdapterError("container_ownership_rejected")
            by_service[service] = row
        if set(by_service) != SERVICES:
            raise DockerAdapterError("container_ownership_rejected")
        return by_service

    def _expected_mounts(self, generation_id):
        engine = str(self.config.store / "generations" / generation_id)
        return {
            "api": {(str(self.config.data), "/var/lib/ultimate-slicer", False),
                    (engine, "/engine", True), (str(self.config.token), "/run/secrets/api-token", True),
                    (str(self.config.tls), "/run/tls", True),
                    (str(self.config.profiles), "/var/lib/ultimate-slicer-profiles", True)},
            "worker": {(str(self.config.data), "/var/lib/ultimate-slicer", False),
                       (engine, "/engine", True),
                       (str(self.config.profiles), "/var/lib/ultimate-slicer-profiles", True)},
        }

    def _verify(self, rows, generation_id, *, running):
        ids = {service: rows[service]["Id"] for service in SERVICES}
        mounts = self._expected_mounts(generation_id)
        for service, row in rows.items():
            host = row.get("HostConfig", {})
            config = row.get("Config", {})
            state = row.get("State", {})
            actual_mounts = {(m.get("Source"), m.get("Destination"), not bool(m.get("RW")))
                             for m in row.get("Mounts", []) if m.get("Type") == "bind"}
            if (row.get("Image") != self.config.image_id or config.get("User") != "65532:65532"
                    or state.get("Running") is not running or actual_mounts != mounts[service]
                    or host.get("ReadonlyRootfs") is not True
                    or "ALL" not in (host.get("CapDrop") or [])
                    or "no-new-privileges:true" not in (host.get("SecurityOpt") or [])
                    or host.get("RestartPolicy", {}).get("Name") != "no"
                    or type(host.get("PidsLimit")) is not int or not 0 < host["PidsLimit"] <= 128):
                raise DockerAdapterError("runtime_contract_rejected")
        api, worker = rows["api"], rows["worker"]
        expected_port = {"8099/tcp": [{"HostIp": self.config.bind,
                                        "HostPort": str(self.config.port)}]}
        if (api["HostConfig"].get("Init") is not True
                or api["HostConfig"].get("Privileged") is not False
                or api["HostConfig"].get("PublishAllPorts") is not False
                or api["HostConfig"].get("PortBindings") != expected_port
                or api["HostConfig"].get("NetworkMode") in ("", "none", "host")
                or worker["HostConfig"].get("Privileged") is not False
                or worker["HostConfig"].get("NetworkMode") != "none"
                or worker["HostConfig"].get("PidMode") != "container:" + ids["api"]):
            raise DockerAdapterError("isolation_contract_rejected")
        binding = {"generation_id": generation_id, "image_id": self.config.image_id,
                   "compose_sha256": self.config.compose_sha256,
                   "volume_sha256": self.config.volume_sha256}
        return {"binding": binding, "containers": ids, "running": running,
                "mounts_verified": True, "isolation_verified": True}

    def snapshot(self):
        ids = self._list(self._active_generation_hint())
        rows = self._inspect(ids, self._active_generation_hint())
        generation = self._generation_from_mount(rows["api"])
        return self._verify(rows, generation, running=self._pair_running(rows))

    @staticmethod
    def _pair_running(rows):
        states = [rows[service].get("State", {}) for service in ("api", "worker")]
        values = [state.get("Running") for state in states]
        if (any(type(value) is not bool for value in values)
                or values[0] is not values[1]
                or any(state.get(flag) is True for state in states
                       for flag in ("Paused", "Restarting", "Dead"))):
            raise DockerAdapterError("partial_runtime_reconciliation_required")
        return values[0]

    def _active_record(self, *, optional=False):
        path = self.config.store / "ACTIVE.json"
        if optional and not os.path.lexists(path):
            return None
        active = _regular(path)
        info = active.lstat()
        if info.st_size > 4096:
            raise DockerAdapterError("invalid_active_generation")
        fd = os.open(active, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                     | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                    or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or opened.st_size > 4096
                    or (os.name == "posix" and
                        (opened.st_uid != info.st_uid or opened.st_mode & 0o022))):
                raise DockerAdapterError("invalid_active_generation")
            data = stream.read(4097)
        def unique(pairs):
            row = {}
            for key, item in pairs:
                if key in row:
                    raise ValueError()
                row[key] = item
            return row
        try:
            value = json.loads(data, object_pairs_hook=unique)
        except (ValueError, UnicodeError, RecursionError):
            raise DockerAdapterError("invalid_active_generation") from None
        if (len(data) > 4096 or type(value) is not dict
                or set(value) != {"schema", "generation_id"}
                or type(value["schema"]) is not int or value["schema"] != 1
                or type(value["generation_id"]) is not str
                or GENERATION.fullmatch(value["generation_id"]) is None):
            raise DockerAdapterError("invalid_active_generation")
        _directory(self.config.store / "generations" / value["generation_id"])
        return value

    def _active_generation_hint(self):
        return self._active_record()["generation_id"]

    def _generation_from_mount(self, row):
        roots = [m.get("Source") for m in row.get("Mounts", []) if m.get("Destination") == "/engine"]
        if len(roots) != 1:
            raise DockerAdapterError("runtime_contract_rejected")
        path = Path(roots[0])
        expected = self.config.store / "generations"
        if path.parent != expected or GENERATION.fullmatch(path.name or "") is None:
            raise DockerAdapterError("runtime_contract_rejected")
        _directory(path)
        return path.name

    def pause(self, request_id):
        self._maintenance("maintenance-begin", request_id)

    def paused(self, request_id):
        value = self._maintenance_record()
        return value is not None and value["request_id"] == request_id

    def stop(self, proof):
        generation = proof["binding"]["generation_id"]
        if self._list(generation) != proof["containers"]:
            raise DockerAdapterError("container_ownership_rejected")
        rows = self._inspect(proof["containers"], generation)
        running = self._pair_running(rows)
        fresh = self._verify(rows, generation, running=running)
        if fresh["binding"] != proof["binding"]:
            raise DockerAdapterError("runtime_binding_rejected")
        if not running:
            return  # Exact owned pair already stopped; do not repeat a mutation.
        self._run((self.config.docker, "container", "stop", "--time", "60",
                   proof["containers"]["worker"], proof["containers"]["api"]),
                  generation_id=generation, timeout=75)

    def stopped(self, proof):
        try:
            rows = self._inspect(proof["containers"], proof["binding"]["generation_id"])
            if self._list(proof["binding"]["generation_id"]) != proof["containers"]:
                return False
            if self._pair_running(rows) is not False:
                return False
            fresh = self._verify(rows, proof["binding"]["generation_id"], running=False)
            return fresh["binding"] == proof["binding"]
        except DockerAdapterError:
            return False

    def remove(self, proof):
        """Remove only the freshly reverified owned stopped API/worker pair."""
        generation = proof["binding"]["generation_id"]
        if self.stopped(proof) is not True:
            raise DockerAdapterError("owned_containers_not_stopped")
        if self._list(generation) != proof["containers"]:
            raise DockerAdapterError("container_ownership_rejected")
        self._run((self.config.docker, "container", "rm",
                   proof["containers"]["worker"], proof["containers"]["api"]),
                  generation_id=generation, timeout=30)
        if self._inventory():
            raise DockerAdapterError("container_removal_unverified")

    def bootstrap_runtime(self, expected):
        """Return exact owned runtime proof during journal-bound first-install recovery."""
        if (type(expected) is not dict or set(expected) !=
                {"generation_id", "image_id", "compose_sha256", "volume_sha256"}
                or expected.get("image_id") != self.config.image_id
                or expected.get("compose_sha256") != self.config.compose_sha256
                or expected.get("volume_sha256") != self.config.volume_sha256
                or GENERATION.fullmatch(expected.get("generation_id") or "") is None):
            raise DockerAdapterError("runtime_binding_rejected")
        active = self._active_record(optional=True)
        if active is not None and active["generation_id"] != expected["generation_id"]:
            raise DockerAdapterError("unexpected_active_generation")
        inventory = self._inventory()
        if set(inventory) - SERVICES:
            raise DockerAdapterError("unexpected_project_containers")
        if not inventory:
            if self._inventory() or self._active_record(optional=True) != active:
                raise DockerAdapterError("installation_observation_changed")
            return None
        if set(inventory) != SERVICES:
            raise DockerAdapterError("partial_runtime_reconciliation_required")
        rows = self._inspect(inventory, expected["generation_id"])
        proof = self._verify(rows, expected["generation_id"],
                             running=self._pair_running(rows))
        if proof["binding"] != expected:
            raise DockerAdapterError("runtime_binding_rejected")
        if self._inventory() != inventory or self._active_record(optional=True) != active:
            raise DockerAdapterError("installation_observation_changed")
        return proof

    def prepare_first_install(self, expected, request_id):
        """Create only the durable dispatch barrier using the fixed data-init service.

        Caller must already hold its durable bootstrap journal/lock and verified
        the package candidate. This method never starts API/worker or pulls an
        image. A lost reply can be retried only with the journal's same request ID.
        """
        if (type(request_id) is not str
                or re.fullmatch(r"[a-f0-9]{32}", request_id) is None):
            raise DockerAdapterError("invalid_bootstrap_request")
        if (type(expected) is not dict or set(expected) != {
                "generation_id", "image_id", "compose_sha256", "volume_sha256"}
                or expected.get("image_id") != self.config.image_id
                or expected.get("compose_sha256") != self.config.compose_sha256
                or expected.get("volume_sha256") != self.config.volume_sha256
                or type(expected.get("generation_id")) is not str
                or GENERATION.fullmatch(expected["generation_id"]) is None):
            raise DockerAdapterError("runtime_binding_rejected")
        state = self.installation_state()
        if state["state"] != "empty" or state["installation_permitted"] is not False:
            raise DockerAdapterError("first_install_runtime_not_empty")
        generation_id = expected["generation_id"]
        argv = (self.config.docker, "compose", "--project-name", self.config.project,
                "--file", str(self.config.compose), "run", "--rm", "--no-deps",
                "-T", "data-init")
        self._run(argv, generation_id=generation_id, timeout=120,
                  extra_env={"SLICER_BOOTSTRAP_REQUEST_ID": request_id},
                  require_engine=False)
        if self._active_record(optional=True) is not None or self._inventory():
            raise DockerAdapterError("first_install_runtime_changed")
        marker = self._maintenance_record()
        if type(marker) is not dict or marker.get("request_id") != request_id:
            raise DockerAdapterError("bootstrap_barrier_unverified")
        return {"state": "first_install_maintenance",
                "request_id": request_id, "dispatch_blocked": True,
                "runtime_absent": True}

    def clear_first_install(self, request_id, generation_id):
        """Clear the owned offline barrier after runtime and ACTIVE are absent."""
        if (re.fullmatch(r"[a-f0-9]{32}", request_id or "") is None
                or GENERATION.fullmatch(generation_id or "") is None):
            raise DockerAdapterError("invalid_bootstrap_request")
        if self._active_record(optional=True) is not None or self._inventory():
            raise DockerAdapterError("first_install_runtime_not_empty")
        marker = self._maintenance_record()
        if marker is None or marker["request_id"] != request_id:
            raise DockerAdapterError("maintenance_proof_rejected")
        argv = (self.config.docker, "compose", "--project-name", self.config.project,
                "--file", str(self.config.compose), "run", "--rm", "--no-deps",
                "-T", "maintenance-clear")
        self._run(argv, generation_id=generation_id, timeout=120,
                  extra_env={"SLICER_BOOTSTRAP_REQUEST_ID": request_id})
        if self._maintenance_record() is not None:
            raise DockerAdapterError("maintenance_clear_unverified")
        if self._active_record(optional=True) is not None or self._inventory():
            raise DockerAdapterError("first_install_runtime_changed")

    def start(self, expected):
        generation = expected["generation_id"]
        if (expected.get("image_id") != self.config.image_id
                or expected.get("compose_sha256") != self.config.compose_sha256
                or expected.get("volume_sha256") != self.config.volume_sha256):
            raise DockerAdapterError("runtime_binding_rejected")
        self._run((self.config.docker, "compose", "--project-name", self.config.project,
                   "--file", str(self.config.compose), "up", "--detach", "--no-build",
                   "--pull", "never", "--wait", "--wait-timeout", "90", "api", "worker"),
                  generation_id=generation, timeout=120)

    def health(self, expected):
        generation = expected["generation_id"]
        ids = self._list(generation)
        rows = self._inspect(ids, generation)
        proof = self._verify(rows, generation, running=True)
        worker = rows["worker"].get("State", {}).get("Health", {}).get("Status")
        if worker != "healthy":
            raise DockerAdapterError("worker_health_rejected")
        maintenance = self._maintenance_record()
        request_id = maintenance.get("request_id") if maintenance else None
        if re.fullmatch(r"[a-f0-9]{32}", request_id or "") is None:
            raise DockerAdapterError("maintenance_proof_rejected")
        if self.api_probe() is not True:
            raise DockerAdapterError("api_tls_authentication_rejected")
        return {"runtime": proof, "api_tls_authenticated": True,
                "worker_healthy": True, "maintenance_id": request_id}

    def resume(self, request_id):
        self._maintenance("maintenance-end", request_id)

    def resumed(self, request_id):
        return self._maintenance_record() is None

    def _maintenance_record(self):
        path = self.config.data / "run" / "container-maintenance.json"
        if not os.path.lexists(path):
            return None
        try:
            _regular(path, private=True)
            info = path.lstat()
            if (info.st_size > 4096 or
                    (os.name == "posix" and stat.S_IMODE(info.st_mode) != 0o600)):
                raise DockerAdapterError("maintenance_proof_rejected")
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0))
            with os.fdopen(fd, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if ((opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
                        or not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                        or opened.st_size > 4096
                        or (os.name == "posix" and
                            (opened.st_uid != info.st_uid or
                             stat.S_IMODE(opened.st_mode) != 0o600))):
                    raise DockerAdapterError("maintenance_proof_rejected")
                raw = stream.read(4097)
            if len(raw) > 4096:
                raise DockerAdapterError("maintenance_proof_rejected")
            def unique(pairs):
                value = {}
                for key, item in pairs:
                    if key in value:
                        raise ValueError("duplicate_field")
                    value[key] = item
                return value
            value = json.loads(raw, object_pairs_hook=unique)
        except (OSError, ValueError, UnicodeError, RecursionError):
            raise DockerAdapterError("maintenance_proof_rejected") from None
        if (type(value) is not dict or set(value) != {"schema", "request_id", "state"}
                or type(value["schema"]) is not int or value["schema"] != 1
                or value["state"] != "maintenance"
                or type(value["request_id"]) is not str
                or re.fullmatch(r"[a-f0-9]{32}", value["request_id"]) is None):
            raise DockerAdapterError("maintenance_proof_rejected")
        return value

    def _maintenance(self, operation, request_id, *, generation=None, ids=None):
        generation = generation or self._active_generation_hint()
        ids = ids or self._list(generation)
        argv = [self.config.docker, "container", "exec", "--user", "65532:65532",
                ids["api"], "python3", "/opt/ultimate-slicer-server/container_service.py",
                operation]
        if request_id is not None:
            if re.fullmatch(r"[a-f0-9]{32}", request_id or "") is None:
                raise DockerAdapterError("invalid_request_id")
            argv += ["--request-id", request_id]
        output = self._run(tuple(argv), generation_id=generation, timeout=15)
        lines = [line for line in output.splitlines() if line.strip()]
        if len(lines) != 1 or type((value := _json(lines[0]))) is not dict:
            raise DockerAdapterError("invalid_maintenance_response")
        return value

    def _probe_api(self):
        cert = _regular(self.config.tls / "server.crt")
        token = _regular(self.config.token, private=True).read_bytes()
        if token.endswith(b"\r\n"):
            token = token[:-2]
        elif token.endswith(b"\n"):
            token = token[:-1]
        if not 32 <= len(token) <= 256 or any(c < 33 or c > 126 for c in token):
            raise DockerAdapterError("invalid_api_token")
        context = ssl.create_default_context(cafile=str(cert))
        request = urllib.request.Request(
            f"https://{self.config.api_host}:{self.config.port}/api/v1/info",
            headers={"Authorization": "Bearer " + token.decode("ascii")})
        try:
            with urllib.request.urlopen(request, timeout=10, context=context) as response:
                if response.status != 200:
                    raise DockerAdapterError("api_tls_authentication_rejected")
                raw = response.read(MAX_HTTP + 1)
        except DockerAdapterError:
            raise
        except Exception:
            raise DockerAdapterError("api_tls_authentication_rejected") from None
        if len(raw) > MAX_HTTP:
            raise DockerAdapterError("api_response_limit")
        value = _json(raw)
        capabilities = value.get("capabilities") if type(value) is dict else None
        if (type(value) is not dict or type(value.get("api_version")) is not int
                or value["api_version"] != 2 or type(value.get("version")) is not str
                or not value["version"] or type(capabilities) is not dict
                or capabilities.get("job_cancellation") is not True
                or type(capabilities.get("cancellation_contract")) is not int
                or capabilities["cancellation_contract"] != 1):
            raise DockerAdapterError("api_contract_rejected")
        return True

