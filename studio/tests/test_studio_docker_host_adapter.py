"""Synthetic fixed-Docker adapter tests; never contact a Docker daemon."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Slicer-Server"))
import docker_host_adapter as docker

OLD = "g-" + "1" * 64
NEW = "g-" + "2" * 64
IMAGE = "sha256:" + "3" * 64
VOLUME = "4" * 64
IDENT = "a" * 32


class FakeRunner:
    def __init__(self, config):
        self.config = config
        self.generation = OLD
        self.ids = {"api": "5" * 64, "worker": "6" * 64}
        self.running = True
        self.healthy = True
        self.partial = False
        self.present = True
        self.bad = None
        self.calls = []

    def rows(self):
        engine = str(self.config.store / "generations" / self.generation)
        common = {"Config": {"User": "65532:65532"},
                  "State": {"Running": self.running},
                  "HostConfig": {"ReadonlyRootfs": True, "CapDrop": ["ALL"],
                      "SecurityOpt": ["no-new-privileges:true"], "PidsLimit": 128,
                      "RestartPolicy": {"Name": "no"}}}
        api = copy.deepcopy(common)
        api.update({"Id": self.ids["api"], "Image": IMAGE,
            "Mounts": [self.mount(self.config.data, "/var/lib/ultimate-slicer", True),
                       self.mount(engine, "/engine", False),
                       self.mount(self.config.token, "/run/secrets/api-token", False),
                       self.mount(self.config.tls, "/run/tls", False),
                       self.mount(self.config.profiles, "/var/lib/ultimate-slicer-profiles", False)]})
        api["Config"]["Labels"] = {"com.docker.compose.project": self.config.project,
                                    "com.docker.compose.service": "api"}
        api["HostConfig"].update({"Init": True, "NetworkMode": "project_default", "PidMode": "",
            "Privileged": False, "PublishAllPorts": False,
            "PortBindings": {"8099/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8099"}]}})
        worker = copy.deepcopy(common)
        worker.update({"Id": self.ids["worker"], "Image": IMAGE,
            "Mounts": [self.mount(self.config.data, "/var/lib/ultimate-slicer", True),
                       self.mount(engine, "/engine", False),
                       self.mount(self.config.profiles, "/var/lib/ultimate-slicer-profiles", False)]})
        worker["Config"]["Labels"] = {"com.docker.compose.project": self.config.project,
                                       "com.docker.compose.service": "worker"}
        worker["HostConfig"].update({"Init": False, "NetworkMode": "none", "Privileged": False,
                                     "PidMode": "container:" + self.ids["api"]})
        if self.healthy:
            worker["State"]["Health"] = {"Status": "healthy"}
        if self.bad == "image":
            worker["Image"] = "sha256:" + "f" * 64
        elif self.bad == "mount":
            worker["Mounts"][0]["Source"] = str(self.config.data.parent / "foreign")
        elif self.bad == "isolation":
            worker["HostConfig"]["NetworkMode"] = "bridge"
        return [api, worker]

    @staticmethod
    def mount(source, target, writable):
        return {"Type": "bind", "Source": str(source), "Destination": target, "RW": writable}

    def __call__(self, argv, *, env, timeout):
        self.calls.append((argv, dict(env), timeout))
        if argv[1:3] == ("container", "ls"):
            if not self.present:
                return docker.Result(0, b"", b"")
            lines = [self.ids["api"] + " api"]
            if not self.partial:
                lines.append(self.ids["worker"] + " worker")
            return docker.Result(0, ("\n".join(lines) + "\n").encode(), b"")
        if argv[1:3] == ("container", "inspect"):
            return docker.Result(0, json.dumps(self.rows()).encode(), b"")
        if argv[1:3] == ("container", "stop"):
            self.running = False
            return docker.Result(0, b"", b"")
        if argv[1:3] == ("container", "rm"):
            if self.running:
                raise AssertionError("running container removal")
            self.present = False
            return docker.Result(0, b"", b"")
        if argv[1] == "compose" and "run" in argv:
            service = argv[-1]
            if service not in ("data-init", "maintenance-clear") or "--no-deps" not in argv or "--rm" not in argv:
                raise AssertionError(argv)
            ident = env.get("SLICER_BOOTSTRAP_REQUEST_ID")
            if not ident or len(ident) != 32:
                raise AssertionError("missing bootstrap request")
            path = self.config.data / "run" / "container-maintenance.json"
            if service == "data-init":
                path.write_text(json.dumps({"schema": 1, "request_id": ident,
                                            "state": "maintenance"}))
                path.chmod(0o600)
                if getattr(self, "lose_bootstrap_reply", False):
                    self.lose_bootstrap_reply = False
                    raise OSError("synthetic lost helper receipt")
            else:
                value = json.loads(path.read_text())
                if value.get("request_id") != ident:
                    raise AssertionError("foreign maintenance owner")
                path.unlink()
            return docker.Result(0, b"", b"")
        if argv[1] == "compose":
            self.generation = Path(env["SLICER_ENGINE"]).name
            self.present = True
            self.ids = {"api": "7" * 64, "worker": "8" * 64}
            self.running = True
            self.healthy = True
            return docker.Result(0, b"", b"")
        if argv[1:3] == ("container", "exec"):
            operation = argv[8]
            marker = self.config.data / "run" / "container-maintenance.json"
            if operation == "maintenance-begin":
                ident = argv[10]
                marker.write_text(json.dumps({"schema": 1, "request_id": ident,
                                               "state": "maintenance"}))
                marker.chmod(0o600)
                value = {"event": operation, "state": "maintenance", "request_id": ident}
            elif operation == "maintenance-end":
                ident = argv[10]
                marker.unlink()
                value = {"event": operation, "state": "resumed", "request_id": ident}
            else:
                raise AssertionError(argv)
            return docker.Result(0, (json.dumps(value) + "\n").encode(), b"")
        raise AssertionError(argv)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("store/generations/" + OLD, "store/generations/" + NEW,
                     "data/run", "profiles", "tls"):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        (self.root / "store/ACTIVE.json").write_text(json.dumps(
            {"schema": 1, "generation_id": OLD}))
        self.compose = self.root / "compose.json"
        self.compose.write_text("{}")
        self.token = self.root / "token"
        self.token.write_text("x" * 43)
        self.token.chmod(0o600)
        self.config = docker.FixedDockerConfig(
            docker="/usr/bin/docker", compose=self.compose,
            compose_sha256=hashlib.sha256(b"{}").hexdigest(), project="ultimate-slicer-server",
            image_id=IMAGE, store=self.root / "store", data=self.root / "data",
            profiles=self.root / "profiles", token=self.token, tls=self.root / "tls",
            bind="127.0.0.1", port=8099, api_host="slicer.example.invalid",
            volume_sha256=VOLUME)
        self.runner = FakeRunner(self.config)
        self.adapter = docker.DockerHostAdapter(self.config, runner=self.runner,
                                                api_probe=lambda: True)

    def marker(self, ident=IDENT):
        path = self.config.data / "run/container-maintenance.json"
        path.write_text(json.dumps({"schema": 1, "request_id": ident,
                                    "state": "maintenance"}))
        path.chmod(0o600)

    def test_snapshot_returns_exact_binding_and_container_ids(self):
        value = self.adapter.snapshot()
        self.assertEqual(value["binding"]["generation_id"], OLD)
        self.assertEqual(value["containers"], self.runner.ids)
        self.assertTrue(value["mounts_verified"])
        self.assertTrue(value["isolation_verified"])

    def test_pause_proves_exact_durable_marker_and_resume_removes_it(self):
        self.adapter.pause(IDENT)
        self.assertTrue(self.adapter.paused(IDENT))
        self.assertFalse(self.adapter.paused("b" * 32))
        self.adapter.resume(IDENT)
        self.assertTrue(self.adapter.resumed(IDENT))
        commands = [call[0] for call in self.runner.calls]
        self.assertTrue(any("65532:65532" in command for command in commands))

    def test_stop_only_exact_owned_ids_then_proves_stopped(self):
        proof = self.adapter.snapshot()
        self.adapter.stop(proof)
        self.assertTrue(self.adapter.stopped(proof))
        stop = [c[0] for c in self.runner.calls if c[0][1:3] == ("container", "stop")][0]
        self.assertEqual(stop[-2:], (proof["containers"]["worker"], proof["containers"]["api"]))

    def test_start_binds_generation_and_health_rechecks_every_contract(self):
        self.marker()
        target = {"generation_id": NEW, "image_id": IMAGE,
                  "compose_sha256": self.config.compose_sha256, "volume_sha256": VOLUME}
        self.adapter.start(target)
        value = self.adapter.health(target)
        self.assertEqual(value["runtime"]["binding"], target)
        self.assertEqual(value["maintenance_id"], IDENT)
        compose = [c for c in self.runner.calls if c[0][1] == "compose"][0]
        self.assertIn("--no-build", compose[0])
        self.assertIn("never", compose[0])
        self.assertEqual(compose[1]["SLICER_ENGINE"], str(self.config.store / "generations" / NEW))

    def test_partial_start_is_reconciliation_not_an_empty_runtime(self):
        self.runner.partial = True
        with self.assertRaisesRegex(docker.DockerAdapterError, "partial_runtime"):
            self.adapter.snapshot()

    def test_wrong_image_mount_or_kernel_contract_is_rejected(self):
        for bad in ("image", "mount", "isolation"):
            with self.subTest(bad=bad):
                self.runner.bad = bad
                with self.assertRaises(docker.DockerAdapterError):
                    self.adapter.snapshot()
        self.runner.bad = None

    def test_unhealthy_worker_and_missing_or_foreign_marker_fail_health(self):
        target = {"generation_id": OLD, "image_id": IMAGE,
                  "compose_sha256": self.config.compose_sha256, "volume_sha256": VOLUME}
        self.runner.healthy = False
        with self.assertRaisesRegex(docker.DockerAdapterError, "worker_health"):
            self.adapter.health(target)
        self.runner.healthy = True
        with self.assertRaisesRegex(docker.DockerAdapterError, "maintenance_proof"):
            self.adapter.health(target)
        self.marker("b" * 32)
        self.assertEqual(self.adapter.health(target)["maintenance_id"], "b" * 32)

    def test_binding_mismatch_never_starts_compose(self):
        target = {"generation_id": NEW, "image_id": "sha256:" + "f" * 64,
                  "compose_sha256": self.config.compose_sha256, "volume_sha256": VOLUME}
        with self.assertRaisesRegex(docker.DockerAdapterError, "binding_rejected"):
            self.adapter.start(target)
        self.assertFalse(any(c[0][1] == "compose" for c in self.runner.calls))

    def test_config_rejects_mutable_identity_and_nonlocal_bind(self):
        with self.assertRaises(docker.DockerAdapterError):
            docker.DockerHostAdapter(docker.FixedDockerConfig(
                **{**self.config.__dict__, "image_id": "latest"}), runner=self.runner)
        with self.assertRaises(docker.DockerAdapterError):
            docker.DockerHostAdapter(docker.FixedDockerConfig(
                **{**self.config.__dict__, "bind": "0.0.0.0"}), runner=self.runner)
        self.compose.write_text("changed")
        with self.assertRaisesRegex(docker.DockerAdapterError, "compose_digest"):
            docker.DockerHostAdapter(self.config, runner=self.runner)

    def test_invalid_active_and_linked_generation_are_rejected(self):
        (self.config.store / "ACTIVE.json").write_text("{}")
        with self.assertRaisesRegex(docker.DockerAdapterError, "active_generation"):
            self.adapter.snapshot()

    def test_tls_probe_uses_server_side_token_and_exact_protocol_contract(self):
        (self.config.tls / "server.crt").write_text("synthetic certificate")
        good = {"version": "1.2.3", "api_version": 2,
                "capabilities": {"job_cancellation": True, "cancellation_contract": 1}}

        class Response:
            status = 200
            def __init__(self, value):self.value = value
            def __enter__(self):return self
            def __exit__(self, *_):return False
            def read(self, _):return json.dumps(self.value).encode()

        with patch.object(docker.ssl, "create_default_context", return_value=object()), \
                patch.object(docker.urllib.request, "urlopen", return_value=Response(good)) as call:
            self.assertTrue(self.adapter._probe_api())
            request = call.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer " + "x" * 43)
        for value in ({**good, "api_version": 3}, {**good, "capabilities": {}}, []):
            with self.subTest(value=value), \
                    patch.object(docker.ssl, "create_default_context", return_value=object()), \
                    patch.object(docker.urllib.request, "urlopen", return_value=Response(value)):
                with self.assertRaisesRegex(docker.DockerAdapterError, "api_contract"):
                    self.adapter._probe_api()

    @unittest.skipUnless(os.name == "posix", "bounded subprocess behavior")
    def test_bounded_runner_enforces_output_and_timeout(self):
        runner = docker.BoundedRunner(1024)
        with self.assertRaisesRegex(docker.DockerAdapterError, "output_limit"):
            runner((sys.executable, "-c", "print('x'*2000)"), env=dict(os.environ), timeout=5)
        with self.assertRaisesRegex(docker.DockerAdapterError, "timeout"):
            runner((sys.executable, "-c", "import time;time.sleep(2)"),
                   env=dict(os.environ), timeout=.05)


    def inventory_override(self, output):
        original = self.runner
        def run(argv, *, env, timeout):
            if argv[1:3] == ("container", "ls"):
                original.calls.append((argv, dict(env), timeout))
                return docker.Result(0, output, b"")
            return original(argv, env=env, timeout=timeout)
        self.adapter.runner = run

    def assert_read_only(self):
        self.assertTrue(all(call[0][1:3] in
                            (("container", "ls"), ("container", "inspect"))
                            for call in self.runner.calls))

    def test_installation_observation_empty_without_active_or_generation(self):
        (self.config.store / "ACTIVE.json").unlink()
        for path in (self.config.store / "generations").iterdir():
            path.rmdir()
        self.inventory_override(b"")
        self.assertEqual(self.adapter.installation_state(),
                         {"state": "empty", "runtime": None, "installation_permitted": False})
        self.assertEqual(len(self.runner.calls), 2)
        self.assert_read_only()
        self.assertFalse((self.config.store / "ACTIVE.json").exists())

    def test_installation_observation_running_and_stopped_are_not_readiness(self):
        for running, state in ((True, "running"), (False, "stopped")):
            with self.subTest(running=running):
                self.runner.running = running
                self.runner.healthy = False  # Inventory does not claim health.
                value = self.adapter.installation_state()
                self.assertEqual(value["state"], state)
                self.assertEqual(value["runtime"]["containers"], self.runner.ids)
                self.assertFalse(value["installation_permitted"])
                self.assert_read_only()

    def test_installation_observation_missing_runtime_is_not_first_install(self):
        self.inventory_override(b"")
        with self.assertRaisesRegex(docker.DockerAdapterError, "runtime_store_reconciliation"):
            self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_missing_active_with_runtime_requires_recovery(self):
        (self.config.store / "ACTIVE.json").unlink()
        with self.assertRaisesRegex(docker.DockerAdapterError, "runtime_store_reconciliation"):
            self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_partial_pair_blocks_with_and_without_active(self):
        self.runner.partial = True
        for active in (True, False):
            if not active:
                (self.config.store / "ACTIVE.json").unlink()
            with self.subTest(active=active), self.assertRaisesRegex(
                    docker.DockerAdapterError, "partial_runtime"):
                self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_unknown_project_helpers_block(self):
        (self.config.store / "ACTIVE.json").unlink()
        for service in ("profile-init", "data-init", "foreign"):
            self.inventory_override(("9" * 64 + " " + service + "\n").encode())
            with self.subTest(service=service), self.assertRaisesRegex(
                    docker.DockerAdapterError, "unexpected_project"):
                self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_inventory_duplicates_and_malformed_fail_closed(self):
        (self.config.store / "ACTIVE.json").unlink()
        valid = "5" * 64 + " api\n"
        for raw in (b"\xff", b"\n", b"bad api\n", valid.encode() * 2,
                    (valid + "5" * 64 + " worker\n").encode(),
                    ("5" * 64 + " \n").encode()):
            with self.subTest(raw=raw):
                self.inventory_override(raw)
                with self.assertRaises(docker.DockerAdapterError):
                    self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_daemon_failure_never_means_empty(self):
        (self.config.store / "ACTIVE.json").unlink()
        for result in (docker.Result(1, b"", b"private detail"), TimeoutError()):
            def run(*args, **kwargs):
                if isinstance(result, Exception):
                    raise result
                return result
            self.adapter.runner = run
            with self.subTest(result=type(result).__name__), self.assertRaises(
                    (docker.DockerAdapterError, TimeoutError)):
                self.adapter.installation_state()

    def test_installation_observation_active_json_strict_and_bounded(self):
        path = self.config.store / "ACTIVE.json"
        for raw in ('[]', 'null', '{"schema":true,"generation_id":"' + OLD + '"}',
                    '{"schema":1,"schema":1,"generation_id":"' + OLD + '"}',
                    '{"schema":1,"generation_id":7}', " " * 4097):
            with self.subTest(raw=raw[:80]):
                path.write_text(raw)
                with self.assertRaisesRegex(docker.DockerAdapterError, "invalid_active"):
                    self.adapter.installation_state()
        self.assertEqual(self.runner.calls, [])

    def test_installation_observation_active_references_missing_generation(self):
        (self.config.store / "generations" / OLD).rmdir()
        with self.assertRaises(docker.DockerAdapterError):
            self.adapter.installation_state()
        self.assertEqual(self.runner.calls, [])

    def test_installation_observation_inventory_change_during_probe_blocks(self):
        original = self.runner
        count = 0
        def run(argv, *, env, timeout):
            nonlocal count
            if argv[1:3] == ("container", "ls"):
                count += 1
                if count == 2:
                    return docker.Result(0, b"", b"")
            return original(argv, env=env, timeout=timeout)
        self.adapter.runner = run
        with self.assertRaisesRegex(docker.DockerAdapterError, "observation_changed"):
            self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_active_change_during_probe_blocks(self):
        original = self.runner
        def run(argv, *, env, timeout):
            result = original(argv, env=env, timeout=timeout)
            if argv[1:3] == ("container", "inspect"):
                (self.config.store / "ACTIVE.json").write_text(json.dumps(
                    {"schema": 1, "generation_id": NEW}))
            return result
        self.adapter.runner = run
        with self.assertRaisesRegex(docker.DockerAdapterError, "observation_changed"):
            self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_existing_contract_mismatch_blocks(self):
        for bad in ("image", "mount", "isolation"):
            with self.subTest(bad=bad):
                self.runner.bad = bad
                with self.assertRaises(docker.DockerAdapterError):
                    self.adapter.installation_state()
        self.assert_read_only()

    def test_installation_observation_changed_compose_blocks_before_daemon(self):
        self.compose.write_text("changed")
        with self.assertRaisesRegex(docker.DockerAdapterError, "compose_digest"):
            self.adapter.installation_state()
        self.assertEqual(self.runner.calls, [])

    @unittest.skipUnless(os.name == "posix", "POSIX link and special file proof")
    def test_installation_observation_dangling_active_and_fifo_are_not_absence(self):
        path = self.config.store / "ACTIVE.json"
        path.unlink()
        path.symlink_to(self.root / "missing")
        with self.assertRaises(docker.DockerAdapterError):
            self.adapter.installation_state()
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(docker.DockerAdapterError):
            self.adapter.installation_state()
        self.assertEqual(self.runner.calls, [])

    def target_binding(self):
        return {"generation_id": NEW, "image_id": IMAGE,
                "compose_sha256": self.config.compose_sha256, "volume_sha256": VOLUME}

    def test_prepare_first_install_allows_generation_to_be_inactive_and_not_copied_yet(self):
        (self.config.store / "ACTIVE.json").unlink()
        (self.config.store / "generations" / NEW).rmdir()
        self.inventory_override(b"")
        result = self.adapter.prepare_first_install(self.target_binding(), IDENT)
        self.assertEqual(result["state"], "first_install_maintenance")
        compose = [call for call in self.runner.calls if call[0][1] == "compose"]
        self.assertEqual(len(compose), 1)
        self.assertEqual(
            compose[0][1]["SLICER_ENGINE"],
            str(self.config.store / "generations" / NEW))
        self.assertFalse((self.config.store / "generations" / NEW).exists())

    def test_prepare_first_install_runs_only_fixed_data_initializer_and_verifies_barrier(self):
        (self.config.store / "ACTIVE.json").unlink()
        self.inventory_override(b"")
        result = self.adapter.prepare_first_install(self.target_binding(), IDENT)
        self.assertEqual(result, {"state": "first_install_maintenance",
                                  "request_id": IDENT, "dispatch_blocked": True,
                                  "runtime_absent": True})
        calls = [c[0] for c in self.runner.calls if c[0][1] == "compose"]
        self.assertEqual(len(calls), 1)
        argv = calls[0]
        self.assertIn("run", argv)
        self.assertIn("data-init", argv)
        self.assertNotIn("up", argv)
        env = [c[1] for c in self.runner.calls if c[0] == argv][0]
        self.assertEqual(env["SLICER_BOOTSTRAP_REQUEST_ID"], IDENT)
        self.assertFalse(any("container" in c[0] and c[0][1:3] == ("container", "exec")
                             for c in self.runner.calls))

    def test_prepare_first_install_replay_after_lost_reply_keeps_same_barrier(self):
        (self.config.store / "ACTIVE.json").unlink()
        self.inventory_override(b"")
        self.runner.lose_bootstrap_reply = True
        with self.assertRaises(OSError):
            self.adapter.prepare_first_install(self.target_binding(), IDENT)
        marker = self.config.data / "run/container-maintenance.json"
        before = marker.read_bytes()
        result = self.adapter.prepare_first_install(self.target_binding(), IDENT)
        self.assertTrue(result["dispatch_blocked"])
        self.assertEqual(marker.read_bytes(), before)
        commands = [c[0] for c in self.runner.calls if c[0][1] == "compose"]
        self.assertEqual(len(commands), 2)
        self.assertTrue(all("data-init" in call and "up" not in call for call in commands))

    def test_prepare_first_install_rejects_invalid_request_binding_and_existing_runtime(self):
        (self.config.store / "ACTIVE.json").unlink()
        self.inventory_override(b"")
        with self.assertRaisesRegex(docker.DockerAdapterError, "invalid_bootstrap"):
            self.adapter.prepare_first_install(self.target_binding(), "../bad")
        with self.assertRaisesRegex(docker.DockerAdapterError, "binding_rejected"):
            self.adapter.prepare_first_install({**self.target_binding(), "image_id": "mutable"}, IDENT)
        self.assertEqual(self.runner.calls, [])
        (self.config.store / "ACTIVE.json").write_text(json.dumps(
            {"schema": 1, "generation_id": OLD}))
        self.adapter.runner = self.runner
        with self.assertRaisesRegex(docker.DockerAdapterError, "not_empty"):
            self.adapter.prepare_first_install(self.target_binding(), IDENT)
        self.assertFalse(any(c[0][1] == "compose" for c in self.runner.calls))

    def test_prepare_first_install_requires_marker_readback_and_no_runtime(self):
        (self.config.store / "ACTIVE.json").unlink()
        self.inventory_override(b"")
        original = self.adapter.runner
        def no_marker(argv, *, env, timeout):
            if argv[1] == "compose" and "run" in argv:
                self.runner.calls.append((argv, dict(env), timeout))
                return docker.Result(0, b"", b"")
            return original(argv, env=env, timeout=timeout)
        self.adapter.runner = no_marker
        with self.assertRaisesRegex(docker.DockerAdapterError, "bootstrap_barrier_unverified"):
            self.adapter.prepare_first_install(self.target_binding(), IDENT)
        self.assertFalse(any(c[0][1:2] == ("compose",) and "up" in c[0]
                             for c in self.runner.calls))




    def test_first_install_remove_and_offline_clear_are_exact_and_fixed(self):
        proof = self.adapter.snapshot()
        self.adapter.stop(proof)
        self.assertTrue(self.adapter.stopped(proof))
        self.adapter.remove(proof)
        self.assertFalse(self.runner.present)
        (self.config.store / "ACTIVE.json").unlink()
        marker = self.config.data / "run/container-maintenance.json"
        marker.write_text(json.dumps({"schema": 1, "request_id": IDENT,
                                      "state": "maintenance"}))
        marker.chmod(0o600)
        self.adapter.clear_first_install(IDENT, OLD)
        self.assertFalse(marker.exists())
        commands = [call[0] for call in self.runner.calls]
        self.assertTrue(any(call[1:3] == ("container", "rm") for call in commands))
        clear = [call for call in commands if call[1] == "compose" and
                 call[-1] == "maintenance-clear"]
        self.assertEqual(len(clear), 1)
        self.assertNotIn("up", clear[0])

    def test_first_install_remove_and_clear_fail_closed(self):
        proof = self.adapter.snapshot()
        with self.assertRaisesRegex(docker.DockerAdapterError,
                                    "owned_containers_not_stopped"):
            self.adapter.remove(proof)
        self.adapter.stop(proof)
        self.adapter.remove(proof)
        (self.config.store / "ACTIVE.json").unlink()
        marker = self.config.data / "run/container-maintenance.json"
        marker.write_text(json.dumps({"schema": 1, "request_id": "b" * 32,
                                      "state": "maintenance"}))
        marker.chmod(0o600)
        with self.assertRaisesRegex(docker.DockerAdapterError,
                                    "maintenance_proof_rejected"):
            self.adapter.clear_first_install(IDENT, OLD)



    def test_bootstrap_runtime_handles_active_lost_reply_and_absent_pair(self):
        expected = {"generation_id": OLD, "image_id": IMAGE,
                    "compose_sha256": self.config.compose_sha256,
                    "volume_sha256": VOLUME}
        proof = self.adapter.bootstrap_runtime(expected)
        self.assertTrue(proof["running"])
        (self.config.store / "ACTIVE.json").unlink()
        self.assertEqual(self.adapter.bootstrap_runtime(expected)["containers"], self.runner.ids)
        self.runner.present = False
        self.assertIsNone(self.adapter.bootstrap_runtime(expected))

    def test_bootstrap_runtime_rejects_foreign_binding(self):
        with self.assertRaisesRegex(docker.DockerAdapterError,
                                    "runtime_binding_rejected"):
            self.adapter.bootstrap_runtime({
                "generation_id": OLD, "image_id": "sha256:" + "9" * 64,
                "compose_sha256": self.config.compose_sha256,
                "volume_sha256": VOLUME})


if __name__ == "__main__":
    unittest.main()
