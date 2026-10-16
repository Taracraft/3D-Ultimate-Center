"""Read-only Supervisor observations and local receipt recovery; synthetic IO only.

No real Supervisor, app, engine or printer is accessed. Reconciliation adopts a
currently verified stopped instance; it does not prove the original call succeeded.
"""
from __future__ import annotations
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('studio_recovery_setup_fixture',ROOT/'tests/test_studio_supervisor_app_setup.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
app=f.app


def job(n=1, *, done=True, children=None):
    return SimpleNamespace(uuid=UUID(int=n),done=done,child_jobs=children or [],errors=[],
                           name='private-job-name',reference='private-reference',extra={'secret':'private-secret'})


class RecoveryFixture(f.SessionFixture):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.client.installed=True
        self.journal.record={'schema':1,'release':f.RELEASE.identity,'state':'pending'}
        self.pending=copy.deepcopy(self.journal.record)
        self.info=SimpleNamespace(ignore_conditions=[],jobs=[job()])
        self.jobs_reads=0
        async def read_jobs():
            self.jobs_reads+=1
            return self.info
        self.client.jobs=SimpleNamespace(info=read_jobs)
    async def reconcile(self,confirmed=True):
        return await self.session.async_run('reconcile','admin',confirmed=confirmed)
    def no_remote_writes(self):
        self.assertNotIn('install',[c[0] for c in self.client.calls])
    def pending_preserved(self):
        self.assertEqual(self.journal.record,self.pending)
        self.assertEqual(self.journal.saves,[])
        self.no_remote_writes()


class RecoveryTests(RecoveryFixture):
    async def test_pending_status_can_review_stopped_instance_without_writing(self):
        result=await self.run_action('status')
        self.assertEqual(result,{'ok':True,'state':'recovery_available'})
        self.pending_preserved()
        self.assertGreaterEqual(self.jobs_reads,2)

    async def test_explicit_reconciliation_is_local_adoption_not_original_install_success(self):
        result=await self.reconcile()
        self.assertEqual(result,{'ok':True,'state':'reconciled_stopped'})
        self.assertEqual(self.journal.record,{'schema':1,'release':f.RELEASE.identity,'state':'reconciled_stopped'})
        self.assertEqual(len(self.journal.saves),1)
        self.no_remote_writes()
        self.assertNotIn('private-',str(result))

    async def test_confirmation_must_be_exact_boolean(self):
        for value in (False,None,1,'true',[]):
            with self.subTest(value=value):
                self.assertEqual((await self.reconcile(value))['error'],'app_confirmation_required')
        self.assertEqual(self.client.calls,[]);self.pending_preserved()

    async def test_missing_app_does_not_clear_the_pending_attempt(self):
        self.client.installed=False
        self.assertEqual((await self.reconcile())['error'],'app_reconciliation_required')
        self.pending_preserved()

    async def test_running_startup_unknown_and_error_are_never_stopped_or_adopted(self):
        for state in ('started','startup','error','unknown'):
            with self.subTest(state=state):
                self.client.state=state;self.assertFalse((await self.reconcile())['ok'])
                self.pending_preserved()

    async def test_wrong_version_is_never_adopted(self):
        self.client.version='9.9.9'
        self.assertEqual((await self.reconcile())['error'],'app_version_mismatch')
        self.pending_preserved()

    async def test_changed_policy_is_not_bypassed_during_recovery(self):
        for changed in ({'docker_api':True},{'protected':False},{'privileged':['SYS_ADMIN']},{'boot':'auto'}):
            with self.subTest(changed=changed):
                self.client.changed=changed
                self.assertEqual((await self.reconcile())['error'],'app_policy_mismatch')
                self.pending_preserved()

    async def test_any_running_job_blocks_including_unrelated_or_child_job(self):
        for roots in ([job(done=False)],[job(children=[job(2,done=False)])],[job(done=None)]):
            with self.subTest(roots=roots):
                self.info.jobs=roots
                self.assertEqual((await self.reconcile())['error'],'app_jobs_active')
                self.pending_preserved()

    async def test_ignored_supervisor_conditions_block(self):
        self.info.ignore_conditions=['healthy']
        self.assertEqual((await self.reconcile())['error'],'app_policy_mismatch')
        self.pending_preserved()

    async def test_lost_or_corrupt_journal_is_not_a_recovery_request(self):
        for record in (None,{}, {'schema':1,'release':'other','state':'pending'},
                       {'schema':True,'release':f.RELEASE.identity,'state':'pending'}):
            with self.subTest(record=record):
                self.journal.record=record
                self.assertFalse((await self.reconcile())['ok'])
                self.assertEqual(self.journal.saves,[]);self.no_remote_writes()

    async def test_pending_legacy_record_preserves_unknown_original_outcome(self):
        self.info.jobs=[]  # There is intentionally no old job to claim as successful.
        result=await self.reconcile()
        self.assertEqual(result['state'],'reconciled_stopped')
        self.assertNotEqual(self.journal.record['state'],'installed_stopped')
        self.no_remote_writes()

    async def test_second_reconciliation_is_idempotent_without_more_saves(self):
        self.assertTrue((await self.reconcile())['ok'])
        self.assertEqual((await self.reconcile())['state'],'reconciled_stopped')
        self.assertEqual(len(self.journal.saves),1);self.no_remote_writes()

    async def test_adopted_outcome_survives_session_recreation(self):
        await self.reconcile()
        recreated=app.SupervisorAppSession(self.hass,release_provider=lambda:f.RELEASE,
            backend_factory=lambda _:app.SupervisorBackend(self.client),journal_factory=lambda _:self.journal)
        self.assertEqual((await recreated.async_run('status','admin'))['state'],'reconciled_stopped')
        self.assertEqual(len(self.journal.saves),1)

    async def test_after_adoption_external_uninstall_still_cannot_trigger_new_install(self):
        await self.reconcile();self.client.installed=False
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.no_remote_writes()

    async def test_not_yet_reconciled_install_action_remains_blocked(self):
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.pending_preserved()

    async def test_no_shipped_release_never_touches_supervisor_or_journal(self):
        self.release[0]=None
        self.assertEqual((await self.reconcile())['error'],'app_release_unavailable')
        self.assertEqual(self.client.calls,[]);self.assertEqual(self.jobs_reads,0)
        self.assertEqual(self.journal.loads,0)

    async def test_inactive_or_nonadmin_user_cannot_adopt(self):
        for change in ('is_admin','is_active'):
            setattr(self.hass.user,change,False)
            self.assertEqual((await self.reconcile())['error'],'forbidden')
            setattr(self.hass.user,change,True)
        self.assertEqual(self.client.calls,[]);self.pending_preserved()

    async def test_new_job_between_observations_blocks(self):
        original=self.client.jobs.info
        async def changed():
            info=await original()
            if self.jobs_reads==2:info.jobs.append(job(3))
            return info
        self.client.jobs.info=changed
        self.assertEqual((await self.reconcile())['error'],'app_recovery_changed')
        self.pending_preserved()

    async def test_active_job_appearing_during_app_inspection_blocks(self):
        original=self.client.installed_info
        async def changed(name):
            result=await original(name);self.info.jobs[0].done=False;return result
        self.client.addons.addon_info=changed
        self.assertEqual((await self.reconcile())['error'],'app_jobs_active')
        self.pending_preserved()

    async def test_receipt_changes_during_review_are_not_overwritten(self):
        original=self.client.jobs.info
        async def changed():
            result=await original()
            if self.jobs_reads==2:self.journal.record={'schema':1,'release':'foreign','state':'pending'}
            return result
        self.client.jobs.info=changed
        self.assertFalse((await self.reconcile())['ok'])
        self.assertEqual(self.journal.record['release'],'foreign')
        self.assertEqual(self.journal.saves,[]);self.no_remote_writes()

    async def test_permission_revoked_on_final_job_read_blocks_local_save(self):
        original=self.client.jobs.info
        async def changed():
            result=await original()
            self.hass.user.is_admin=False
            return result
        self.client.jobs.info=changed
        self.assertEqual((await self.reconcile())['error'],'forbidden')
        self.pending_preserved()

    async def test_unload_or_release_change_during_last_user_lookup_blocks(self):
        original=self.hass.auth.async_get_user
        count=0
        async def changed(uid):
            nonlocal count
            value=await original(uid);count+=1
            if count==2:self.session.invalidate()
            return value
        self.hass.auth.async_get_user=changed
        self.assertEqual((await self.reconcile())['error'],'app_closed')
        self.pending_preserved()

    async def test_jobs_transport_error_is_redacted_and_preserves_intent(self):
        async def failed():raise RuntimeError('private-secret-error')
        self.client.jobs.info=failed
        result=await self.reconcile();self.assertFalse(result['ok'])
        self.assertNotIn('private-',str(result));self.pending_preserved()

    async def test_jobs_timeout_keeps_session_available_and_does_not_mutate(self):
        async def blocked():await asyncio.Event().wait()
        self.client.jobs.info=blocked;self.session._read_timeout=0.02
        result=await self.reconcile();self.assertFalse(result['ok'])
        self.assertFalse(self.session.busy);self.pending_preserved()

    async def test_save_failure_preserves_unknown_outcome(self):
        self.journal.fail_save=1
        result=await self.reconcile();self.assertEqual(result['error'],'app_storage_failed')
        self.assertEqual(self.journal.record,self.pending);self.no_remote_writes()

    async def test_false_save_success_is_detected_by_readback(self):
        async def silent(value):self.journal.saves.append(copy.deepcopy(value))
        self.journal.async_save=silent
        result=await self.reconcile();self.assertEqual(result['error'],'app_storage_failed')
        self.assertEqual(self.journal.record,self.pending);self.no_remote_writes()

    async def test_browser_cancellation_does_not_cancel_owner_or_duplicate_work(self):
        entered=asyncio.Event();finish=asyncio.Event();original=self.client.jobs.info
        async def wait():entered.set();await finish.wait();return await original()
        self.client.jobs.info=wait
        task=asyncio.create_task(self.reconcile());await entered.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual((await self.reconcile())['error'],'app_busy')
        finish.set();await self.session._active
        self.assertEqual(self.session.snapshot()['result']['state'],'reconciled_stopped')
        self.assertEqual(len(self.journal.saves),1);self.no_remote_writes()

    async def test_post_save_state_drift_does_not_report_ready(self):
        original=self.journal.async_save
        async def change(value):await original(value);self.client.state='started'
        self.journal.async_save=change
        result=await self.reconcile();self.assertFalse(result['ok'])
        self.assertEqual(self.journal.record['state'],'reconciled_stopped')
        self.no_remote_writes()


class JobsModelTests(RecoveryFixture):
    async def test_completed_nested_jobs_and_errors_do_not_claim_original_success(self):
        self.info.jobs=[job(children=[job(2)])];self.info.jobs[0].errors=[SimpleNamespace(message='private')]
        self.assertEqual((await self.reconcile())['state'],'reconciled_stopped')
        self.no_remote_writes()

    async def test_cycle_duplicate_uuid_and_unknown_done_are_rejected(self):
        cycle=job();cycle.child_jobs=[cycle]
        for value in ([cycle],[job(),job()],[job(done=1)]):
            with self.subTest(value=str(value)[:40]):
                self.info.jobs=value;self.assertFalse((await self.reconcile())['ok'])
                self.pending_preserved()

    async def test_invalid_job_uuid_and_child_shape_rejected(self):
        for attr,value in (('uuid','not-a-uuid'),('uuid',UUID(int=0)),('child_jobs',()),('errors',None)):
            with self.subTest(attr=attr,value=value):
                root=job();setattr(root,attr,value);self.info.jobs=[root]
                self.assertFalse((await self.reconcile())['ok']);self.pending_preserved()

    async def test_job_limit_is_bounded(self):
        self.info.jobs=[job(n) for n in range(1,2050)]
        self.assertEqual((await self.reconcile())['error'],'app_jobs_invalid');self.pending_preserved()

    async def test_nested_depth_is_bounded(self):
        root=job();node=root
        for n in range(2,70):child=job(n);node.child_jobs=[child];node=child
        self.info.jobs=[root]
        self.assertEqual((await self.reconcile())['error'],'app_jobs_invalid');self.pending_preserved()

    async def test_job_order_is_not_state_change(self):
        self.info.jobs=[job(),job(2)];original=self.client.jobs.info
        async def reordered():result=await original();result.jobs.reverse();return result
        self.client.jobs.info=reordered
        self.assertEqual((await self.reconcile())['state'],'reconciled_stopped')

    async def test_empty_jobs_is_idle_not_absent_supervisor_response(self):
        self.info.jobs=[]
        self.assertEqual((await self.run_action('status'))['state'],'recovery_available')
        self.pending_preserved()


class RecoveryFlowTests(RecoveryFixture):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.flow=f.Flow(self.hass,SimpleNamespace(options={'secret':'untouched'}),self.session)
        token=f.REQUEST.set({'ha_authenticated':True,'hass_user':self.hass.user})
        self.addCleanup(f.REQUEST.reset,token)
    async def show(self):
        progress=await self.flow.async_step_slicer_supervisor();await progress['progress_task']
        await self.flow.async_step_slicer_supervisor_progress()
        return await self.flow.async_step_slicer_supervisor_result()
    async def test_review_offers_reconcile_not_install(self):
        form=await self.show()
        self.assertEqual(form['data_schema'].schema['operation'].config['options'],['status','reconcile','back'])
        self.pending_preserved()
    async def test_separate_confirmation_then_current_actor_adopts(self):
        await self.show()
        confirm=await self.flow.async_step_slicer_supervisor({'operation':'reconcile'})
        self.assertEqual(confirm['step_id'],'slicer_supervisor_reconcile')
        self.pending_preserved()
        progress=await self.flow.async_step_slicer_supervisor_reconcile({'confirm':True})
        await progress['progress_task'];await self.flow.async_step_slicer_supervisor_progress()
        form=await self.flow.async_step_slicer_supervisor_result()
        self.assertEqual(form['description_placeholders']['state'],'reconciled_stopped')
        self.assertEqual(form['data_schema'].schema['operation'].config['options'],['status','back'])
        self.assertEqual(self.flow.config_entry.options,{'secret':'untouched'});self.no_remote_writes()
    async def test_decline_does_not_write_or_start(self):
        await self.show();await self.flow.async_step_slicer_supervisor({'operation':'reconcile'})
        result=await self.flow.async_step_slicer_supervisor_reconcile({'confirm':False})
        self.assertEqual(result['type'],'form');self.pending_preserved()
    async def test_reconcile_direct_submission_without_release_remains_blocked(self):
        self.release[0]=None
        await self.flow.async_step_slicer_supervisor({'operation':'reconcile'})
        progress=await self.flow.async_step_slicer_supervisor_reconcile({'confirm':True})
        await progress['progress_task']
        self.assertEqual(self.session.snapshot()['result']['error'],'app_release_unavailable')
        self.assertEqual(self.client.calls,[])
    async def test_actor_change_on_confirmation_cannot_reconcile(self):
        await self.show();await self.flow.async_step_slicer_supervisor({'operation':'reconcile'})
        f.REQUEST.set({'ha_authenticated':True,'hass_user':SimpleNamespace(id='other')})
        progress=await self.flow.async_step_slicer_supervisor_reconcile({'confirm':True})
        await progress['progress_task'];self.pending_preserved()
    async def test_stale_form_does_not_bypass_fresh_pending_inspection(self):
        await self.show();self.client.state='started'
        await self.flow.async_step_slicer_supervisor({'operation':'reconcile'})
        progress=await self.flow.async_step_slicer_supervisor_reconcile({'confirm':True})
        await progress['progress_task'];self.assertFalse(self.session.snapshot()['result']['ok'])
        self.pending_preserved()


if __name__=='__main__':unittest.main()
