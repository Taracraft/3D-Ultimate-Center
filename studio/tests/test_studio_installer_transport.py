"""Real temporary Unix sockets with synthetic installer archives only."""
import json
import math
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Slicer-Server"))
import installer_transport as transport
import pairing_registry as pairing
import restricted_installer as core
import package_staging as staging
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_studio_restricted_installer import fixtures


class ProtocolTests(unittest.TestCase):
    def test_nonfinite_bool_zero_and_excessive_deadlines_rejected(self):
        for value in [True, False, 0, -1, 301, math.nan, math.inf, -math.inf, "1", None]:
            with self.subTest(value=repr(value)), self.assertRaises(transport.TransportError):
                transport._seconds(value)
        self.assertEqual(transport._seconds(1), 1.0)

    def test_frame_bounds_and_identity(self):
        good = transport._request_frame("a"*32, "Bearer "+"s"*64, b"{}")
        self.assertEqual(len(good), transport.HEADER.size+71+2)
        for host, auth, body in [("bad","Bearer "+"s"*64,b"{}"),
                                 ("a"*32,"Bearer short",b"{}"),
                                 ("a"*32,"Bearer "+"s"*64,b"x"*8193),
                                 ("a"*32,"Bearer "+"s"*64,b"")]:
            with self.assertRaises(transport.TransportError):
                transport._request_frame(host,auth,body)

    def test_peer_uid_validation(self):
        for value in [-1, True, 2**32, "0"]:
            with self.assertRaises(transport.TransportError):
                transport._uid(value)


