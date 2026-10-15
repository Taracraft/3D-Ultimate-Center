"""HA installer backend: protected handoff, secret store and Unix proof."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy" / "homeassistant" / "custom_components" / "ultimate_3d_studio"


def load_backend():
    spec = importlib.util.spec_from_file_location("studio_installer_backend_test", COMPONENT / "slicer_installer_backend.py")
    module = importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


backend = load_backend()


class FakeClient:
    calls = []
    response = {"ok": True, "state": "available"}
    def __init__(self, directory, **kwargs): self.directory,self.kwargs=directory,kwargs
    def request(self, token, request):
        self.calls.append((token,request));return self.response


class BackendTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.base=Path(temp.name);self.secret="T"*64;self.host="a"*32
        self.store=self.base/"store";self.store.mkdir(mode=0o700)
        self.handoff=self.base/"handoff";self.handoff.mkdir(mode=0o700)
        payload={"host_id":self.host,"principal":"ha","token":self.secret}
        self.source=self.handoff/backend.TOKEN_FILE
        self.source.write_text(json.dumps(payload,separators=(",",":")),encoding="ascii")
        self.source.chmod(0o400)

    def credential_store(self):
        return backend.InstallerCredentialStore(self.store,expected_host_id=self.host,
                                                server_uid=os.geteuid() if hasattr(os,"geteuid") else 0)

    def test_handoff_is_removed_only_after_private_store_readback(self):
        store=self.credential_store();result=store.adopt_handoff(self.handoff)
        self.assertEqual(result,{"credential_stored":True,"host_id":self.host,"principal":"ha"})
        self.assertFalse(self.source.exists())
        saved=store.path.read_text(encoding="ascii")
        self.assertIn(self.secret,saved)
        self.assertNotIn(self.secret,repr(store.load()))
        self.assertNotIn(self.secret,str(store.public_status()))

    def test_failed_store_keeps_handoff(self):
        store=self.credential_store()
        with patch.object(backend,"_atomic_private_json",side_effect=OSError("synthetic")):
            with self.assertRaises(OSError):store.adopt_handoff(self.handoff)
        self.assertTrue(self.source.exists())

    def test_wrong_host_duplicate_keys_links_and_oversize_are_rejected(self):
        store=self.credential_store()
        cases=[b'{"host_id":"'+b'b'*32+b'","principal":"ha","token":"'+b'T'*64+b'"}',
               b'{"host_id":"'+b'a'*32+b'","host_id":"'+b'a'*32+b'"}',
               b'x'*(backend.MAX_HANDOFF_BYTES+1)]
        for data in cases:
            with self.subTest(size=len(data)):
                self.source.chmod(0o600);self.source.write_bytes(data);self.source.chmod(0o400)
                with self.assertRaises(backend.InstallerBackendError):store.adopt_handoff(self.handoff)

    def test_backend_uses_secret_internally_and_rejects_secret_response(self):
        store=self.credential_store();store.adopt_handoff(self.handoff)
        service=backend.InstallerBackend(store,self.base,server_uid=0,client_factory=FakeClient)
        FakeClient.calls=[];FakeClient.response={"ok":True,"state":"blocked"}
        result=service.request({"protocol":1,"operation":"preflight"})
        self.assertEqual(result,{"ok":True,"state":"blocked"})
        self.assertEqual(FakeClient.calls[0][0],self.secret)
        self.assertNotIn(self.secret,str(result)+repr(service))
        FakeClient.response={"ok":True,"token":self.secret}
        with self.assertRaisesRegex(backend.InstallerBackendError,"secret_in_response"):
            service.request({"protocol":1,"operation":"preflight"})


@unittest.skipUnless(sys.platform=="linux","Linux Unix socket interoperability")
class LinuxInteropTests(unittest.TestCase):
    def test_component_client_calls_real_installer_server_after_handoff(self):
        sys.path.insert(0,str(ROOT/"Slicer-Server"))
        import installer_handoff,installer_transport,pairing_registry,restricted_installer
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);base=Path(temp.name)
        registry_dir=base/"registry";registry_dir.mkdir(mode=0o700)
        registry=pairing_registry.Registry(registry_dir,pairing_registry.initialize(registry_dir))
        delivery=base/"delivery";delivery.mkdir(mode=0o700)
        uid=os.geteuid();gid=os.getegid()
        installer_handoff.publish_handoff(registry,"ha",restricted_installer.SCOPES,delivery,
                                          client_uid=uid,client_gid=gid)
        sockets=base/"sockets";sockets.mkdir(mode=0o700)
        control=base/"control";control.mkdir(mode=0o700)
        policy=restricted_installer.HostPolicy("linux","amd64","managed_docker",True,True,
                                               base/"engines",control)
        catalog=json.dumps({"schema":1,"releases":[],
            "pending":sorted(restricted_installer.catalog.ENTRYPOINTS)}).encode()
        core=restricted_installer.Installer(policy,(),catalog,verify_volume=lambda:True,
                    workers_stopped=lambda:True,credential_provider=registry.snapshot)
        secrets_dir=base/"secrets";secrets_dir.mkdir(mode=0o700)
        store=backend.InstallerCredentialStore(secrets_dir,expected_host_id=registry.host_id,server_uid=uid)
        store.adopt_handoff(delivery)
        with installer_transport.UnixInstallerServer(sockets,core,registry,client_uid=uid,client_gid=gid):
            service=backend.InstallerBackend(store,sockets,server_uid=uid,timeout=2)
            result=service.request({"protocol":1,"operation":"preflight"})
        self.assertTrue(result["ok"],result)
        self.assertIn("engine_releases_pending",result["reasons"])


if __name__=="__main__":unittest.main()
