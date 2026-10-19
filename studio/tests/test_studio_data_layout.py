"""Data layout after real dispatcher metadata; no engine or live container."""
import importlib.util
import contextlib
from types import SimpleNamespace
from unittest.mock import patch
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Slicer-Server'))
import container_service as service

class DataLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        service.initialize_data(self.base)

    def write_result(self, raw):
        p = self.base / 'last_job.json'
        p.write_text(json.dumps(raw))
        p.chmod(0o600)
        return p

    def test_completed_job_metadata_allows_next_dispatch(self):
        self.write_result({'job_id': 'studio-' + 'a'*32, 'status': 'completed', 'engine': 'auto'})
        self.assertEqual(service.persistent_data(self.base), self.base)
        self.assertEqual(service.initialize_data(self.base)['initialized'], False)
        self.assertEqual(service.persistent_data(self.base), self.base)

    def test_failed_and_cancelled_results_are_owned_metadata(self):
        for state in ('failed', 'cancelled'):
            self.write_result({'job_id': 'studio-' + 'b'*32, 'status': state})
            self.assertEqual(service.persistent_data(self.base), self.base)

    def test_unrelated_root_file_is_still_rejected(self):
        (self.base / 'foreign.txt').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'data_unrecognized_store'):
            service.persistent_data(self.base)

    def test_last_result_must_be_bounded_private_regular_valid_json(self):
        for raw in ({}, {'job_id': '../invalid', 'status': 'completed'}, {'job_id':'job', 'status':'running'}, []):
            self.write_result(raw)
            with self.assertRaises(ValueError): service.persistent_data(self.base)
        p = self.write_result({'job_id':'job', 'status':'completed'})
        p.unlink(); p.symlink_to(self.base / 'DATA_STATE.json')
        with self.assertRaises(ValueError): service.persistent_data(self.base)
        p.unlink(); p.write_text('{' + ' '*70000);p.chmod(0o600)
        with self.assertRaises(ValueError): service.persistent_data(self.base)



class MetadataRecoveryTests(DataLayoutTests):
    def prepared_recovery(self):
        last={'job_id':'studio-'+'a'*32,'status':'completed'}
        self.write_result(last)
        (self.base/'run/container-recovery.json').write_text(json.dumps({'requires_recovery':True,'error':'RecoveryRequired'}))
        (self.base/'data/jobs'/ (last['job_id']+'.completed.json')).write_text('{}')
        (self.base/'data/output'/(last['job_id']+'.result.json')).write_text(json.dumps(last))
        for p in self.base.rglob('*.json'):p.chmod(0o600)
        jc=SimpleNamespace(JobControl=lambda base:SimpleNamespace(run=base/'run',jobs=base/'data/jobs',output=base/'data/output'),
            file_lock=lambda *args,**kw:contextlib.nullcontext(),
            atomic_json=lambda p,v:p.write_text(json.dumps(v)),utcnow=lambda:'test-time')
        return jc

    def test_known_terminal_metadata_recovery_preserves_artifacts_and_evidence(self):
        jc=self.prepared_recovery()
        with patch.object(service,'canonical',return_value=jc):
            result=service.recover_data_layout(self.base,verified_legacy_error=True)
            self.assertTrue(result['recovered'])
            self.assertEqual(service.recover_data_layout(self.base,verified_legacy_error=True)['state'],'no_recovery_marker')
        self.assertTrue((self.base/'run/data-layout-recovery.json').is_file())
        self.assertFalse((self.base/'run/container-recovery.json').exists())
        self.assertEqual(len(list((self.base/'data/jobs').glob('*.completed.json'))),1)

    def test_recovery_requires_specific_host_proof(self):
        self.prepared_recovery()
        with self.assertRaisesRegex(ValueError,'legacy_layout_failure_proof_required'):
            service.recover_data_layout(self.base)

    def test_unknown_error_is_not_cleared(self):
        jc=self.prepared_recovery()
        marker=self.base/'run/container-recovery.json';marker.write_text(json.dumps({'requires_recovery':True,'error':'OtherError'}))
        with patch.object(service,'canonical',return_value=jc),self.assertRaisesRegex(ValueError,'unrecognized_recovery_error'):
            service.recover_data_layout(self.base,verified_legacy_error=True)
        self.assertTrue(marker.exists())

    def test_unfinished_job_blocks_recovery(self):
        jc=self.prepared_recovery();(self.base/'data/jobs/other.slicing.json').write_text('{}')
        with patch.object(service,'canonical',return_value=jc),self.assertRaisesRegex(ValueError,'unfinished_job_requires_recovery'):
            service.recover_data_layout(self.base,verified_legacy_error=True)
        self.assertTrue((self.base/'run/container-recovery.json').exists())

    def test_live_owner_lock_blocks_recovery(self):
        jc=self.prepared_recovery()
        def locked(*args,**kwargs):raise BlockingIOError('held')
        jc.file_lock=locked
        with patch.object(service,'canonical',return_value=jc),self.assertRaises(BlockingIOError):
            service.recover_data_layout(self.base,verified_legacy_error=True)
        self.assertTrue((self.base/'run/container-recovery.json').exists())

if __name__ == '__main__': unittest.main()
