"""Real worker queue/HTTP contracts with temporary directories, never production jobs."""
import importlib.util
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import time
import threading
import unittest
from unittest.mock import Mock, patch

WORKER = Path(__file__).resolve().parents[1] / 'deploy/homeassistant/host/3d-printer-slicing-server'
spec = importlib.util.spec_from_file_location('studio_test_job_control', WORKER / 'job_control.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
JobControl = module.JobControl


class WorkerCancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.control = JobControl(self.base)
        self.config = self.base/'config.json'
        self.config.write_text(json.dumps({'base_dir':str(self.base),'token':'test-only'}))
        with patch.object(sys,'argv',[str(WORKER/'server.py'),str(self.config)]), patch('http.server.ThreadingHTTPServer'):
            self.worker = runpy.run_path(str(WORKER/'server.py'))

    def job(self, name='sample', state='queued', **extra):
        path=self.control.jobs/f'{name}.{state}.json'
        path.write_text(json.dumps({'job_id':name,'input_file':'model.stl','manual_release':True,**extra}))
        return path

    def post(self, name='sample', authorized=True):
        handler=object.__new__(self.worker['Handler'])
        handler.path=f'/api/v1/jobs/{name}/cancel'
        handler.require_authorization=lambda:authorized
        answers=[]
        handler.send_json=lambda status,payload:answers.append((status,payload))
        handler.do_POST()
        return answers

    def test_held_cancel_is_idempotent_and_preserves_upload(self):
        self.job()
        upload=self.base/'data/uploads/model.stl';upload.write_bytes(b'input')
        out=self.control.output/'sample';out.mkdir();(out/'plate_1.gcode').write_bytes(b'partial')
        self.assertEqual(self.post()[0][0],200)
        self.assertEqual(self.worker['job_state']('sample')['status'],'cancelled')
        first=(self.control.output/'sample.result.json').read_bytes()
        self.assertTrue(self.post()[0][1]['already_cancelled'])
        self.assertEqual(first,(self.control.output/'sample.result.json').read_bytes())
        self.assertTrue(upload.exists());self.assertFalse(out.exists())
        self.assertIsNone(self.worker['result_file']('sample'))

    def test_missing_invalid_terminal_and_unauthorized_are_non_mutating(self):
        self.assertEqual(self.post('missing')[0][0],404)
        self.assertEqual(self.post('bad.id')[0][0],400)
        self.job(state='completed');before=(self.control.jobs/'sample.completed.json').read_bytes()
        self.assertEqual(self.post()[0][0],409)
        self.assertEqual(self.post(authorized=False),[])
        self.assertEqual(before,(self.control.jobs/'sample.completed.json').read_bytes())

    def test_unmanaged_or_reused_supervisor_identity_is_not_cancelled(self):
        self.job(state='slicing')
        self.assertEqual(self.post()[0][0],409)
        module.atomic_json(self.control.run/'sample-owner.json',{'supervisor_pid':os.getpid(),'identity':['old-boot','0']})
        self.assertEqual(self.post()[0][0],409)
        self.assertFalse(self.control.request_path('sample').exists())

    def test_partial_and_failed_artifacts_are_not_downloadable(self):
        out=self.control.output/'sample';out.mkdir();(out/'plate_1.gcode').write_bytes(b'partial')
        for state in ['queued','slicing','failed','cancelled']:
            with self.subTest(state=state):
                path=self.job(state=state)
                self.assertIsNone(self.worker['result_file']('sample'))
                path.unlink()
        self.job(state='completed')
        self.assertIsNotNone(self.worker['result_file']('sample'))

    def test_release_cannot_resurrect_cancelled_job(self):
        self.job();self.post()
        self.assertEqual(self.worker['release_job']('sample')['status'],409)
        self.assertFalse((self.control.jobs/'sample.queued.json').exists())

    def test_cleanup_preserves_prefix_sibling_runtime_and_external_symlink_targets(self):
        self.job('sample');self.job('sample-child')
        sibling=self.control.run/'sample-child-process.json';sibling.write_text('keep sibling')
        own=self.control.run/'sample-process.json';own.write_text('remove own')
        external=self.base/'external';external.mkdir();(external/'keep.txt').write_text('keep external')
        if os.name == 'posix':
            (self.control.output/'sample').symlink_to(external,target_is_directory=True)
            (self.control.run/'sample-xdg').symlink_to(external,target_is_directory=True)
        self.assertEqual(self.post()[0][1]['status'],'cancelled')
        self.assertTrue(sibling.exists());self.assertFalse(own.exists());self.assertTrue((external/'keep.txt').exists())
        self.worker['delete_job']('sample')
        self.assertTrue(sibling.exists());self.assertTrue((external/'keep.txt').exists())

    def test_polling_and_cancellation_share_consistent_state(self):
        from concurrent.futures import ThreadPoolExecutor
        for index in range(30):self.job(f'race-{index:02}')
        def cancel(index):return self.post(f'race-{index:02}')
        def poll(_index):return self.worker['list_jobs']()
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures=[executor.submit(cancel,i) if i%2 else executor.submit(poll,i) for i in range(30)]
            for future in futures:future.result(timeout=5)
        rows=self.worker['list_jobs']()
        self.assertEqual(len(rows),30)
        self.assertEqual(sum(row['status']=='cancelled' for row in rows),15)

    def test_fifty_queued_jobs_cancel_independently(self):
        for i in range(50):self.job(f'queue-{i:02}')
        started=time.monotonic()
        for i in range(50):self.assertEqual(self.post(f'queue-{i:02}')[0][1]['status'],'cancelled')
        jobs=self.worker['list_jobs']()
        self.assertEqual(len(jobs),50);self.assertTrue(all(j['status']=='cancelled' for j in jobs))
        self.assertFalse(list(self.control.jobs.glob('*.queued.json')))
        self.assertLess(time.monotonic()-started,10)

    def test_concurrent_create_same_id_has_one_commit_under_shared_job_lock(self):
        from concurrent.futures import ThreadPoolExecutor
        from contextlib import contextmanager
        worker=self.worker;globals_=worker['Handler'].do_POST.__globals__
        (worker['PROFILES']/'test-printer.json').write_text('{}')
        (worker['UPLOADS']/'model.stl').write_bytes(b'test-only')
        payload={'job_id':'same-id','input_file':'model.stl','printer_profile':'test-printer','manual_release':True}
        writing=threading.Event();release=threading.Event();second_lock=threading.Event()
        original_write=globals_['atomic_json'];original_lock=worker['JOB_CONTROL'].lock
        lock_calls=[];writes=[]
        @contextmanager
        def observed_lock(job_id):
            lock_calls.append(job_id)
            if len(lock_calls)==2:second_lock.set()
            with original_lock(job_id):yield
        def held_write(path,value):
            writes.append(path);writing.set()
            if not release.wait(3):raise TimeoutError('test writer not released')
            return original_write(path,value)
        def create():
            handler=object.__new__(worker['Handler']);handler.path='/api/v1/jobs'
            handler.require_authorization=lambda:True
            handler.read_body=lambda _limit:json.dumps(payload).encode()
            replies=[];handler.send_json=lambda status,body:replies.append((status,body))
            handler.do_POST();return replies[0]
        with patch.object(worker['JOB_CONTROL'],'lock',observed_lock),patch.dict(globals_,{'atomic_json':held_write}):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first=executor.submit(create)
                try:
                    self.assertTrue(writing.wait(2));second=executor.submit(create)
                    self.assertTrue(second_lock.wait(2))
                finally:release.set()
                replies=[first.result(timeout=3),second.result(timeout=3)]
        self.assertEqual(sorted(status for status,_ in replies),[202,409])
        self.assertEqual(len(writes),1)
        self.assertEqual(module.read_json(worker['JOBS']/'same-id.queued.json')['job_id'],'same-id')


@unittest.skipUnless(sys.platform.startswith('linux'), 'Native process group tests require Linux')
class LinuxCancellationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.control=JobControl(self.base)
        (self.control.jobs/'sample.queued.json').write_text(json.dumps({'job_id':'sample','manual_release':False}))

    def run_dispatch(self, body):
        script=self.base/'dispatch-job.sh';script.write_text(body)
        results=[];errors=[]
        def run():
            try:results.append(self.control.dispatch(script,term_timeout=.2,kill_timeout=1,poll_interval=.01))
            except Exception as exc:errors.append(exc)
        thread=threading.Thread(target=run);thread.start()
        return thread,results,errors

    def wait_file(self,path):
        until=time.monotonic()+3
        while not path.exists() and time.monotonic()<until:time.sleep(.01)
        self.assertTrue(path.exists())

    def test_terminate_owned_process_group_with_grandchild_and_cleanup(self):
        marker=self.base/'ready';childfile=self.base/'child'
        script=f'''#!/bin/sh
mkdir -p "$STUDIO_WORKER_BASE/data/output/sample"
echo partial > "$STUDIO_WORKER_BASE/data/output/sample/plate_1.gcode"
trap '' TERM
python3 -c 'import os,signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); open("{childfile}","w").write(str(os.getpid())); time.sleep(30)' &
touch "{marker}"
wait
'''
        thread,results,errors=self.run_dispatch(script)
        self.wait_file(marker);self.wait_file(childfile)
        started=time.monotonic();reply=self.control.cancel('sample')
        self.assertEqual(reply['status'],'cancelling')
        self.assertTrue(self.control.cancel('sample')['already_requested'])
        thread.join(4)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(results[0]['status'],'cancelled');self.assertLess(time.monotonic()-started,3)
        self.assertFalse((self.control.output/'sample').exists())
        self.assertIsNone(module.process_identity(int(childfile.read_text())))
        self.assertEqual(self.control.cancel('sample')['status'],'cancelled')

    def test_manual_hold_and_unmanaged_active_job_fail_closed(self):
        (self.control.jobs/'sample.queued.json').write_text('{"manual_release":true}')
        script=self.base/'unused.sh';script.write_text('exit 99')
        self.assertEqual(self.control.dispatch(script)['status'],'idle')
        (self.control.jobs/'old.slicing.json').write_text('{}')
        self.assertEqual(self.control.dispatch(script)['status'],'blocked')

    def test_cancellation_wins_even_if_child_writes_completed_after_term(self):
        marker=self.base/'ready'
        script=f'''#!/bin/sh
trap 'mv "$STUDIO_JOB_PATH" "$STUDIO_WORKER_BASE/data/jobs/sample.completed.json"; exit 0' TERM
touch "{marker}"
while :; do sleep .1; done
'''
        thread,results,errors=self.run_dispatch(script);self.wait_file(marker)
        self.control.cancel('sample');thread.join(4)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(results[0]['status'],'cancelled')
        self.assertFalse((self.control.jobs/'sample.completed.json').exists())

    def test_invalid_queued_json_becomes_failed_and_cannot_block_queue(self):
        (self.control.jobs/'sample.queued.json').write_text('broken json')
        script=self.base/'unused.sh';script.write_text('exit 99')
        self.assertEqual(self.control.dispatch(script)['status'],'idle')
        self.assertFalse((self.control.jobs/'sample.queued.json').exists())
        result=module.read_json(self.control.output/'sample.result.json')
        self.assertEqual(result['error'],'invalid_job_json')

    def test_completed_result_is_not_terminal_until_process_group_exits(self):
        marker=self.base/'ready';release=self.base/'finish'
        body=f'''#!/bin/sh
echo '{{"job_id":"sample","status":"completed"}}' > "$STUDIO_WORKER_BASE/data/output/sample.result.json"
touch "{marker}"
while [ ! -f "{release}" ]; do sleep .01; done
'''
        thread,results,errors=self.run_dispatch(body);self.wait_file(marker)
        self.assertEqual(self.control.state('sample')[0],'slicing')
        release.touch();thread.join(3)
        self.assertEqual(errors,[]);self.assertEqual(results[0]['status'],'completed')
        self.assertFalse((self.control.jobs/'sample.slicing.json').exists())

    def test_actual_dispatch_shell_consumes_claimed_job_without_native_slice(self):
        # Unknown test engine deliberately exercises the real shell error path only.
        profiles=self.base/'profiles/printers';profiles.mkdir(parents=True)
        (profiles/'test-printer.json').write_text('{"compatible_engines":["test-engine"]}')
        uploads=self.base/'data/uploads';uploads.mkdir(parents=True)
        (uploads/'model.stl').write_text('test-only')
        (self.base/'bed-temperature-contract.sh').write_text(':\n')
        (self.base/'refresh-state.sh').write_text(':\n')
        (self.control.jobs/'sample.queued.json').write_text(json.dumps({'job_id':'sample','manual_release':False,'engine':'test-engine','printer_profile':'test-printer','input_file':'model.stl'}))
        result=self.control.dispatch(WORKER/'dispatch-job.sh',term_timeout=.2,kill_timeout=1)
        self.assertEqual(result['status'],'failed')
        self.assertFalse((self.control.jobs/'sample.slicing.json').exists())
        self.assertFalse((self.control.jobs/'sample.queued.json').exists())
        self.assertIn('Unknown engine: test-engine',(self.control.output/'sample.log').read_text())

    def test_unexpected_exit_becomes_failed_without_blocking_next_job(self):
        thread,results,errors=self.run_dispatch('exit 7\n');thread.join(3)
        self.assertEqual(errors,[]);self.assertEqual(results[0]['status'],'failed')
        self.assertFalse((self.control.run/'sample-owner.json').exists())
        self.assertEqual(self.control.dispatch(self.base/'dispatch-job.sh')['status'],'idle')

    def test_dead_leader_with_live_group_member_never_commits_or_cleans_artifacts(self):
        # Deterministically represent a killed leader with a child still in kernel I/O.
        # No OS process is signalled: Popen, waitid, killpg and /proc inspection are doubles.
        process=Mock(pid=12345,returncode=None)
        output=self.control.output/'sample';output.mkdir();(output/'plate_1.gcode').write_bytes(b'partial')
        script=self.base/'unused.sh';script.write_text('exit 0')
        module.atomic_json(self.control.output/'sample.result.json',{'job_id':'sample','status':'completed'})
        with patch.object(module.subprocess,'Popen',return_value=process), \
             patch.object(module.os,'waitid',return_value=object()), \
             patch.object(module.os,'killpg') as kill, \
             patch.object(module,'live_group_members',return_value=[12346]):
            result=self.control.dispatch(script,term_timeout=0,kill_timeout=0)
        self.assertEqual(result['status'],'cancelling');self.assertTrue(result['requires_recovery'])
        self.assertEqual(result['error'],'owned_process_group_still_running')
        self.assertEqual([call.args[1] for call in kill.call_args_list],[module.signal.SIGTERM,module.signal.SIGKILL])
        process.wait.assert_not_called()
        self.assertTrue((output/'plate_1.gcode').exists())
        self.assertTrue((self.control.jobs/'sample.slicing.json').exists())
        self.assertFalse((self.control.jobs/'sample.cancelled.json').exists())
        self.assertEqual(self.control.dispatch(script)['status'],'blocked')

    def test_unreadable_process_snapshot_fails_closed(self):
        with patch.object(module.Path,'iterdir',side_effect=PermissionError('test only')):
            with self.assertRaises(module.ProcessGroupStillRunning):module.live_group_members(12345)


if __name__=='__main__':unittest.main()
