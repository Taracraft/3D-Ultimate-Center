"""Persistent guided setup sequence; all host effects are synthetic."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
COMPONENT=ROOT/"deploy"/"homeassistant"/"custom_components"/"ultimate_3d_studio"
PKG="studio_installer_setup_test"


def load(name):
    package=sys.modules.setdefault(PKG,type(sys)(PKG));package.__path__=[str(COMPONENT)]
    full=PKG+"."+name
    spec=importlib.util.spec_from_file_location(full,COMPONENT/(name+".py"))
    module=importlib.util.module_from_spec(spec);sys.modules[full]=module;spec.loader.exec_module(module)
    return module


backend=load("slicer_installer_backend");setup=load("slicer_installer_setup")


class FakeClient:
    calls=[]
    def __init__(self,*args,**kwargs):pass
    def request(self,token,request):
        self.calls.append(request.copy())
        op=request["operation"]
        states={"preflight":"available","initialize":"initialized","stage":"prepared","retry":"prepared",
                "activate":"ready_paused","status":"ready_paused","cancel":"cancel_requested",
                "recover":"recovered","rollback":"rolled_back_absent","resume":"complete"}
        return {"ok":True,"request_id":request.get("request_id",request.get("target")),"state":states[op]}


class SetupTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.base=Path(temp.name)
        store_dir=self.base/"secret";store_dir.mkdir(mode=0o700)
        self.store=backend.InstallerCredentialStore(store_dir,expected_host_id="a"*32,server_uid=0)
        backend._atomic_private_json(self.store.path,{"host_id":"a"*32,"principal":"ha","token":"T"*64})
        self.service=backend.InstallerBackend(self.store,self.base,server_uid=0,client_factory=FakeClient)
        state=self.base/"state";state.mkdir(mode=0o700);self.flow=setup.GuidedInstallerSetup(self.service,state)
        FakeClient.calls=[]

    def test_guided_sequence_generates_and_reuses_server_side_ids(self):
        self.assertEqual(self.flow.run("preflight")["state"],"available")
        self.assertEqual(self.flow.run("initialize")["state"],"initialized")
        first=FakeClient.calls[-1]["request_id"]
        self.flow.run("initialize")
        self.assertEqual(FakeClient.calls[-1]["request_id"],first)
        self.flow.run("stage");stage_id=FakeClient.calls[-1]["request_id"]
        self.flow.run("activate");activate=FakeClient.calls[-1]
        self.assertEqual(activate["target"],stage_id)
        activate_id=activate["request_id"]
        for action in ("status","rollback","resume"):
            self.flow.run(action);self.assertEqual(FakeClient.calls[-1]["target"],activate_id)
        public=self.flow.public_status()
        self.assertEqual(public["requests"]["initialize"],first)
        self.assertNotIn("T"*64,str(public))

    def test_cancel_targets_stage_and_missing_steps_fail_closed(self):
        with self.assertRaisesRegex(setup.InstallerSetupError,"setup_step_missing"):
            self.flow.run("activate")
        self.flow.run("stage");target=FakeClient.calls[-1]["request_id"]
        self.flow.run("cancel");self.assertEqual(FakeClient.calls[-1]["target"],target)
        with self.assertRaisesRegex(setup.InstallerSetupError,"unknown_setup_action"):
            self.flow.run("shell")

    def test_state_survives_restart_without_reissuing_identity(self):
        self.flow.run("initialize");ident=FakeClient.calls[-1]["request_id"]
        second=setup.GuidedInstallerSetup(self.service,self.flow.directory)
        second.run("initialize");self.assertEqual(FakeClient.calls[-1]["request_id"],ident)

    def test_backend_failure_is_sanitized_and_request_id_retained(self):
        original=self.service.request
        self.service.request=lambda request: (_ for _ in ()).throw(backend.InstallerBackendError("private"))
        try:result=self.flow.run("initialize")
        finally:self.service.request=original
        self.assertEqual(result,{"ok":False,"error":"installer_unavailable"})
        self.assertRegex(self.flow.public_status()["requests"]["initialize"],r"^[a-f0-9]{32}$")


    def test_retry_and_recover_keep_distinct_persistent_targets(self):
        self.flow.run("stage")
        stage_id=FakeClient.calls[-1]["request_id"]
        self.flow.run("retry")
        retry=FakeClient.calls[-1]
        self.assertEqual(retry["target"],stage_id)
        retry_id=retry["request_id"]
        self.flow.run("activate")
        activate=FakeClient.calls[-1]
        self.assertEqual(activate["target"],retry_id)
        activation_id=activate["request_id"]

        result=self.flow.run("recover",target_action="activate",recovery_action="rollback")
        recovery=FakeClient.calls[-1]
        self.assertEqual(result["state"],"recovered")
        self.assertEqual(recovery["target"],activation_id)
        self.assertEqual(recovery["action"],"rollback")
        recovery_id=recovery["request_id"]
        self.flow.run("recover",target_action="activate",recovery_action="rollback")
        self.assertEqual(FakeClient.calls[-1]["request_id"],recovery_id)
        self.assertNotIn("T"*64,str(self.flow.public_status()))

    def test_recovery_requires_fixed_target_and_action(self):
        for kwargs in ({}, {"target_action":"stage"}, {"target_action":"initialize","recovery_action":"abort"},
                       {"target_action":"stage","recovery_action":"adopt"}, {"target_action":"shell","recovery_action":"abort"},
                       {"target_action":"stage","recovery_action":"shell"}):
            with self.assertRaisesRegex(setup.InstallerSetupError,"invalid_recovery_action"):
                self.flow.run("recover",**kwargs)
if __name__=="__main__":unittest.main()