@unittest.skipUnless(sys.platform == "linux", "Linux SO_PEERCRED and Unix lifecycle")
class SocketTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base/"sockets";self.root.mkdir(mode=0o700)
        registry_root=self.base/"registry";registry_root.mkdir(mode=0o700)
        self.registry=pairing.Registry(registry_root,pairing.initialize(registry_root))
        self.token=self.registry.issue("ha",core.SCOPES)
        control=self.base/"control";control.mkdir(mode=0o700)
        volume=self.base/"volume";volume.mkdir(mode=0o700)
        policy=core.HostPolicy("linux","amd64","managed_docker",True,True,volume/"engines",control)
        catalog,self.archives=fixtures()
        self.service=core.Installer(policy,(),catalog,verify_volume=lambda:True,
                                    workers_stopped=lambda:True,
                                    credential_provider=self.registry.snapshot)
        self.server=transport.UnixInstallerServer(self.root,self.service,self.registry,
                       client_uid=os.geteuid(),client_gid=os.getegid(),io_timeout=2).start()
        self.addCleanup(self.server.close)
        self.client=transport.UnixInstallerClient(self.root,host_id=self.registry.host_id,
                       server_uid=os.geteuid(),timeout=2)
        self.seq=0
        def download(artifact,path,guard):
            guard.check();path.write_bytes(self.archives[artifact.id])
        self.download=download
        self.patcher=patch.object(staging,"_download",side_effect=download)
        self.patcher.start();self.addCleanup(self.patcher.stop)

    def request(self,operation,token=None,client=None,**extra):
        request={"protocol":1,"operation":operation,**extra}
        if operation in core.WRITE_FIELDS and "request_id" not in request:
            self.seq+=1;request["request_id"]=f"{self.seq:032x}"
        return (client or self.client).request(token or self.token,request)

    def raw(self,lane,body,header=None):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.settimeout(2);conn.connect(str(self.root/(lane+".sock")))
            frame=header or transport._request_frame(self.registry.host_id,"Bearer "+self.token,body)
            conn.sendall(frame)
            deadline=time.monotonic()+2
            length,=struct.unpack("!I",transport._read(conn,4,deadline))
            return json.loads(transport._read(conn,length,deadline))["result"]

    def test_complete_synthetic_pipeline_status_and_replay(self):
        first=self.request("initialize",request_id="a"*32)
        self.assertEqual(first["state"],"initialized")
        self.assertEqual(self.request("initialize",request_id="a"*32),first)
        prepared=self.request("stage",request_id="b"*32)
        self.assertEqual(prepared["state"],"prepared")
        result=self.request("activate",target="b"*32,request_id="c"*32)
        self.assertEqual(result["state"],"activated")
        self.assertEqual(self.request("status",target="c"*32)["generation_id"],result["generation_id"])

    def test_rotation_revocation_and_ownership(self):
        first=self.request("initialize")
        old=self.token;self.token=self.registry.rotate("ha")
        self.assertEqual(self.request("preflight",token=old)["error"],"authentication_failed")
        self.assertEqual(self.request("status",target=first["request_id"])["state"],"initialized")
        other=self.registry.issue("other",core.SCOPES)
        self.assertEqual(self.request("status",token=other,target=first["request_id"])["error"],"forbidden")
        self.registry.revoke("ha")
        self.assertEqual(self.request("preflight")["error"],"authentication_failed")

    def test_wrong_lane_cannot_mutate(self):
        result=self.raw("control",b'{"protocol":1,"operation":"initialize","request_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}')
        self.assertEqual(result["error"],"wrong_lane")
        self.assertFalse(self.service.store.exists())

    def test_forwarded_trust_unknown_fields_and_duplicate_keys_rejected(self):
        for body in [b'{"protocol":1,"operation":"preflight","secure_channel":true}',
                     b'{"protocol":1,"operation":"preflight","operation":"initialize"}',
                     b'{"protocol":1,"operation":"preflight","X-Forwarded-Proto":"https"}']:
            self.assertEqual(self.raw("control",body)["error"],"invalid_request")

    def test_oversize_header_rejected_without_reading_claimed_body(self):
        header=transport.HEADER.pack(b"STI1",self.registry.host_id.encode(),71,2**32-1)
        self.assertEqual(self.raw("control",b"",header)["error"],"invalid_frame")

    def test_wrong_host_id_and_invalid_peer_are_rejected(self):
        header=transport._request_frame("f"*32,"Bearer "+self.token,b'{"protocol":1,"operation":"preflight"}')
        self.assertEqual(self.raw("control",b"",header)["error"],"invalid_frame")
        self.server.client_uid=os.geteuid()+1
        self.assertEqual(self.request("preflight")["error"],"unverified_peer")

    def test_client_rejects_wrong_server_owner_before_sending_token(self):
        with self.assertRaises(transport.TransportError):
            transport.UnixInstallerClient(self.root,host_id=self.registry.host_id,
                                           server_uid=os.geteuid()+1)

    def test_real_kernel_peer_check(self):
        first,second=socket.socketpair()
        with first,second:
            transport._peer(first,os.geteuid())
            with self.assertRaises(transport.TransportError):
                transport._peer(first,os.geteuid()+1)

    def test_timeout_keeps_mutation_running_and_control_can_cancel(self):
        self.request("initialize")
        entered,release=threading.Event(),threading.Event()
        def block(artifact,path,guard):
            entered.set()
            if not release.wait(3):raise RuntimeError("test deadline")
            self.download(artifact,path,guard)
        short=transport.UnixInstallerClient(self.root,host_id=self.registry.host_id,
                                            server_uid=os.geteuid(),timeout=.1)
        with patch.object(staging,"_download",side_effect=block):
            result=self.request("stage",client=short,request_id="d"*32)
            try:
                self.assertTrue(entered.is_set())
                self.assertEqual(result["outcome"],"unknown")
                self.assertEqual(result["request_id"],"d"*32)
                self.assertEqual(self.request("status",target="d"*32)["state"],"running")
                denied=self.request("stage",request_id="e"*32)
                self.assertFalse(denied["ok"])
                self.assertEqual(self.request("status",target="e"*32)["error"],"unknown_request")
                self.token=self.registry.rotate("ha")
                self.assertEqual(self.request("cancel",target="d"*32)["state"],"cancel_requested")
            finally:
                release.set()
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                result=self.request("status",target="d"*32)
                if result.get("state")!="running":break
                time.sleep(.01)
            self.assertEqual(result["state"],"cancelled")

    def test_slow_partial_frame_has_absolute_read_deadline(self):
        self.server.io_timeout=.1
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
            conn.settimeout(1);conn.connect(str(self.root/"control.sock"))
            conn.sendall(b"S")
            self.assertEqual(conn.recv(1),b"")

    def test_saturation_bounds_pre_authentication_connections(self):
        sockets=[]
        try:
            for _ in range(2):
                conn=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                conn.connect(str(self.root/"control.sock"));sockets.append(conn)
            deadline=time.monotonic()+1
            while self.server._active<2 and time.monotonic()<deadline:time.sleep(.005)
            self.assertEqual(self.server._active,2)
            self.assertFalse(self.request("preflight")["ok"])
            # A saturated control lane does not consume mutation capacity.
            self.assertEqual(self.request("initialize")["state"],"initialized")
        finally:
            for conn in sockets:conn.close()

    def test_blocked_mutation_auth_does_not_hold_control_lock(self):
        entered,release=threading.Event(),threading.Event()
        original=self.registry._read
        def blocked():
            if threading.current_thread().name.startswith("installer-mutation"):
                entered.set()
                if not release.wait(3):raise RuntimeError("test deadline")
            return original()
        results={}
        with patch.object(self.registry,"_read",side_effect=blocked):
            thread=threading.Thread(target=lambda:results.update(self.request("initialize")))
            thread.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertTrue(self.request("preflight")["ok"])
            finally:
                release.set();thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results["state"],"initialized")

    def test_unexpected_dispatch_exception_is_sanitized(self):
        with patch.object(self.service,"dispatch",side_effect=RuntimeError("private secret path")):
            self.assertEqual(self.request("preflight"),{"ok":False,"error":"transport_failed"})

    def test_corrupt_registry_never_uses_cached_token(self):
        (self.registry.directory/"REGISTRY.json").write_text("broken")
        self.assertEqual(self.request("preflight")["error"],"credentials_unavailable")

    def test_close_drains_without_claiming_cancellation(self):
        entered,release=threading.Event(),threading.Event()
        original=self.service._preflight
        def block():
            entered.set()
            if not release.wait(3):raise RuntimeError("test deadline")
            return original()
        with patch.object(self.service,"_preflight",side_effect=block):
            thread=threading.Thread(target=lambda:self.request("preflight"));thread.start()
            try:
                self.assertTrue(entered.wait(1))
                self.assertEqual(self.server.close(),{"accepting":False,"draining":True})
                self.assertFalse((self.root/"control.sock").exists())
            finally:
                release.set();thread.join(3)
        self.assertFalse(thread.is_alive())

    def test_occupied_socket_path_is_preserved(self):
        self.server.close()
        marker=self.root/"control.sock";marker.write_text("keep")
        other=transport.UnixInstallerServer(self.root,self.service,self.registry,
                    client_uid=os.geteuid(),client_gid=os.getegid())
        with self.assertRaises(transport.TransportError):other.start()
        self.assertEqual(marker.read_text(),"keep")

    def test_wrong_socket_type_and_insecure_directory_fail_closed(self):
        self.server.close()
        (self.root/"control.sock").write_text("not socket")
        self.assertFalse(self.request("preflight")["ok"])
        self.root.chmod(0o777)
        try:
            self.assertFalse(self.request("preflight")["ok"])
        finally:self.root.chmod(0o700)


if __name__=="__main__":
    unittest.main()
