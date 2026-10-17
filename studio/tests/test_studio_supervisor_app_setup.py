"""Supervisor setup integration contracts; no real HA, Supervisor, engine or network.

Production backend methods run against explicit official-client-shaped objects.
The native flow schema/rendering and HA Store are isolated test boundaries.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from contextvars import ContextVar
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / 'deploy/homeassistant/custom_components/ultimate_3d_studio'
PKG = 'studio_supervisor_app_setup_tests'
REQUEST = ContextVar("synthetic_authenticated_request", default=None)
package = sys.modules.setdefault(PKG, ModuleType(PKG)); package.__path__ = [str(COMP)]
const = ModuleType(PKG + '.const'); const.DOMAIN = 'ultimate_3d_studio'; sys.modules[const.__name__] = const
spec = importlib.util.spec_from_file_location(PKG + '.slicer_supervisor_app', COMP / 'slicer_supervisor_app.py')
app = importlib.util.module_from_spec(spec); sys.modules[spec.name] = app; spec.loader.exec_module(app)
RELEASE = app.AppRelease('deadbeef', 'deadbeef_ultimate_slicer_server', '1.2.3', 'a' * 64)


class MemoryJournal:
    def __init__(self):
        self.record = None
        self.saves = []
        self.loads = 0
        self.fail_load = False
        self.fail_save = 0
    async def async_load(self):
        self.loads += 1
        if self.fail_load: raise RuntimeError('private-store-error')
        return copy.deepcopy(self.record)
    async def async_save(self, value):
        self.saves.append(copy.deepcopy(value))
        if len(self.saves) == self.fail_save: raise RuntimeError('private-save-error')
        self.record = copy.deepcopy(value)


class Client:
    def __init__(self):
        self.calls = []
        self.installed = False
        self.state = 'stopped'
        self.version = RELEASE.version
        self.latest = RELEASE.version
        self.changed = {}
        self.repo_source = app.REPOSITORY_URL
        self.install_entered = asyncio.Event()
        self.install_finish = asyncio.Event(); self.install_finish.set()
        self.error = None
        self.on_install = None
        self.store = SimpleNamespace(repository_info=self.repository_info, addon_info=self.store_info,
                                     install_addon=self.install)
        self.addons = SimpleNamespace(addon_info=self.installed_info)
    def info(self):
        return dict(slug=RELEASE.slug, repository=RELEASE.repository, available=True, build=False,
                    detached=False, host_network=False, host_pid=False, full_access=False,
                    docker_api=False, homeassistant_api=False, supervisor_api=False, auth_api=False,
                    apparmor='profile', arch=['amd64'], version_latest=self.latest, installed=self.installed,
                    version=self.version, protected=True, privileged=[], boot='manual',
                    boot_config='manual_only', auto_update=False, host_ipc=False, host_uts=False,
                    host_dbus=False, kernel_modules=False, state=self.state,
                    options={'secret':'never-export-this-secret'}, hostname='never-use-as-automatic-trust')
    async def repository_info(self, name):
        self.calls.append(('repository_info',name))
        return SimpleNamespace(slug=RELEASE.repository,source=self.repo_source)
    async def store_info(self, name):
        self.calls.append(('store_info',name))
        return SimpleNamespace(**(self.info() | self.changed))
    async def installed_info(self, name):
        self.calls.append(('installed_info',name))
        return SimpleNamespace(**(self.info() | self.changed))
    async def install(self, name):
        self.calls.append(('install',name)); self.install_entered.set()
        if self.on_install: self.on_install()
        await self.install_finish.wait()
        if self.error: raise self.error
        self.installed=True


class Hass:
    def __init__(self):
        self.data={}; self.config=SimpleNamespace(components={'hassio'})
        self.user=SimpleNamespace(id="admin",is_admin=True,is_active=True)
        self.auth=SimpleNamespace(async_get_user=self.get_user)
        self.tasks=[]; self.auth_calls=[]
    async def get_user(self, user):
        self.auth_calls.append(user)
        return self.user if user=='admin' else None
    def async_create_task(self, coro):
        task=asyncio.create_task(coro); self.tasks.append(task); return task


class ReleaseTests(unittest.TestCase):
    def test_no_published_app_is_fabricated(self):
        self.assertIsNone(app.shipped_release())
    def test_only_fixed_component_and_concrete_identities(self):
        values=[('deadbeef','other','1.2.3','a'*64),('00000000','00000000_ultimate_slicer_server','1.2.3','a'*64),
                ('deadbeef',RELEASE.slug,'latest','a'*64),('deadbeef',RELEASE.slug,'1.2.3','0'*64),
                (True,RELEASE.slug,'1.2.3','a'*64),('deadbeef',RELEASE.slug,True,'a'*64)]
        for valueset in values:
            with self.subTest(values=valueset),self.assertRaises(ValueError):app.AppRelease(*valueset)
    def test_reference_is_immutable_and_receipt_bound(self):
        with self.assertRaises(Exception): RELEASE.version='9.9.9'
        other=app.AppRelease(RELEASE.repository,RELEASE.slug,'1.2.4','a'*64)
        self.assertNotEqual(RELEASE.identity,other.identity)
        self.assertEqual(RELEASE.identity,copy.deepcopy(RELEASE).identity)
    def test_host_and_credential_capabilities_not_present(self):
        tree=ast.parse((COMP/'slicer_supervisor_app.py').read_bytes())
        attrs={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        for name in ('start_addon','stop_addon','uninstall_addon','update_addon','set_addon_options','add_repository'):
            self.assertNotIn(name,attrs)
        imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
        self.assertFalse(any(getattr(n,'module','') in {'subprocess','os','socket'} for n in imports))


class BackendTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client=Client();self.backend=app.SupervisorBackend(self.client)
    async def test_absent_only_reads_repository_and_store(self):
        self.assertEqual(await self.backend.inspect(RELEASE),{'ok':True,'state':'not_installed'})
        self.assertEqual([c[0] for c in self.client.calls],['repository_info','store_info'])
    async def test_installed_state_drops_all_secrets_and_hosts(self):
        self.client.installed=True
        self.assertEqual(await self.backend.inspect(RELEASE),{'ok':True,'state':'installed_stopped'})
    async def test_running_is_not_connection_or_engine_acceptance(self):
        self.client.installed=True;self.client.state='started'
        self.assertEqual(await self.backend.inspect(RELEASE),{'ok':True,'state':'running_unverified'})
    async def test_repository_origin_does_not_follow_redirects_or_fuzzy_names(self):
        for source in (app.REPOSITORY_URL+'-evil','http://github.com/Taracraft/3D-Ultimate-Slicer-Server',
                       app.REPOSITORY_URL+'?token=private','https://example.org/app.git'):
            with self.subTest(source=source),self.assertRaises(app.AppError):
                self.client.repo_source=source;await self.backend.inspect(RELEASE)
        self.client.repo_source=app.REPOSITORY_URL+'.git'
        self.assertTrue((await self.backend.inspect(RELEASE))['ok'])
    async def test_foreign_slug_or_repository_is_rejected(self):
        for field in ('slug','repository'):
            with self.subTest(field=field),self.assertRaises(app.AppError):
                self.client.changed={field:'other'};await self.backend.inspect(RELEASE)
    async def test_preinstall_store_policy_is_not_relaxed(self):
        changes=[{key:True} for key in ('build','detached','host_network','host_pid','full_access',
                    'docker_api','homeassistant_api','supervisor_api','auth_api')]
        changes += [{'apparmor':'disable'},{'arch':['aarch64']},{'arch':['amd64','aarch64']},{'available':1},{'installed':1}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises(app.AppError):
                self.client.changed=change;await self.backend.inspect(RELEASE)
    async def test_installed_policy_cannot_gain_privileges_or_autostart(self):
        self.client.installed=True
        for change in ({'protected':False},{'privileged':['SYS_ADMIN']},{'boot':'auto'},
                       {'boot_config':'auto'},{'auto_update':True},{'host_ipc':True},
                       {'host_uts':True},{'host_dbus':True},{'kernel_modules':True}):
            with self.subTest(change=change),self.assertRaises(app.AppError):
                self.client.changed=change;await self.backend.inspect(RELEASE)
    async def test_latest_and_installed_version_are_both_bound(self):
        self.client.latest='1.2.4'
        with self.assertRaises(app.AppError):await self.backend.inspect(RELEASE)
        self.client.latest=RELEASE.version;self.client.installed=True;self.client.version='1.2.2'
        with self.assertRaises(app.AppError):await self.backend.inspect(RELEASE)
    async def test_error_unknown_state_not_promoted(self):
        self.client.installed=True
        for state in ('unknown','error','private-token',None):
            with self.subTest(state=state),self.assertRaises(app.AppError):
                self.client.state=state;await self.backend.inspect(RELEASE)
    async def test_install_uses_only_official_install_method(self):
        await self.backend.install(RELEASE)
        self.assertEqual(self.client.calls,[('install',RELEASE.slug)])


class SessionFixture(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.hass=Hass();self.client=Client();self.journal=MemoryJournal();self.release=[RELEASE]
        self.factories=[]
        def backend(hass):self.factories.append(hass);return app.SupervisorBackend(self.client)
        self.session=app.SupervisorAppSession(self.hass,release_provider=lambda:self.release[0],
                    backend_factory=backend,journal_factory=lambda hass:self.journal,read_timeout=1,install_timeout=1)
    async def asyncTearDown(self):
        self.client.install_finish.set()
        if self.hass.tasks:await asyncio.gather(*self.hass.tasks,return_exceptions=True)
    async def run_action(self,action='install',**kwargs):
        return await self.session.async_run(action,'admin',confirmed=True,**kwargs)


class SessionTests(SessionFixture):
    async def test_construction_is_lazy_no_import_install_or_storage(self):
        self.assertEqual(self.factories,[]);self.assertEqual(self.client.calls,[]);self.assertEqual(self.journal.loads,0)
    async def test_pending_release_never_touches_supervisor_or_journal(self):
        self.release[0]=None
        for action in ('status','install'):
            self.assertEqual((await self.run_action(action))['error'],'app_release_unavailable')
        self.assertEqual(self.factories,[]);self.assertEqual(self.client.calls,[]);self.assertEqual(self.journal.saves,[])
    async def test_non_supervisor_installation_does_not_fall_back(self):
        self.hass.config.components=set()
        self.assertEqual((await self.run_action())['error'],'supervisor_unavailable')
        self.assertEqual(self.factories,[])
    async def test_admin_and_active_user_required_even_for_read(self):
        for user in (None,SimpleNamespace(is_admin=False,is_active=True),SimpleNamespace(is_admin=True,is_active=False),SimpleNamespace(is_admin=1,is_active=True)):
            self.hass.user=user
            with self.subTest(user=user):self.assertEqual((await self.run_action('status'))['error'],'forbidden')
        self.assertEqual(self.client.calls,[])
    async def test_missing_or_wrong_user_identity_is_not_a_token(self):
        for uid in (None,'','someone-else',True,[]):
            with self.subTest(uid=uid):self.assertEqual((await self.session.async_run('status',uid))['error'],'forbidden')
    async def test_install_requires_exact_explicit_confirmation(self):
        for flag in (False,None,1,'yes'):
            with self.subTest(flag=flag):
                result=await self.session.async_run('install','admin',confirmed=flag)
                self.assertEqual(result['error'],'app_confirmation_required')
        self.assertEqual(self.client.calls,[])
    async def test_status_no_writes_and_no_secrets(self):
        result=await self.run_action('status')
        self.assertEqual(result,{'ok':True,'state':'not_installed'})
        self.assertEqual(self.journal.saves,[]);self.assertNotIn('secret',str(self.session.snapshot()))
    async def test_install_stays_stopped_and_persists_before_mutation(self):
        self.client.on_install=lambda:self.assertEqual(self.journal.record['state'],'pending')
        result=await self.run_action()
        self.assertEqual(result,{'ok':True,'state':'installed_stopped'})
        self.assertEqual([v['state'] for v in self.journal.saves],['pending','installed_stopped'])
        self.assertEqual([c[0] for c in self.client.calls].count('install'),1)
        self.assertEqual(self.hass.auth_calls,['admin','admin'])
    async def test_second_install_does_not_reinstall_or_start(self):
        await self.run_action();await self.run_action()
        self.assertEqual([c[0] for c in self.client.calls].count('install'),1)
        self.assertEqual(len(self.journal.saves),2)
    async def test_already_running_left_unchanged(self):
        self.client.installed=True;self.client.state='started'
        self.assertEqual((await self.run_action())['state'],'running_unverified')
        self.assertEqual(self.journal.saves,[]);self.assertNotIn('install',[c[0] for c in self.client.calls])
    async def test_corrupt_or_pending_journal_never_retries(self):
        for record in ({},{'schema':True,'release':RELEASE.identity,'state':'pending'},
                       {'schema':1,'release':RELEASE.identity,'state':'pending'},
                       {'schema':1,'release':'different','state':'installed_stopped'}):
            with self.subTest(record=record):
                self.journal.record=record
                self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertEqual(self.client.calls,[])
    async def test_store_load_error_does_not_become_absence(self):
        self.journal.fail_load=True
        self.assertEqual((await self.run_action())['error'],'app_storage_failed')
        self.assertEqual(self.client.calls,[])
    async def test_intent_save_failure_prevents_mutation(self):
        self.journal.fail_save=1
        self.assertEqual((await self.run_action())['error'],'app_storage_failed')
        self.assertNotIn('install',[c[0] for c in self.client.calls])
    async def test_final_save_failure_never_reports_success(self):
        self.journal.fail_save=2
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertEqual(self.journal.record['state'],'pending')
    async def _assert_context_change_during_final_receipt_save(self, change_context):
        entered = asyncio.Event()
        finish = asyncio.Event()
        original_save = self.journal.async_save

        async def delayed_final_save(value):
            if value["state"] == "installed_stopped":
                entered.set()
                await finish.wait()
            await original_save(value)

        self.journal.async_save = delayed_final_save
        action = asyncio.create_task(self.run_action())
        try:
            async with asyncio.timeout(1):
                await entered.wait()
            change_context()
        finally:
            finish.set()
        result = await action

        # The remote install already happened. Reject only stale success;
        # do not pretend to undo it, erase its receipt or install a second time.
        self.assertTrue(self.client.installed)
        self.assertEqual(self.client.state, "stopped")
        self.assertEqual([call[0] for call in self.client.calls].count("install"), 1)
        self.assertEqual(self.journal.record,
            {"schema": 1, "release": RELEASE.identity, "state": "installed_stopped"})
        self.assertEqual([value["state"] for value in self.journal.saves],
            ["pending", "installed_stopped"])
        self.assertEqual(result,
            {"ok": False, "state": "blocked", "error": "app_reconciliation_required"})
        self.assertEqual(self.session.snapshot()["result"], result)
        self.assertFalse((await self.run_action())["ok"])
        self.assertEqual([call[0] for call in self.client.calls].count("install"), 1)
        self.assertEqual(self.journal.record["state"], "installed_stopped")

    async def test_unload_during_final_receipt_save_rejects_stale_success(self):
        await self._assert_context_change_during_final_receipt_save(self.session.invalidate)

    async def test_release_change_during_final_receipt_save_rejects_stale_success(self):
        await self._assert_context_change_during_final_receipt_save(
            lambda: self.release.__setitem__(0, None))

    async def test_request_failure_remains_unknown_across_session_recreation(self):
        self.client.error=RuntimeError('token-private-DO-NOT-EXPOSE')
        result=await self.run_action();self.assertEqual(result['error'],'app_reconciliation_required')
        self.assertNotIn('private',str(result))
        recreated=app.SupervisorAppSession(self.hass,release_provider=lambda:RELEASE,
            backend_factory=lambda hass:app.SupervisorBackend(self.client),journal_factory=lambda hass:self.journal)
        result=await recreated.async_run('install','admin',confirmed=True)
        self.assertEqual(result['error'],'app_reconciliation_required')
        self.assertEqual([c[0] for c in self.client.calls].count('install'),1)
    async def test_timeout_is_not_remote_cancellation_and_does_not_retry(self):
        self.client.install_finish.clear();self.session._install_timeout=0.02
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertEqual(self.journal.record['state'],'pending')
        await self.run_action();self.assertEqual([c[0] for c in self.client.calls].count('install'),1)
    async def test_closing_browser_keeps_one_owner_and_prevents_duplicate(self):
        self.client.install_finish.clear()
        observer=asyncio.create_task(self.run_action())
        await asyncio.wait_for(self.client.install_entered.wait(),1)
        observer.cancel()
        with self.assertRaises(asyncio.CancelledError):await observer
        self.assertTrue(self.session.busy)
        self.assertEqual((await self.run_action())['error'],'app_busy')
        self.client.install_finish.set();await self.session._active
        self.assertEqual(self.session.snapshot()['result']['state'],'installed_stopped')
        self.assertEqual([c[0] for c in self.client.calls].count('install'),1)
    async def test_shutdown_during_install_keeps_pending_reconciliation(self):
        self.client.install_finish.clear();task=asyncio.create_task(self.run_action())
        await asyncio.wait_for(self.client.install_entered.wait(),1);self.session.invalidate()
        self.client.install_finish.set()
        self.assertEqual((await task)['error'],'app_reconciliation_required')
        self.assertEqual(self.journal.record['state'],'pending')
        self.assertEqual((await self.run_action())['error'],'app_closed')
    async def test_release_change_after_install_does_not_accept_response(self):
        self.client.on_install=lambda:self.release.__setitem__(0,None)
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertEqual(self.journal.record['state'],'pending')
    async def test_version_change_between_preflight_and_install_stays_stopped(self):
        self.client.on_install=lambda:setattr(self.client,'version','1.2.4')
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertEqual(self.journal.record['state'],'pending')
    async def test_running_after_install_is_not_silently_accepted_or_stopped(self):
        self.client.on_install=lambda:setattr(self.client,'state','started')
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertEqual(self.client.state,'started')
    async def test_outside_uninstall_requires_reconciliation(self):
        await self.run_action();self.client.installed=False
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertEqual([c[0] for c in self.client.calls].count('install'),1)
    async def test_unknown_commands_are_never_dispatched(self):
        for action in ('start','stop','uninstall','update','shell',[],None):
            with self.subTest(action=action):self.assertFalse((await self.session.async_run(action,'admin',confirmed=True))['ok'])
        self.assertEqual(self.client.calls,[])
    async def test_snapshot_is_detached(self):
        await self.run_action('status');snapshot=self.session.snapshot();snapshot['result']['ok']=False
        self.assertTrue(self.session.snapshot()['result']['ok'])

    async def test_admin_revoked_during_final_store_read_prevents_install(self):
        original=self.client.store.addon_info
        calls=0
        async def revoke_after_read(name):
            nonlocal calls
            result=await original(name);calls+=1
            if calls==2:self.hass.user.is_admin=False
            return result
        self.client.store.addon_info=revoke_after_read
        result=await self.run_action()
        self.assertEqual(result['error'],'forbidden')
        self.assertNotIn('install',[c[0] for c in self.client.calls])
        self.assertEqual(self.journal.record['state'],'pending')

    async def test_deactivated_user_during_final_store_read_prevents_install(self):
        original=self.client.store.addon_info
        calls=0
        async def deactivate_after_read(name):
            nonlocal calls
            result=await original(name);calls+=1
            if calls==2:self.hass.user.is_active=False
            return result
        self.client.store.addon_info=deactivate_after_read
        self.assertEqual((await self.run_action())['error'],'forbidden')
        self.assertNotIn('install',[c[0] for c in self.client.calls])

    async def test_release_changes_while_final_user_lookup_is_awaited(self):
        original=self.hass.auth.async_get_user
        calls=0
        async def user_lookup(user):
            nonlocal calls
            result=await original(user);calls+=1
            if calls==2:self.release[0]=None
            return result
        self.hass.auth.async_get_user=user_lookup
        self.assertEqual((await self.run_action())['error'],'app_release_changed')
        self.assertNotIn('install',[c[0] for c in self.client.calls])
        self.assertEqual(self.journal.record['state'],'pending')

    async def test_unload_during_final_user_lookup_prevents_dispatch(self):
        original=self.hass.auth.async_get_user
        calls=0
        async def user_lookup(user):
            nonlocal calls
            result=await original(user);calls+=1
            if calls==2:self.session.invalidate()
            return result
        self.hass.auth.async_get_user=user_lookup
        self.assertEqual((await self.run_action())['error'],'app_closed')
        self.assertNotIn('install',[c[0] for c in self.client.calls])
        self.assertEqual(self.journal.record['state'],'pending')

    async def test_pending_attempt_is_not_cleared_after_permission_restored(self):
        original=self.client.store.addon_info
        calls=0
        async def revoke_after_read(name):
            nonlocal calls
            result=await original(name);calls+=1
            if calls==2:self.hass.user.is_admin=False
            return result
        self.client.store.addon_info=revoke_after_read
        self.assertEqual((await self.run_action())['error'],'forbidden')
        self.hass.user.is_admin=True
        self.assertEqual((await self.run_action())['error'],'app_reconciliation_required')
        self.assertNotIn('install',[c[0] for c in self.client.calls])



class Schema:
    def __init__(self,value):self.schema=value
class Select:
    def __init__(self,config):self.config=config


def flow_class():
    tree=ast.parse((COMP/'slicer_installation_flow.py').read_bytes())
    selected=[n for n in tree.body if isinstance(n,(ast.Assign,ast.ClassDef))]
    env={'vol':SimpleNamespace(Schema=Schema,Required=lambda key,**kwargs:key),
         'selector':SimpleNamespace(SelectSelector=Select,SelectSelectorConfig=lambda **kwargs:kwargs,
                                   SelectSelectorMode=SimpleNamespace(DROPDOWN='dropdown')),
         'get_supervisor_session':app.get_supervisor_session,
         'current_request':REQUEST,'KEY_AUTHENTICATED':'ha_authenticated'}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<native setup flow>','exec'),env)
    return env['SlicerInstallationFlowMixin']


class Flow(flow_class()):
    def __init__(self,hass,entry,session):
        self.hass=hass;self.config_entry=entry;self._supervisor_session=session;self.context={'user_id':'admin'}
        self.external=0;self.legacy=0
    def async_show_menu(self,**kwargs):return {'type':'menu',**kwargs}
    def async_show_form(self,**kwargs):return {'type':'form',**kwargs}
    def async_abort(self,**kwargs):return {'type':'abort',**kwargs}
    def async_show_progress(self,**kwargs):return {'type':'progress',**kwargs}
    def async_show_progress_done(self,**kwargs):return {'type':'progress_done',**kwargs}
    async def async_step_init(self,user_input=None):self.external+=1;return {'type':'form','step_id':'init'}
    async def async_step_installer(self):self.legacy+=1;return {'type':'legacy'}


class FlowTests(SessionFixture):
    # Shared fixture only; the session tests are not duplicated.
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.entry=SimpleNamespace(options={'secret':'private-option'},data={'title':'studio'})
        self.flow=Flow(self.hass,self.entry,self.session)
        token=REQUEST.set({"ha_authenticated":True,"hass_user":self.hass.user})
        self.addCleanup(REQUEST.reset,token)
    async def test_entry_menu_does_not_probe_mounts_or_supervisor(self):
        result=await self.flow.async_step_slicer_installation()
        self.assertEqual(result['menu_options'],['slicer_supervisor','slicer_external','slicer_host_legacy'])
        self.assertEqual(self.client.calls,[]);self.assertEqual(self.flow.legacy,0)
    async def test_external_returns_existing_options_without_saving(self):
        before=copy.deepcopy(self.entry.options)
        result=await self.flow.async_step_slicer_external()
        self.assertEqual(result['step_id'],'init');self.assertEqual(self.entry.options,before)
        self.assertEqual(self.client.calls,[])
    async def test_legacy_is_an_explicit_distinct_choice(self):
        self.assertEqual(await self.flow.async_step_slicer_host_legacy(),{'type':'legacy'})
        self.assertEqual(self.flow.legacy,1);self.assertEqual(self.client.calls,[])
    async def test_unreleased_app_hidden_install_action_and_clear_error(self):
        self.release[0]=None
        result=await self.flow.async_step_slicer_supervisor();await result['progress_task']
        await self.flow.async_step_slicer_supervisor_progress()
        form=await self.flow.async_step_slicer_supervisor_result()
        self.assertEqual(form['errors']['base'],'supervisor_app_release_unavailable')
        self.assertEqual(form['data_schema'].schema['operation'].config['options'],['status','back'])
        self.assertEqual(self.flow.legacy,0)
    async def test_install_confirmation_separate_from_start(self):
        progress=await self.flow.async_step_slicer_supervisor();await progress['progress_task']
        await self.flow.async_step_slicer_supervisor_progress()
        form=await self.flow.async_step_slicer_supervisor({'operation':'install'})
        self.assertEqual(form['step_id'],'slicer_supervisor_confirm')
        self.assertNotIn('install',[c[0] for c in self.client.calls])
        declined=await self.flow.async_step_slicer_supervisor_confirm({'confirm':False})
        self.assertEqual(declined['step_id'],'slicer_supervisor')
        progress=await self.flow.async_step_slicer_supervisor_confirm({'confirm':True})
        await progress['progress_task'];await self.flow.async_step_slicer_supervisor_progress()
        self.assertEqual(self.session.snapshot()['result']['state'],'installed_stopped')
        self.assertEqual(self.entry.options,{'secret':'private-option'})
    async def test_progress_reuses_observer(self):
        first=await self.flow.async_step_slicer_supervisor()
        second=await self.flow.async_step_slicer_supervisor_progress()
        self.assertIs(first['progress_task'],second['progress_task'])
        await first['progress_task']
    async def test_form_never_exposes_backend_options(self):
        progress=await self.flow.async_step_slicer_supervisor();await progress['progress_task']
        form=await self.flow.async_step_slicer_supervisor_result()
        self.assertNotIn('never-export',str(form));self.assertNotIn('private-option',str(form))
    async def test_options_route_is_the_new_menu(self):
        tree=ast.parse((COMP/'config_flow.py').read_bytes())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Ultimate3DStudioOptionsFlow')
        method=next(n for n in cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='async_step_init')
        env={'CONF_INSTALLER_SETUP':'slicer_installer_setup'}
        module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),method],type_ignores=[])
        exec(compile(ast.fix_missing_locations(module),'<options route>','exec'),env)
        result=await env['async_step_init'](self.flow,{'slicer_installer_setup':True})
        self.assertEqual(result['type'],'menu');self.assertEqual(self.flow.legacy,0)

    async def test_authenticated_http_actor_works_with_empty_native_context(self):
        self.flow.context={}
        progress=await self.flow.async_step_slicer_supervisor()
        await progress['progress_task']
        self.assertEqual(self.session.snapshot()['result'],{'ok':True,'state':'not_installed'})
        self.assertEqual(self.hass.auth_calls,['admin'])

    async def test_forged_context_actor_without_http_auth_does_not_authorize(self):
        REQUEST.set(None)
        self.flow.context={'user_id':'admin'}
        progress=await self.flow.async_step_slicer_supervisor();await progress['progress_task']
        self.assertEqual(self.session.snapshot()['result']['error'],'forbidden')
        self.assertEqual(self.client.calls,[])

    async def test_unauthenticated_request_with_user_object_cannot_authorize(self):
        REQUEST.set({'ha_authenticated':False,'hass_user':self.hass.user})
        progress=await self.flow.async_step_slicer_supervisor();await progress['progress_task']
        self.assertEqual(self.session.snapshot()['result']['error'],'forbidden')
        self.assertEqual(self.client.calls,[])

    async def test_confirmation_uses_actual_current_http_actor(self):
        progress=await self.flow.async_step_slicer_supervisor();await progress['progress_task']
        await self.flow.async_step_slicer_supervisor({'operation':'install'})
        REQUEST.set({'ha_authenticated':True,'hass_user':SimpleNamespace(id='other-user')})
        progress=await self.flow.async_step_slicer_supervisor_confirm({'confirm':True})
        await progress['progress_task']
        self.assertEqual(self.session.snapshot()['result']['error'],'forbidden')
        self.assertNotIn('install',[c[0] for c in self.client.calls])
        self.assertEqual(self.journal.saves,[])

    async def test_submitted_user_id_cannot_override_authenticated_actor(self):
        REQUEST.set({'ha_authenticated':True,'hass_user':SimpleNamespace(id='other-user')})
        await self.flow.async_step_slicer_supervisor({'operation':'status','user_id':'admin'})
        await self.flow._supervisor_task
        self.assertEqual(self.session.snapshot()['result']['error'],'forbidden')
        self.assertEqual(self.client.calls,[])



class PackagingTests(unittest.TestCase):
    def test_optional_hassio_does_not_require_supervisor_on_container(self):
        manifest=json.loads((COMP/'manifest.json').read_bytes())
        self.assertIn('hassio',manifest.get('after_dependencies',[]))
        self.assertNotIn('hassio',manifest.get('dependencies',[]))
    def test_all_new_steps_actions_and_errors_translated(self):
        for rel in ('strings.json','translations/de.json','translations/en.json'):
            with self.subTest(file=rel):
                doc=json.loads((COMP/rel).read_text(encoding='utf-8-sig'))
                for step in ('slicer_installation','slicer_supervisor','slicer_supervisor_confirm','slicer_external','slicer_host_legacy'):
                    self.assertIn(step,doc['options']['step'])
                self.assertEqual(set(doc['selector']['supervisor_app_operation']['options']),{'status','install','reconcile','back'})
                for code in app.ERRORS:self.assertIn('supervisor_'+code,doc['options']['error'])
                self.assertIn('supervisor_app_working',doc['options']['progress'])


if __name__=='__main__':unittest.main()
