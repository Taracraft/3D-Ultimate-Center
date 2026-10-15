"""Protected secret handoff fixtures, including an actual unprivileged client."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"Slicer-Server"))
import installer_handoff as handoff
import installer_transport as transport
import pairing_registry as pairing
import restricted_installer as core


class HandoffRepresentationTests(unittest.TestCase):
    def test_repr_hides_secret(self):
        secret="s"*64
        self.assertNotIn(secret,repr(handoff.Handoff("a"*32,"ha",secret)))


@unittest.skipUnless(sys.platform=="linux","Linux protected handoff ownership")
class HandoffTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name)
        root=self.base/"registry";root.mkdir(mode=0o700)
        self.registry=pairing.Registry(root,pairing.initialize(root))
        self.delivery=self.base/"delivery";self.delivery.mkdir(mode=0o700)

    def publish(self,**kwargs):
        return handoff.publish_handoff(self.registry,"ha",core.SCOPES,self.delivery,
                    client_uid=os.geteuid(),client_gid=os.getegid(),**kwargs)

    def read(self):
        return handoff.read_handoff(self.delivery,server_uid=os.geteuid(),
                                    expected_host_id=self.registry.host_id)

    def test_delivery_readback_rotation_and_private_metadata(self):
        result=self.publish()
        self.assertEqual(set(result),{"host_id","principal","delivered"})
        first=self.read()
        self.assertEqual(first.principal,"ha")
        path=self.delivery/handoff.TOKEN_FILE
        self.assertEqual(path.stat().st_mode&0o777,0o400)
        self.assertNotIn(first.token,(self.registry.directory/"REGISTRY.json").read_text())
        self.publish(rotate=True)
        self.assertNotEqual(first.token,self.read().token)
        self.assertEqual(len(self.registry.snapshot()),1)

    def test_initial_delivery_does_not_replace_existing_recipient(self):
        self.publish();before=(self.delivery/handoff.TOKEN_FILE).read_bytes()
        with self.assertRaises(handoff.HandoffError):self.publish()
        self.assertEqual((self.delivery/handoff.TOKEN_FILE).read_bytes(),before)

    def test_missing_rotation_target_does_not_create_credentials(self):
        with self.assertRaises(handoff.HandoffError):self.publish(rotate=True)
        self.assertEqual(self.registry.snapshot(),())

    def test_wrong_host_pin_and_broad_permissions_rejected(self):
        self.publish()
        with self.assertRaises(handoff.HandoffError):
            handoff.read_handoff(self.delivery,server_uid=os.geteuid(),expected_host_id="f"*32)
        path=self.delivery/handoff.TOKEN_FILE;path.chmod(0o644)
        with self.assertRaises(handoff.HandoffError):self.read()

    def test_hardlinks_symlinks_and_oversize_rejected(self):
        self.publish();path=self.delivery/handoff.TOKEN_FILE
        saved=path.read_bytes();alias=self.base/"alias"
        os.link(path,alias)
        with self.assertRaises(handoff.HandoffError):self.read()
        alias.unlink();path.unlink();alias.write_bytes(saved);path.symlink_to(alias)
        with self.assertRaises(handoff.HandoffError):self.read()
        path.unlink();path.write_bytes(b"x"*(handoff.MAX_HANDOFF+1));path.chmod(0o400)
        with self.assertRaises(handoff.HandoffError):self.read()

    def test_registry_commit_failure_is_explicitly_unconfirmed(self):
        original=handoff.activation._fsync_directory
        def fail(path):
            if Path(path)==self.registry.directory:raise OSError("synthetic private detail")
            return original(path)
        with patch.object(handoff.activation,"_fsync_directory",side_effect=fail):
            with self.assertRaisesRegex(handoff.HandoffError,"^credential_commit_unconfirmed$"):
                self.publish()
        self.assertFalse((self.delivery/handoff.TOKEN_FILE).exists())
        # The registry change may be visible; no false revocation guarantee.
        self.assertEqual(len(self.registry.snapshot()),1)
        self.registry.revoke("ha")

    def test_delivery_failure_revokes_minted_credential(self):
        original=handoff.os.replace
        def fail(src,dest):
            if Path(dest).name==handoff.TOKEN_FILE:raise OSError("synthetic private details")
            return original(src,dest)
        with patch.object(handoff.os,"replace",side_effect=fail):
            with self.assertRaisesRegex(handoff.HandoffError,"^delivery_failed_revoked$"):
                self.publish()
        self.assertEqual(self.registry.snapshot(),())
        self.assertFalse((self.delivery/handoff.TOKEN_FILE).exists())
        self.assertEqual(list(self.delivery.glob(".handoff-*.tmp")),[])

    def test_post_publication_failure_leaves_only_revoked_secret(self):
        original=handoff.activation._fsync_directory
        def fail(path):
            if Path(path)==self.delivery:raise OSError("synthetic")
            return original(path)
        with patch.object(handoff.activation,"_fsync_directory",side_effect=fail):
            with self.assertRaisesRegex(handoff.HandoffError,"^delivery_failed_revoked$"):
                self.publish()
        self.assertTrue((self.delivery/handoff.TOKEN_FILE).exists())
        self.assertEqual(self.registry.snapshot(),())

    def test_revocation_failure_is_not_reported_as_safe(self):
        original=handoff.os.replace
        def fail(src,dest):
            if Path(dest).name==handoff.TOKEN_FILE:raise OSError("synthetic")
            return original(src,dest)
        with patch.object(handoff.os,"replace",side_effect=fail), patch.object(
                self.registry,"revoke",side_effect=OSError("private error")):
            with self.assertRaisesRegex(handoff.HandoffError,"^delivery_failed_revoke_unconfirmed$"):
                self.publish()

    def test_publication_lock_prevents_second_enrollment(self):
        import fcntl
        fd=pairing._open(self.delivery/".handoff.lock",os.O_RDWR|os.O_CREAT)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaisesRegex(handoff.HandoffError,"handoff_busy"):self.publish()
            self.assertEqual(self.registry.snapshot(),())
        finally:os.close(fd)

    def test_modified_or_duplicate_payload_is_rejected(self):
        self.publish();path=self.delivery/handoff.TOKEN_FILE
        for data in [b'{"host_id":"a","host_id":"b"}',b'{}']:
            path.chmod(0o600);path.write_bytes(data);path.chmod(0o400)
            with self.assertRaises(handoff.HandoffError):self.read()

    @unittest.skipUnless(hasattr(os,"geteuid") and os.geteuid()==0,"isolated root UID fixture")
    def test_actual_unprivileged_client_reads_token_and_calls_server(self):
        self.base.chmod(0o755)
        os.chown(self.delivery,0,65532);self.delivery.chmod(0o750)
        handoff.publish_handoff(self.registry,"ha",core.SCOPES,self.delivery,
                                client_uid=65532,client_gid=65532)
        sockets=self.base/"sockets";sockets.mkdir(mode=0o750);os.chown(sockets,0,65532)
        control=self.base/"control";control.mkdir(mode=0o700)
        policy=core.HostPolicy("linux","amd64","managed_docker",True,True,
                               self.base/"engines",control)
        catalog=json.dumps({"schema":1,"releases":[],"pending":sorted(core.catalog.ENTRYPOINTS)}).encode()
        service=core.Installer(policy,(),catalog,verify_volume=lambda:True,
                               workers_stopped=lambda:True,credential_provider=self.registry.snapshot)
        with transport.UnixInstallerServer(sockets,service,self.registry,
                                           client_uid=65532,client_gid=65532):
            code="""import sys,os,json
sys.path.insert(0,sys.argv[1])
import installer_handoff as h
import installer_transport as t
os.setgroups([]);os.setgid(65532);os.setuid(65532)
bundle=h.read_handoff(sys.argv[2],server_uid=0,expected_host_id=sys.argv[4])
client=t.UnixInstallerClient(sys.argv[3],host_id=sys.argv[4],server_uid=0)
print(json.dumps(client.request(bundle.token,{"protocol":1,"operation":"preflight"})))
"""
            r=subprocess.run([sys.executable,"-c",code,str(Path(transport.__file__).parent),
                              str(self.delivery),str(sockets),self.registry.host_id],
                              capture_output=True,text=True,timeout=5)
            self.assertEqual(r.returncode,0,r.stderr)
            result=json.loads(r.stdout)
            self.assertTrue(result["ok"],result)
            self.assertIn("engine_releases_pending",result["reasons"])


if __name__=="__main__":
    unittest.main()
