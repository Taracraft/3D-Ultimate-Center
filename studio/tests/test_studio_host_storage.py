"""Persistent storage tests; native writes confined to temporary synthetic trees."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock
import stat
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import host_storage as storage
import restricted_installer as installer


class MountTests(unittest.TestCase):
    def row(self, ident=1, parent=1, device="8:1", root="/", point="/",
            fs="ext4", options="rw", super_options="rw"):
        return f"{ident} {parent} {device} {root} {point} {options} shared:1 - {fs} /dev/test {super_options}\n".encode()

    def test_mountinfo_optional_fields_and_escaped_paths(self):
        rows = storage.parse_mountinfo(self.row() + self.row(2, point=r"/my\040disk"))
        selected = storage.select_mount(rows, "/my disk/engines", "8:1")
        self.assertEqual(selected.point, "/my disk")
        self.assertEqual(selected.mount_id, 2)

    def test_unrelated_namespace_mount_does_not_block_local_volume(self):
        rows = storage.parse_mountinfo(self.row() + self.row(2, root="net:[12345]",
                                                          point="/run/netns/test", fs="nsfs"))
        self.assertEqual(storage.select_mount(rows, "/var/lib/studio", "8:1").filesystem, "ext4")
        with self.assertRaisesRegex(storage.StorageError, "unsupported"):
            storage.select_mount(rows, "/run/netns/test", "8:1")

    def test_nested_mount_wins_even_when_parent_device_matches(self):
        rows = storage.parse_mountinfo(self.row() + self.row(2, point="/data", device="8:2"))
        with self.assertRaisesRegex(storage.StorageError, "mount_device_mismatch"):
            storage.select_mount(rows, "/data/engines", "8:1")

    def test_path_component_boundary_is_respected(self):
        rows = storage.parse_mountinfo(self.row() + self.row(2, point="/data"))
        self.assertEqual(storage.select_mount(rows, "/database/engines", "8:1").mount_id, 1)

    def test_stacked_mount_is_rejected(self):
        rows = storage.parse_mountinfo(self.row() + self.row(2))
        with self.assertRaisesRegex(storage.StorageError, "ambiguous_mount"):
            storage.select_mount(rows, "/engines", "8:1")

    def test_ephemeral_remote_overlay_and_readonly_mounts_rejected(self):
        for fs in ("tmpfs", "overlay", "nfs", "cifs", "btrfs"):
            with self.subTest(fs=fs), self.assertRaisesRegex(storage.StorageError, "unsupported"):
                storage.select_mount(storage.parse_mountinfo(self.row(fs=fs)), "/data", "8:1")
        for kwargs in ({"options": "ro"}, {"super_options": "ro"}):
            with self.assertRaisesRegex(storage.StorageError, "read_only_volume"):
                storage.select_mount(storage.parse_mountinfo(self.row(**kwargs)), "/data", "8:1")

    def test_malformed_duplicate_and_bounded_input(self):
        for data in (b"", b"invalid", self.row()+self.row(), self.row(point=r"/bad\999"),
                     self.row(point="relative"), b"\xff"):
            with self.subTest(data=data), self.assertRaises(storage.StorageError):
                storage.parse_mountinfo(data)
        with self.assertRaisesRegex(storage.StorageError, "mountinfo_size"):
            storage.parse_mountinfo(b" "*(storage.MAX_MOUNTINFO+1))

    def test_missing_mount_and_traversal(self):
        rows = storage.parse_mountinfo(self.row(point="/data"))
        with self.assertRaisesRegex(storage.StorageError, "mount_not_found"):
            storage.select_mount(rows, "/other", "8:1")
        with self.assertRaisesRegex(storage.StorageError, "invalid_storage_path"):
            storage.select_mount(rows, "/data/../other", "8:1")

    def test_native_probe_rejects_temporary_paths_before_host_reads(self):
        with patch.object(storage.platform, "system", return_value="Linux"):
            for path in ("/tmp/studio", "/var/tmp/studio", "/run/studio",
                         "/dev/studio", "/proc/studio", "/sys/studio"):
                with self.subTest(path=path), self.assertRaisesRegex(storage.StorageError, "temporary_storage_path"):
                    storage.native_volume(PurePosixPath(path))

    def test_uuid_probe_requires_exactly_one_matching_block_device(self):
        def entry(name, device, mode=stat.S_IFBLK):
            item = Mock()
            item.name = name
            item.stat.return_value = SimpleNamespace(st_mode=mode, st_rdev=device)
            return item
        good = entry("stable-uuid", 42)
        wrong = entry("wrong-device", 43)
        regular = entry("regular", 42, stat.S_IFREG)
        with patch.object(Path, "is_dir", return_value=True):
            with patch.object(Path, "iterdir", return_value=iter([good, wrong, regular])):
                self.assertEqual(storage._uuid_for_device(42), "stable-uuid")
            for entries in ([], [good, entry("duplicate", 42)]):
                with patch.object(Path, "iterdir", return_value=iter(entries)):
                    with self.assertRaisesRegex(storage.StorageError, "filesystem_uuid_ambiguous"):
                        storage._uuid_for_device(42)
        with patch.object(Path, "is_dir", return_value=False):
            with self.assertRaisesRegex(storage.StorageError, "filesystem_uuid_unavailable"):
                storage._uuid_for_device(42)


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.control = self.root/"control"
        self.control.mkdir(mode=0o700)
        self.parent = self.root/"volume"
        self.parent.mkdir(mode=0o700)
        self.base = self.parent/"studio"
        self.volume = storage.Volume("test-uuid", "/", "/test-volume", "ext4")
        self.observe = lambda path: self.volume

    def provision(self, **kwargs):
        return storage.provision(self.control, base=kwargs.pop("base", self.base),
                                 approved_roots=kwargs.pop("approved_roots", (self.parent,)),
                                 observe=kwargs.pop("observe", self.observe), **kwargs)

    def guard(self, **kwargs):
        return storage.VolumeGuard(self.control, observe=kwargs.get("observe", self.observe))

    def test_new_layout_and_repeated_provision_preserve_data(self):
        result = self.provision()
        self.assertEqual(set(p.name for p in self.base.iterdir()), set(storage.LAYOUT))
        (result["profiles"]/"user.json").write_text("keep")
        self.assertEqual(self.provision(), result)
        self.assertEqual((result["profiles"]/"user.json").read_text(), "keep")
        self.assertTrue(self.guard()())
        self.assertEqual(json.loads((self.control/"VOLUME.json").read_bytes())["state"], "ready")

    def test_pending_catalog_can_initialize_store_with_real_guard(self):
        layout = self.provision()
        token = "a"*64
        credentials = (installer.Credential("ha", hashlib.sha256(token.encode()).digest(),
                                           installer.SCOPES),)
        catalog_bytes = json.dumps({"schema":1, "releases":[],
                                   "pending":["bambu_studio","prusaslicer","curaengine"]}).encode()
        policy = installer.HostPolicy("linux","amd64","managed_docker",True,True,
                                       layout["engines"],self.control)
        api = installer.Installer(policy, credentials, catalog_bytes,
                                  verify_volume=self.guard(), workers_stopped=lambda: False)
        body = json.dumps({"protocol":1,"operation":"initialize","request_id":"1"*32}).encode()
        reply = api.dispatch("Bearer "+token, body, secure_channel=True)
        self.assertEqual(reply["state"], "initialized", reply)
        self.assertTrue((layout["engines"]/"STORE.json").exists())
        self.assertTrue(self.guard()())

    def test_existing_foreign_data_is_untouched(self):
        self.base.mkdir()
        (self.base/"keep").write_text("original")
        with self.assertRaisesRegex(storage.StorageError, "storage_not_empty"):
            self.provision()
        self.assertEqual((self.base/"keep").read_text(),"original")
        self.assertFalse((self.control/"VOLUME.json").exists())

    def test_only_approved_child_paths(self):
        for path in (self.parent, self.root/"outside", self.parent/"missing"/"studio"):
            with self.subTest(path=path), self.assertRaises(storage.StorageError):
                self.provision(base=path)
        self.assertFalse(self.base.exists())

    def test_default_path_can_be_used_without_a_path_argument(self):
        with patch.object(storage,"DEFAULT_BASE",self.base):
            layout = storage.provision(self.control, approved_roots=(self.parent,), observe=self.observe)
        self.assertEqual(layout["base"],self.base)

    def test_lost_mount_uuid_root_and_mountpoint_are_not_adopted(self):
        self.provision()
        for field,value in (("uuid","other"),("point","/"),("root","/different"),("filesystem","xfs")):
            changed=replace(self.volume,**{field:value})
            guard=self.guard(observe=lambda path:changed)
            self.assertFalse(guard())
            with self.assertRaisesRegex(storage.StorageError,"volume_changed"):
                guard.check()

    def test_nested_replacement_mount_is_rejected(self):
        self.provision()
        changed=replace(self.volume,uuid="different")
        guard=self.guard(observe=lambda path: changed if path.name=="profiles" else self.volume)
        self.assertFalse(guard())

    def test_missing_directory_does_not_get_recreated(self):
        self.provision()
        (self.base/"profiles").rmdir()
        self.assertFalse(self.guard()())
        self.assertFalse((self.base/"profiles").exists())
        with self.assertRaises(storage.StorageError):
            self.provision()

    def test_volume_changed_between_intent_and_creation(self):
        calls={"count":0}
        def observe(path):
            calls["count"]+=1
            return self.volume if calls["count"]==1 else replace(self.volume,uuid="other")
        with self.assertRaisesRegex(storage.StorageError,"volume_changed"):
            self.provision(observe=observe)
        self.assertFalse(self.base.exists())
        self.assertEqual(json.loads((self.control/"VOLUME.json").read_bytes())["state"],"provisioning")
        with self.assertRaisesRegex(storage.StorageError,"provisioning_reconciliation_required"):
            self.provision()

    def test_crash_during_creation_keeps_durable_intent(self):
        original=Path.mkdir
        def fail(path,*args,**kwargs):
            if path==self.base/"data":
                raise OSError("synthetic crash")
            return original(path,*args,**kwargs)
        with patch.object(Path,"mkdir",fail),self.assertRaises(OSError):
            self.provision()
        self.assertTrue((self.base/"engines").exists())
        self.assertFalse(self.guard()())
        with self.assertRaisesRegex(storage.StorageError,"provisioning_reconciliation_required"):
            self.provision()

    def test_insufficient_space_does_not_leave_intent(self):
        usage=storage.shutil.disk_usage(self.parent)
        with patch.object(storage.shutil,"disk_usage",return_value=type(usage)(usage.total,usage.used,1)):
            with self.assertRaisesRegex(storage.StorageError,"insufficient_storage_space"):
                self.provision()
        self.assertFalse((self.control/"VOLUME.json").exists())

    def test_binding_change_and_new_path_are_rejected(self):
        self.provision()
        guard=self.guard()
        binding=json.loads((self.control/"VOLUME.json").read_bytes())
        binding["volume"]["uuid"]="other"
        from package_activation import _atomic_json
        _atomic_json(self.control/"VOLUME.json",binding)
        self.assertFalse(guard())
        with self.assertRaisesRegex(storage.StorageError,"storage_binding_mismatch"):
            self.provision(base=self.parent/"new")

    def test_symlink_target_is_rejected(self):
        try:
            self.base.symlink_to(self.control,target_is_directory=True)
        except OSError:
            self.skipTest("symlink unsupported")
        with self.assertRaisesRegex(storage.StorageError,"linked_storage_path"):
            self.provision()

    def test_control_overlap_is_rejected(self):
        with self.assertRaises(storage.StorageError):
            self.provision(base=self.control/"child",approved_roots=(self.root,))

    def test_shared_control_permissions_are_rejected(self):
        if os.name=="nt":
            self.skipTest("POSIX control permissions")
        self.control.chmod(0o755)
        with self.assertRaisesRegex(storage.StorageError,"private_control_required"):
            self.provision()
        self.control.chmod(0o700)

    def test_process_lock_prevents_parallel_provisioning(self):
        from package_activation import _store_lock
        storage._control(self.control)
        with _store_lock(self.control),self.assertRaises(Exception):
            self.provision()
        self.assertFalse(self.base.exists())


if __name__=="__main__":
    unittest.main()
