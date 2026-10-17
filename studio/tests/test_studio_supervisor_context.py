"""Supervisor packaging uses only synthetic engines and explicit source pins."""
from pathlib import Path
import importlib.util
import json
import os
import sys
import unittest
from unittest import mock

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p/'Slicer-Server/prepare_runtime_context.py').is_file())
sys.path.insert(0,str(ROOT/'Slicer-Server'))
try:
    candidate=Path(__file__).with_name('prepare_supervisor_context.py')
    spec=importlib.util.spec_from_file_location('tested_supervisor_context',
        candidate if candidate.is_file() else ROOT/'Slicer-Server/prepare_supervisor_context.py')
    app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    spec=importlib.util.spec_from_file_location('supervisor_runtime_fixture',ROOT/'tests/test_studio_runtime_context.py')
    fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
finally:
    sys.path.remove(str(ROOT/'Slicer-Server'))


class SupervisorContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.RuntimeContextTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.work=self.fixture.work
        source=self.fixture.source
        manifest=json.loads((source/'context-manifest.json').read_bytes())
        names={r['path'] for r in manifest['files']}
        docker=(source/'Dockerfile').read_text(encoding='utf-8-sig')
        for name in app.APP_FILES:
            if name in names:continue
            raw=('synthetic '+name+'; never imported\n').encode()
            (source/name).write_bytes(raw)
            manifest['files'].append({'path':name,'sha256':app.dist.sha(raw),'size_bytes':len(raw)})
            docker=docker.replace('container_service.py ',name+' container_service.py ',1)
        (source/'Dockerfile').write_text(docker,encoding='utf-8',newline='\n')
        (source/'context-manifest.json').write_bytes(app.dist.canonical(manifest))
        self.fixture.pins[0]=app.dist.sha((source/'context-manifest.json').read_bytes())
        self.fixture.pins[1]=app.dist.sha((source/'Dockerfile').read_bytes())
        self.fixture.prepare()
        self.runtime=self.fixture.output
        self.pins=self.fixture.pins
        self.output=self.work/'supervisor-context'

    def prepare(self,**kwargs):
        return app.prepare(self.runtime,self.output,*self.pins,**kwargs)

    def test_complete_package_preserves_runtime_and_does_not_claim_release(self):
        result=self.prepare()
        self.assertEqual(result,app.verify(self.output,*self.pins))
        self.assertTrue(result['app_context_verified']);self.assertTrue(result['engine_included'])
        for field in ('engine_executed','image_built','runtime_approved','license_review_complete','app_published','app_installed'):
            self.assertIs(result[field],False)
        for path in self.runtime.rglob('*'):
            if path.is_file():self.assertEqual(path.read_bytes(),(self.output/'runtime'/path.relative_to(self.runtime)).read_bytes())

    def test_configuration_requests_no_host_api_privileges_or_autostart(self):
        self.prepare();config=json.loads((self.output/'config.json').read_bytes())
        self.assertEqual(config['boot'],'manual_only');self.assertEqual(config['arch'],['amd64'])
        self.assertEqual(config['ports'],{'8099/tcp':None});self.assertEqual(config['privileged'],[])
        self.assertEqual(config['map'],[{'type':'ssl','read_only':True}])
        self.assertEqual(config['options']['api_secret'],'')
        self.assertEqual(config['schema']['api_secret'],'password')
        for name in ('host_network','host_pid','host_ipc','host_dbus','host_uts','hassio_api','homeassistant_api','docker_api','auth_api'):
            self.assertIs(config[name],False)

    def test_docker_context_keeps_engines_and_protects_writable_root(self):
        self.prepare();docker=(self.output/'Dockerfile').read_text()
        self.assertIn('runtime/engine/ /engine/',docker)
        self.assertIn('chown -R 0:0 /opt/ultimate-slicer-server /engine /usr/share/ultimate-slicer-server',docker)
        self.assertEqual(docker.count('ENTRYPOINT '),1)
        self.assertIn('supervisor_app_service.py", "start"]',docker)
        self.assertIn('io.hass.arch="amd64"',docker)
        self.assertIn('CMD []',docker)
        for line in docker.splitlines():
            if line.startswith('COPY '):
                self.assertTrue(all(n.startswith('runtime/') for n in line.split()[2:-1]))

    def test_modified_app_permissions_are_rejected(self):
        self.prepare();path=self.output/'config.json';value=json.loads(path.read_bytes());value['host_network']=True
        path.write_bytes(app.dist.canonical(value))
        with self.assertRaisesRegex(ValueError,'bytes_mismatch'):app.verify(self.output,*self.pins)

    def test_approval_flags_cannot_be_set_in_receipt(self):
        self.prepare();p=self.output/app.RECEIPT;value=json.loads(p.read_bytes());value['app_published']=True
        p.write_bytes(app.dist.canonical(value))
        with self.assertRaisesRegex(ValueError,'bytes_mismatch'):app.verify(self.output,*self.pins)

    def test_engine_changes_are_rejected(self):
        self.prepare();p=next((self.output/'runtime/engine').rglob('*.txt'));p.write_bytes(b'not the pinned engine')
        with self.assertRaises(ValueError):app.verify(self.output,*self.pins)

    def test_existing_output_is_never_replaced(self):
        self.output.mkdir();(self.output/'preserve').write_bytes(b'original')
        with self.assertRaisesRegex(ValueError,'output_exists'):self.prepare()
        self.assertEqual((self.output/'preserve').read_bytes(),b'original')

    def test_extra_file_is_rejected(self):
        self.prepare();(self.output/'unreviewed').write_bytes(b'not allowed')
        with self.assertRaisesRegex(ValueError,'members_mismatch'):app.verify(self.output,*self.pins)

    def test_input_digest_mismatch_never_creates_output(self):
        self.pins[0]='a'*64
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.output.exists())

    def test_failed_final_verification_only_removes_own_stage(self):
        marker=self.work/'preserve';marker.write_bytes(b'original')
        with mock.patch.object(app,'verify',side_effect=app.AppContextError('synthetic verifier rejection')):
            with self.assertRaises(app.AppContextError):self.prepare()
        self.assertFalse(self.output.exists());self.assertFalse(list(self.work.glob('.supervisor-context-*')))
        self.assertEqual(marker.read_bytes(),b'original')

    def test_competing_output_survives_exclusive_publish_failure(self):
        real=app.runtime._publish
        def racing(stage,out):
            out.mkdir();(out/'other-writer').write_bytes(b'preserve');real(stage,out)
        with mock.patch.object(app.runtime,'_publish',side_effect=racing):
            with self.assertRaises(OSError):self.prepare()
        self.assertEqual((self.output/'other-writer').read_bytes(),b'preserve')
        self.assertFalse(list(self.work.glob('.supervisor-context-*')))

    def test_two_builds_have_identical_metadata(self):
        first=self.prepare();other=self.work/'second-context'
        second=app.prepare(self.runtime,other,*self.pins)
        self.assertEqual(first,second)
        for name in ('Dockerfile','config.json','README.md','.dockerignore',app.RECEIPT):
            self.assertEqual((self.output/name).read_bytes(),(other/name).read_bytes())

    def test_invalid_versions_cannot_inject_docker_or_config(self):
        for version in ('',None,True,'1.0.0\nRUN bad','1.0','latest','1.0.0"'):
            with self.subTest(value=version),self.assertRaises(ValueError):app.configuration(version)


if __name__=='__main__':unittest.main()
