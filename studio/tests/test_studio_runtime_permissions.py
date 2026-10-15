"""Synthetic permission contracts; no engine, Docker or service execution."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import host_storage as storage
import package_activation as activation


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.control = self.root / "control"
        self.control.mkdir(mode=0o700)
        self.volume = self.root / "volume"
        self.volume.mkdir(mode=0o700)
        self.base = self.volume / "studio"
        self.identity = storage.Volume("synthetic-uuid", "/", "/fixture", "ext4")
        self.observe = lambda path: self.identity
        self.layout = storage.provision(self.control, base=self.base,
                                        approved_roots=(self.volume,), observe=self.observe)
        self.binding = storage._read_binding(self.control)

    def record(self, **changes):
        value = {"schema": 1, "state": "ready", "gid": storage.RUNTIME_GID,
                 "mode": storage.RUNTIME_MODE, "volume_sha256": storage._volume_digest(self.binding)}
        value.update(changes)
        activation._atomic_json(self.control / "PERMISSIONS.json", value)
        return value

    def test_no_record_retains_original_strict_guard(self):
        self.assertIsNone(storage._runtime_permissions(self.control, self.binding))
        self.assertTrue(storage.VolumeGuard(self.control, observe=self.observe)())

    def test_binding_digest_is_order_independent(self):
        self.assertEqual(storage._volume_digest(self.binding),
                         storage._volume_digest(dict(reversed(list(self.binding.items())))))

    def test_malformed_records_fail_closed(self):
        for change in ({"schema":True},{"gid":0},{"gid":True},{"mode":0o777},
                       {"volume_sha256":"bad"},{"state":"unknown"},{"extra":1}):
            with self.subTest(change=change):
                self.record(**change)
                self.assertFalse(storage.VolumeGuard(self.control, observe=self.observe)())

    def test_incomplete_permission_intent_blocks_guard(self):
        self.record(state="preparing")
        with self.assertRaisesRegex(storage.StorageError,"reconciliation_required"):
            storage._runtime_permissions(self.control,self.binding)
        self.assertFalse(storage.VolumeGuard(self.control,observe=self.observe)())

    def test_windows_cannot_apply_linux_permissions(self):
        with patch.object(storage.platform,"system",return_value="Windows"):
            with self.assertRaisesRegex(storage.StorageError,"linux_root_required"):
                storage.grant_runtime_access(self.control,lambda:True,observe=self.observe)

    def test_symlinked_record_rejected(self):
        target=self.root/"foreign.json"
        target.write_text("{}")
        try:(self.control/"PERMISSIONS.json").symlink_to(target)
        except OSError:self.skipTest("symlink unavailable")
        self.assertFalse(storage.VolumeGuard(self.control,observe=self.observe)())
        self.assertEqual(target.read_text(),"{}")


@unittest.skipUnless(os.name=="posix" and getattr(os,"geteuid",lambda:1)()==0,
                     "Linux root POSIX permission contract")
class LinuxPermissionsTests(RecordTests):
    def grant(self, stopped=lambda:True):
        return storage.grant_runtime_access(self.control,stopped,observe=self.observe)

    def test_grant_exact_group_modes_and_preserve_engine_control(self):
        before={p: p.stat() for p in (self.base,self.layout["engines"],self.control)}
        self.grant()
        for name in storage.MUTABLE_LAYOUT:
            info=self.layout[name].stat()
            self.assertEqual((info.st_uid,info.st_gid,stat.S_IMODE(info.st_mode)),(0,65532,0o2770))
        for path,info in before.items():
            after=path.stat()
            self.assertEqual((after.st_uid,after.st_gid,after.st_mode),
                             (info.st_uid,info.st_gid,info.st_mode))
        self.assertTrue(storage.VolumeGuard(self.control,observe=self.observe)())
        self.assertEqual(storage.provision(self.control,base=self.base,
                         approved_roots=(self.volume,),observe=self.observe),self.layout)

    def test_worker_uid_can_write_but_cannot_chmod_root(self):
        self.grant()
        for name in storage.MUTABLE_LAYOUT:
            fd=os.open(self.layout[name],os.O_RDONLY|os.O_DIRECTORY)
            try:
                code = (
                    "import os;from pathlib import Path;"
                    "os.fchdir(int(__import__('sys').argv[1]));"
                    "os.setgroups([]);os.setgid(65532);os.setuid(65532);"
                    "Path('synthetic').write_text('test');"
                    "assert Path('synthetic').stat().st_gid==65532;"
                    "\ntry: os.chmod('.',0o777)\nexcept PermissionError: pass\nelse: raise AssertionError('root mode writable')"
                )
                r=subprocess.run([sys.executable,"-c",code,str(fd)],pass_fds=(fd,),capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)
            finally:os.close(fd)
        self.assertTrue(storage.VolumeGuard(self.control,observe=self.observe)())

    def test_worker_can_read_generation_but_not_modify_it(self):
        self.grant()
        generation=self.layout["engines"]/"synthetic-generation"
        generation.mkdir(mode=0o755)
        (generation/"fixture").write_text("read-only")
        (generation/"fixture").chmod(0o644)
        fd=os.open(generation,os.O_RDONLY|os.O_DIRECTORY)
        try:
            code = (
                "import os;from pathlib import Path;"
                "os.fchdir(int(__import__('sys').argv[1]));"
                "os.setgroups([]);os.setgid(65532);os.setuid(65532);"
                "assert Path('fixture').read_text()=='read-only';"
                "\ntry: Path('fixture').write_text('changed')\nexcept PermissionError: pass\nelse: raise AssertionError('engine writable')"
                "\ntry: Path('new').write_text('changed')\nexcept PermissionError: pass\nelse: raise AssertionError('generation writable')"
            )
            r=subprocess.run([sys.executable,"-c",code,str(fd)],pass_fds=(fd,),capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
        finally:os.close(fd)

    def test_worker_cannot_read_private_control(self):
        self.grant()
        fd=os.open(self.control,os.O_RDONLY|os.O_DIRECTORY)
        try:
            code = (
                "import os;from pathlib import Path;"
                "os.fchdir(int(__import__('sys').argv[1]));"
                "os.setgroups([]);os.setgid(65532);os.setuid(65532);"
                "\ntry: Path('VOLUME.json').read_bytes()\nexcept PermissionError: pass\nelse: raise AssertionError('control readable')"
            )
            r=subprocess.run([sys.executable,"-c",code,str(fd)],pass_fds=(fd,),capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
        finally:os.close(fd)

    def test_nonempty_initial_directory_is_not_reowned(self):
        p=self.layout["profiles"]/"user-profile";p.write_text("keep")
        before=self.layout["data"].stat()
        with self.assertRaisesRegex(storage.StorageError,"not_empty"):self.grant()
        self.assertEqual(p.read_text(),"keep")
        self.assertEqual(self.layout["data"].stat().st_mode,before.st_mode)
        self.assertFalse((self.control/"PERMISSIONS.json").exists())

    def test_repeated_grant_preserves_existing_contents(self):
        self.grant()
        p=self.layout["data"]/"keep";p.write_text("original")
        with patch.object(storage.os,"fchown",side_effect=AssertionError("must not mutate")):
            self.grant(stopped=lambda:False)
        self.assertEqual(p.read_text(),"original")

    def test_workers_must_be_confirmed_stopped(self):
        for stopped in (None,lambda:False,lambda:1):
            with self.assertRaisesRegex(storage.StorageError,"workers_not_stopped"):
                self.grant(stopped)
        self.assertFalse((self.control/"PERMISSIONS.json").exists())

    def test_crash_retains_intent_and_blocks_next_attempt(self):
        original=os.fchmod
        calls={"n":0}
        def fail(fd,mode):
            calls["n"]+=1
            if calls["n"]==2:raise OSError("synthetic failure")
            return original(fd,mode)
        with patch.object(storage.os,"fchmod",fail),self.assertRaises(OSError):
            self.grant()
        self.assertEqual(json.loads((self.control/"PERMISSIONS.json").read_bytes())["state"],"preparing")
        self.assertFalse(storage.VolumeGuard(self.control,observe=self.observe)())
        with self.assertRaisesRegex(storage.StorageError,"reconciliation_required"):self.grant()

    def test_drift_in_mode_group_owner_is_rejected(self):
        self.grant();p=self.layout["data"]
        for uid,gid,mode in ((0,65532,0o2777),(0,12345,0o2770),(65532,65532,0o2770)):
            os.chown(p,uid,gid);p.chmod(mode)
            self.assertFalse(storage.VolumeGuard(self.control,observe=self.observe)())
        os.chown(p,0,65532);p.chmod(0o2770)
        self.assertTrue(storage.VolumeGuard(self.control,observe=self.observe)())

    def test_runtime_permission_never_applies_to_ancestor_or_engine(self):
        self.grant()
        for p in (self.base,self.layout["engines"]):
            original=p.stat()
            os.chown(p,0,65532);p.chmod(0o2770)
            self.assertFalse(storage.VolumeGuard(self.control,observe=self.observe)())
            os.chown(p,original.st_uid,original.st_gid);p.chmod(stat.S_IMODE(original.st_mode))

    def test_acl_rejected_without_changes(self):
        with patch.object(storage.os,"listxattr",return_value=["system.posix_acl_default"]):
            with self.assertRaisesRegex(storage.StorageError,"runtime_directory_acl"):self.grant()
        self.assertFalse((self.control/"PERMISSIONS.json").exists())

    def test_lock_prevents_concurrent_grant(self):
        with activation._store_lock(self.control),self.assertRaises(activation.ActivationError):
            self.grant()
        self.assertFalse((self.control/"PERMISSIONS.json").exists())


if __name__=="__main__":unittest.main()
