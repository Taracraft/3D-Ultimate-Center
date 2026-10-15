"""Locally provisioned installer/lifecycle/store coupling; no remote configuration."""
from pathlib import Path
import first_install as bootstrap
import host_lifecycle as lifecycle
import package_activation as activation


class InstallerLifecycle:
    """One installation with separate installer, lifecycle and store locks.

    The driver and immutable runtime binding come only from trusted provisioning.
    A missing ACTIVE/runtime pair is routed through the durable FirstInstall
    transaction; later generation changes retain the existing Lifecycle path.
    """

    def __init__(self, directory, store, driver, runtime_binding, *,
                 verify_volume, verify_exclusive_host):
        self.directory = Path(directory).absolute()
        self.store = Path(store).absolute()
        self.driver = driver
        self.verify_volume = verify_volume
        self.verify_exclusive_host = verify_exclusive_host
        if not callable(verify_volume):
            raise lifecycle.LifecycleError("missing_volume_adapter")
        if not callable(verify_exclusive_host):
            raise lifecycle.LifecycleError("missing_host_exclusivity_adapter")
        self.runtime_binding = lifecycle.binding(
            {**runtime_binding, "generation_id": "g-" + "0" * 64})
        self.runtime_binding.pop("generation_id")
        if set(runtime_binding) != set(self.runtime_binding):
            raise lifecycle.LifecycleError("invalid_runtime_binding")
        if self._overlap(self.directory, self.store):
            raise lifecycle.LifecycleError("control_store_overlap")
        lifecycle._private_directory(self.directory)
        self.first_install_directory = self.directory / "first-install"
        if not self.first_install_directory.exists():
            self.first_install_directory.mkdir(mode=0o700)
            activation._fsync_directory(self.directory)
        lifecycle._private_directory(self.first_install_directory)

    @staticmethod
    def _overlap(left, right):
        return left == right or left in right.parents or right in left.parents

    def validate_installer(self, store, control):
        if Path(store).absolute() != self.store or self._overlap(
                self.directory, Path(control).absolute()):
            raise lifecycle.LifecycleError("lifecycle_control_overlap")

    def _active(self, store_id):
        row = activation.active_generation(self.store, store_id)
        return row["generation_id"] if row else None

    def _make_first(self, request_id, store_id, candidates=None, expected=None):
        request_id = lifecycle.identifier(request_id)

        def verify_store(value):
            if value != store_id:
                return False
            activation.verify_store(self.store, store_id)
            return True

        def active():
            return self._active(store_id)

        absent_target = {"value": None if expected is None else lifecycle.binding(
            {**self.runtime_binding, "generation_id": expected})}

        def stopped_absent():
            if (self.verify_volume() is not True
                    or self.driver.paused(request_id) is not True
                    or absent_target["value"] is None):
                return False
            return self.driver.bootstrap_runtime(absent_target["value"]) is None

        def activate(generation, transaction):
            if (candidates is None or generation != expected
                    or transaction != "t-" + request_id):
                raise lifecycle.LifecycleError("candidate_not_current")
            result = activation.activate_generation(
                self.store, store_id, candidates, stopped_absent,
                transaction_id=transaction, expected_generation=generation)
            if result["generation_id"] != generation:
                raise lifecycle.LifecycleError("active_generation_mismatch")

        def deactivate(generation, transaction):
            absent_target["value"] = lifecycle.binding(
                {**self.runtime_binding, "generation_id": generation})
            activation.restore_first_install_absence(
                self.store, store_id, transaction, generation, stopped_absent)

        return bootstrap.FirstInstall(
            self.first_install_directory, self.driver,
            verify_volume=self.verify_volume, verify_store=verify_store,
            verify_exclusive_host=self.verify_exclusive_host,
            active_generation=active, activate=activate, deactivate=deactivate)

    def _make(self, request_id, store_id, candidates=None, expected=None):
        request_id = lifecycle.identifier(request_id)

        def active():
            return self._active(store_id)

        def stopped():
            if self.verify_volume() is not True or self.driver.paused(request_id) is not True:
                return False
            row = engine._load()
            if row["request_id"] != request_id:
                raise lifecycle.LifecycleError("request_id_conflict")
            proof = self.driver.snapshot()
            if proof["binding"] not in (row["previous"], row["target"]):
                raise lifecycle.LifecycleError("unexpected_runtime_binding")
            lifecycle._proof(proof, proof["binding"], running=False)
            return self.driver.stopped(proof) is True

        def activate(generation):
            if candidates is None or generation != expected:
                raise lifecycle.LifecycleError("candidate_not_current")
            result = activation.activate_generation(
                self.store, store_id, candidates, stopped,
                transaction_id="t-" + request_id, expected_generation=generation)
            if result["generation_id"] != generation:
                raise lifecycle.LifecycleError("active_generation_mismatch")

        def restore(previous):
            row = engine._load()
            if row["request_id"] != request_id or row["previous"]["generation_id"] != previous:
                raise lifecycle.LifecycleError("request_id_conflict")
            activation.restore_committed_generation(
                self.store, store_id, "t-" + request_id,
                row["target"]["generation_id"], previous, stopped)

        engine = lifecycle.Lifecycle(
            self.directory, self.driver, verify_volume=self.verify_volume,
            active_generation=active, activate=activate, restore=restore)
        return engine

    def switch(self, request_id, store_id, candidates, expected_generation,
               principal_sha256):
        target = lifecycle.binding(
            {**self.runtime_binding, "generation_id": expected_generation})
        if self._active(store_id) is None:
            result = self._make_first(
                request_id, store_id, candidates, expected_generation).install(
                    request_id, principal_sha256, store_id, target)
            return {**result, "transaction_id": "t-" + request_id}
        engine = self._make(request_id, store_id, candidates, expected_generation)
        result = engine.switch(request_id, target)
        return {**result, "transaction_id": "t-" + request_id}

    def _first_for(self, request_id, store_id):
        first = self._make_first(request_id, store_id)
        status = first.status()
        return first if status.get("request_id") == request_id else None

    def rollback(self, request_id, store_id, principal_sha256):
        first = self._first_for(request_id, store_id)
        if first is not None:
            return first.rollback(request_id, principal_sha256)
        return self._make(request_id, store_id).rollback(request_id)

    def resume(self, request_id, store_id, principal_sha256):
        first = self._first_for(request_id, store_id)
        if first is not None:
            return first.resume(request_id, principal_sha256)
        return self._make(request_id, store_id).resume(request_id)
