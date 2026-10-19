"""HA installer binding/flow tests with real asyncio and isolated synthetic host I/O."""
from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest

# HA schema/selector rendering is an explicit boundary; no HA runtime installed here.
class Schema:
    def __init__(self, value): self.schema = value
vol = SimpleNamespace(Schema=Schema, Required=lambda key, **kwargs: key, Invalid=ValueError)

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'deploy/homeassistant/custom_components/ultimate_3d_studio'
PKG = 'studio_installer_ha_binding_tests'


def load(name):
    package = sys.modules.setdefault(PKG, type(sys)(PKG))
    package.__path__ = [str(COMPONENT)]
    full = PKG + '.' + name
    spec = importlib.util.spec_from_file_location(full, COMPONENT / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    sys.modules[full] = value
    spec.loader.exec_module(value)
    return value


# Preserve the exact canonical DOMAIN without importing HA's Platform enum.
_const = type(sys)(PKG + '.const')
_const_tree = ast.parse((COMPONENT / 'const.py').read_text(encoding='utf-8-sig'))
_const.DOMAIN = next(ast.literal_eval(n.value) for n in _const_tree.body
    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'DOMAIN' for t in n.targets))
sys.modules[PKG + '.const'] = _const
runtime = load('slicer_installer_runtime')


class FakeHass:
    def __init__(self, path):
        self.data = {}
        self.config = SimpleNamespace(path=lambda *parts: str(path.joinpath(*parts)))
        self.executor_threads = []
        self.forward_fail = False
        self.unload_result = True
        self.config_entries = SimpleNamespace(async_forward_entry_setups=self.forward,
                                              async_unload_platforms=self.unload)
    async def forward(self, *args):
        if self.forward_fail:
            raise RuntimeError('synthetic forward failure')
    async def unload(self, *args):
        return self.unload_result
    def async_create_task(self, coro):
        return asyncio.create_task(coro)
    async def async_add_executor_job(self, func, *args):
        def invoke():
            self.executor_threads.append(threading.get_ident())
            return func(*args)
        return await asyncio.to_thread(invoke)


class FakeController:
    def __init__(self):
        self.calls = []
        self.block_stage = False
        self.entered = threading.Event()
        self.release = threading.Event()
        self.preflight_blocked = False
        self.fail_stage = False
        self.on_call = None
    def run(self, operation, **kwargs):
        self.calls.append((operation, kwargs))
        if self.on_call is not None:
            self.on_call(operation)
        if operation == 'stage' and self.block_stage:
            self.entered.set()
            if not self.release.wait(3):
                raise RuntimeError('synthetic stage not released')
        if operation == 'preflight' and self.preflight_blocked:
            return {'ok':True,'state':'blocked','reasons':['engine_releases_pending']}
        if operation == 'stage' and self.fail_stage:
            return {'ok':False,'error':'response_unavailable','outcome':'unknown'}
        states = {'preflight':'available','initialize':'initialized','stage':'prepared',
                  'retry':'prepared','activate':'ready_paused','resume':'complete',
                  'cancel':'cancel_requested','status':'running','rollback':'rolled_back_absent',
                  'recover':'recovered'}
        return {'ok':True,'state':states[operation]}


class _BindingFixture(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.hass = FakeHass(self.root)
        self.controller = FakeController()
        self.pin = ['pinned-host']
        self.factories = 0
        def factory(path, endpoint):
            self.factories += 1
            return self.controller
        self.session = runtime.InstallerSession(self.hass, self.root/'private-state',
            endpoint_loader=lambda: self.pin[0], controller_factory=factory)
    async def asyncTearDown(self):
        self.controller.release.set()
        await self.session.async_close()


class AsyncBindingTests(_BindingFixture):
    async def test_construction_is_lazy_and_no_install(self):
        self.assertEqual(self.factories,0)
        self.assertEqual(self.controller.calls,[])
        self.assertFalse((self.root/'private-state').exists())

    async def test_host_calls_are_in_executor_not_event_loop(self):
        thread=threading.get_ident()
        self.assertTrue((await self.session.async_run('preflight'))['ok'])
        self.assertTrue(self.hass.executor_threads)
        self.assertNotIn(thread,self.hass.executor_threads)

    async def test_connect_only_pairs_without_host_mutation(self):
        result=await self.session.async_run('connect')
        self.assertEqual(result,{'ok':True,'state':'paired'})
        self.assertEqual(self.controller.calls,[])

    async def test_install_full_sequence_stops_paused(self):
        result=await self.session.async_run('install')
        self.assertEqual(result,{'ok':True,'state':'ready_paused'})
        self.assertEqual([a for a,_ in self.controller.calls],['preflight','initialize','stage','activate'])
        self.assertNotIn('resume',[a for a,_ in self.controller.calls])

    async def test_pending_engines_block_before_first_mutation(self):
        self.controller.preflight_blocked=True
        result=await self.session.async_run('install')
        self.assertEqual(result['state'],'blocked')
        self.assertEqual(result['reasons'],['engine_releases_pending'])
        self.assertEqual([a for a,_ in self.controller.calls],['preflight'])

    async def test_uncertain_stage_never_auto_retries_or_activates(self):
        self.controller.fail_stage=True
        result=await self.session.async_run('install')
        self.assertFalse(result['ok'])
        self.assertEqual(result['outcome'],'unknown')
        self.assertEqual([a for a,_ in self.controller.calls],['preflight','initialize','stage'])

    async def test_browser_cancellation_preserves_operation_and_control_lane(self):
        self.controller.block_stage=True
        outer=asyncio.create_task(self.session.async_run('install'))
        self.assertTrue(await asyncio.to_thread(self.controller.entered.wait,1))
        running=self.session._active
        outer.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await outer
        self.assertTrue(self.session.snapshot()['busy'])
        duplicate=await self.session.async_run('install')
        self.assertEqual(duplicate['error'],'installer_busy')
        result=await asyncio.wait_for(self.session.async_run('cancel'),1)
        self.assertEqual(result['state'],'cancel_requested')
        self.controller.release.set()
        final=await asyncio.wait_for(running,1)
        self.assertEqual(final['state'],'ready_paused')
        self.assertEqual([a for a,_ in self.controller.calls].count('stage'),1)

    async def test_status_remains_available_during_stage(self):
        self.controller.block_stage=True
        outer=asyncio.create_task(self.session.async_run('stage'))
        self.assertTrue(await asyncio.to_thread(self.controller.entered.wait,1))
        self.assertEqual((await asyncio.wait_for(self.session.async_run('status'),1))['state'],'running')
        self.controller.release.set()
        await outer

    async def test_endpoint_change_before_dispatch_is_rejected(self):
        await self.session.async_run('connect')
        self.pin[0]='other-host'
        result=await self.session.async_run('initialize')
        self.assertEqual(result['error'],'endpoint_changed')
        self.assertEqual(self.controller.calls,[])

    async def test_endpoint_change_during_rpc_is_unknown(self):
        self.controller.on_call=lambda op:self.pin.__setitem__(0,'other-host')
        result=await self.session.async_run('initialize')
        self.assertEqual(result['error'],'endpoint_changed')
        self.assertEqual(result['outcome'],'unknown')

    async def test_missing_provisioning_is_not_cached_as_a_success(self):
        self.session._endpoint_loader=lambda: (_ for _ in ()).throw(ValueError('private path/token text'))
        result=await self.session.async_run('connect')
        self.assertFalse(result['ok'])
        self.assertNotIn('private path',str(result))
        self.assertFalse(self.session.snapshot()['paired'])
        self.assertFalse((self.root/'private-state').exists())

    async def test_concurrent_connection_builds_one_controller(self):
        results=await asyncio.gather(*[self.session.async_run('connect') for _ in range(8)])
        self.assertTrue(all(x['ok'] for x in results))
        self.assertEqual(self.factories,1)

    async def test_close_prevents_new_operations(self):
        await self.session.async_close()
        result=await self.session.async_run('install')
        self.assertEqual(result['error'],'installer_closed')
        self.assertEqual(self.controller.calls,[])

    async def test_recovery_commands_are_fixed(self):
        for action,pair in runtime.RECOVERY_ACTIONS.items():
            result=await self.session.async_run(action)
            self.assertTrue(result['ok'])
            self.assertEqual(self.controller.calls[-1],('recover',{'target_action':pair[0],'recovery_action':pair[1]}))

    async def test_unknown_actions_do_not_dispatch(self):
        for value in ('shell','download_url',[],None,1):
            result=await self.session.async_run(value)
            self.assertEqual(result['error'],'unknown_setup_action')
        self.assertEqual(self.controller.calls,[])

    async def test_safe_ui_projection_drops_host_paths_tokens_and_unknown_values(self):
        result=runtime.safe_result({'ok':False,'error':'private_token_123','state':'/root/private',
            'token':'secret','principal':'private','data':{'secret':'keep-private'},
            'reasons':['engine_releases_pending',{'secret':'x'},'private_token_123']})
        self.assertEqual(result,{'ok':False,'state':'unknown','error':'installer_failed','reasons':['engine_releases_pending']})
        self.assertNotIn('secret',str(result))

    async def test_snapshot_has_no_alias_to_internal_result_lists(self):
        self.controller.preflight_blocked=True
        await self.session.async_run('preflight')
        snapshot=self.session.snapshot()
        snapshot['result']['reasons'].append('changed')
        self.assertEqual(self.session.snapshot()['result']['reasons'],['engine_releases_pending'])


class Select:
    def __init__(self, config):self.config=config
    def __call__(self,value):
        if value not in self.config['options']:raise vol.Invalid('invalid choice')
        return value


def flow_mixin():
    source=(COMPONENT/'slicer_installer_flow.py').read_text(encoding='utf-8-sig')
    tree=ast.parse(source)
    selected=[n for n in tree.body if isinstance(n,(ast.Assign,ast.ClassDef))]
    env={'vol':vol,'selector':SimpleNamespace(SelectSelector=Select,
        SelectSelectorConfig=lambda **kwargs:kwargs,SelectSelectorMode=SimpleNamespace(DROPDOWN='dropdown')),
        'ACTIONS':runtime.ACTIONS,'MUTATION_ACTIONS':runtime.MUTATION_ACTIONS,
        'get_installer_session':runtime.get_installer_session}
    exec(compile(ast.Module(body=selected,type_ignores=[]),'<actual installer flow>','exec'),env)
    return env['InstallerOptionsFlowMixin']


Mixin=flow_mixin()


class FakeFlow(Mixin):
    def __init__(self,hass,entry):self.hass=hass;self.config_entry=entry
    def async_show_form(self,**kwargs):return {'type':'form',**kwargs}
    def async_abort(self,**kwargs):return {'type':'abort',**kwargs}
    def async_show_progress(self,**kwargs):return {'type':'progress',**kwargs}
    def async_show_progress_done(self,**kwargs):return {'type':'progress_done',**kwargs}
    async def async_step_init(self,user_input=None):return {'type':'form','step_id':'init'}
    async def async_step_slicer_installation(self,user_input=None):return {'type':'menu','step_id':'slicer_installation'}


class FlowTests(_BindingFixture):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.entry=SimpleNamespace(entry_id='synthetic-entry',data={'preserved':'data'},options={'preserved':'options'})
        self.hass.data={runtime.DOMAIN:{runtime.DATA_INSTALLERS:{self.entry.entry_id:self.session}}}
        self.flow=FakeFlow(self.hass,self.entry)

    async def test_native_progress_reuses_same_observer_task(self):
        first=await self.flow.async_step_installer()
        second=await self.flow.async_step_installer_progress()
        self.assertEqual(first['type'],'progress')
        self.assertIs(first['progress_task'],second['progress_task'])
        await first['progress_task']
        done=await self.flow.async_step_installer_progress()
        self.assertEqual(done,{'type':'progress_done','next_step_id':'installer_action'})

    async def test_missing_runtime_aborts_without_fallback_host(self):
        self.hass.data={}
        result=await self.flow.async_step_installer()
        self.assertEqual(result['type'],'abort')
        self.assertEqual(self.controller.calls,[])

    async def test_install_requires_explicit_confirmation(self):
        await self.session.async_run('connect')
        await self.flow.async_step_installer()
        choice=await self.flow.async_step_installer_action({'operation':'install'})
        self.assertEqual(choice['step_id'],'installer_confirm')
        self.assertEqual(self.controller.calls,[])
        cancelled=await self.flow.async_step_installer_confirm({'confirm':False})
        self.assertEqual(cancelled['step_id'],'installer_action')
        self.assertEqual(self.controller.calls,[])
        progress=await self.flow.async_step_installer_confirm({'confirm':True})
        await progress['progress_task']
        self.assertEqual([x for x,_ in self.controller.calls],['preflight','initialize','stage','activate'])

    async def test_finish_preserves_all_existing_options(self):
        await self.session.async_run('connect')
        await self.flow.async_step_installer()
        result=await self.flow.async_step_installer_action({'operation':'finish'})
        self.assertEqual(result,{'type':'form','step_id':'init'})
        self.assertEqual(self.entry.options,{'preserved':'options'})
        self.assertEqual(self.entry.data,{'preserved':'data'})

    async def test_invalid_operation_is_not_forwarded(self):
        await self.session.async_run('connect')
        await self.flow.async_step_installer()
        result=await self.flow.async_step_installer_action({'operation':'shell'})
        self.assertEqual(result['errors']['base'],'installer_invalid_action')
        self.assertEqual(self.controller.calls,[])

    async def test_advanced_options_routes_before_any_printer_or_account_work(self):
        source=(COMPONENT/'config_flow.py').read_text(encoding='utf-8-sig')
        tree=ast.parse(source)
        klass=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Ultimate3DStudioOptionsFlow')
        method=next(x for x in klass.body if isinstance(x,ast.AsyncFunctionDef) and x.name=='async_step_advanced')
        module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),method],type_ignores=[])
        env={'CONF_INSTALLER_SETUP':'slicer_installer_setup','CONF_CLOUD_REAUTHENTICATE':'cloud_reauthenticate'}
        exec(compile(ast.fix_missing_locations(module),'<actual options init>','exec'),env)
        result=await env['async_step_advanced'](self.flow,{'slicer_installer_setup':True})
        self.assertEqual(result,{'type':'menu','step_id':'slicer_installation'})
        self.assertEqual(self.controller.calls,[])

    async def test_translations_cover_all_native_flow_choices(self):
        schemas=[]
        for filename in ('strings.json','translations/de.json','translations/en.json'):
            value=json.loads((COMPONENT/filename).read_text(encoding='utf-8-sig'))
            self.assertIn('slicer_installer_setup',value['options']['step']['advanced']['data'])
            self.assertIn('installer_working',value['options']['progress'])
            schemas.append(set(value['selector']['installer_operation']['options']))
        self.assertEqual(schemas[0],schemas[1])
        self.assertEqual(schemas[1],schemas[2])


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.hass=FakeHass(Path(self.temp.name))
        self.entry=SimpleNamespace(entry_id='synthetic-entry',title='Studio',data={},options={},
            async_on_unload=lambda cb:None,add_update_listener=lambda cb:lambda:None)
        self.audit_fail=False
        outer=self
        class Log:
            async def async_append(self,**kwargs):
                if outer.audit_fail and kwargs.get('event')=='entry_started':raise RuntimeError('synthetic audit failure')
        class Runtime:
            provider_count=0
            def __init__(self,*args):pass
            async def async_start(self):pass
            async def async_stop(self):pass
        async def noop(*args):pass
        source=(COMPONENT/'__init__.py').read_text(encoding='utf-8-sig')
        tree=ast.parse(source)
        nodes=[n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name in ('async_setup_entry','async_unload_entry')]
        env={'DOMAIN':runtime.DOMAIN,'DATA_RUNTIMES':'runtimes','PLATFORMS':[],
             'Ultimate3DStudioRuntime':Runtime,'install_profile_runtime_v2':lambda hass:None,
             '_async_reload_entry':noop,'async_start_cloud_profile_sync':noop,'async_setup_dashboard':noop,'async_setup_hacs':noop,
             'async_stop_cloud_profile_sync':noop,'get_audit_log':lambda hass:Log(),
             'register_installer_session':runtime.register_installer_session,
             'async_remove_installer_session':runtime.async_remove_installer_session}
        module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*nodes],type_ignores=[])
        exec(compile(ast.fix_missing_locations(module),'<actual lifecycle>','exec'),env)
        self.setup=env['async_setup_entry'];self.unload=env['async_unload_entry']
    async def test_setup_registers_lazy_session_without_files(self):
        self.assertTrue(await self.setup(self.hass,self.entry))
        self.assertIsNotNone(runtime.get_installer_session(self.hass,self.entry))
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])
    async def test_failed_unload_preserves_installer_session(self):
        await self.setup(self.hass,self.entry)
        session=runtime.get_installer_session(self.hass,self.entry)
        self.hass.unload_result=False
        self.assertFalse(await self.unload(self.hass,self.entry))
        self.assertIs(runtime.get_installer_session(self.hass,self.entry),session)
        self.assertFalse(session._closed)
    async def test_successful_unload_closes_session(self):
        await self.setup(self.hass,self.entry)
        session=runtime.get_installer_session(self.hass,self.entry)
        self.assertTrue(await self.unload(self.hass,self.entry))
        self.assertTrue(session._closed)
        self.assertIsNone(runtime.get_installer_session(self.hass,self.entry))
    async def test_setup_failure_cleans_up_installer_session(self):
        self.audit_fail=True
        with self.assertRaises(RuntimeError):await self.setup(self.hass,self.entry)
        self.assertIsNone(runtime.get_installer_session(self.hass,self.entry))


class IntegratedBindingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.hass=FakeHass(self.base)
        self.backend_module=sys.modules[PKG+'.slicer_installer_backend']
        self.setup_module=sys.modules[PKG+'.slicer_installer_setup']
        self.credential=self.base/'credential';self.credential.mkdir(mode=0o700)
        self.store=self.backend_module.InstallerCredentialStore(
            self.credential,expected_host_id='a'*32,server_uid=0)
        self.backend_module._atomic_private_json(self.store.path,
            {'host_id':'a'*32,'principal':'synthetic','token':'T'*64})
        self.calls=[]
        self.fail_stage=False
        owner=self
        class Client:
            def __init__(self,*args,**kwargs):pass
            def request(self,token,request):
                owner.assertEqual(token,'T'*64)
                owner.calls.append(dict(request))
                if request['operation']=='stage' and owner.fail_stage:
                    return {'ok':False,'error':'response_unavailable','outcome':'unknown',
                            'request_id':request['request_id']}
                states={'preflight':'available','initialize':'initialized','stage':'prepared',
                        'activate':'ready_paused','status':'observed'}
                return {'ok':True,'state':states[request['operation']],
                        'request_id':request.get('request_id',request.get('target'))}
        self.backend=self.backend_module.InstallerBackend(self.store,self.base,
            server_uid=0,client_factory=Client)
        self.state=self.base/'state';self.state.mkdir(mode=0o700)
        self.controller=self.setup_module.GuidedInstallerSetup(self.backend,self.state)
        self.session=runtime.InstallerSession(self.hass,self.base/'binding',
            endpoint_loader=lambda:'fixed-endpoint',controller_factory=lambda *args:self.controller)
    async def asyncTearDown(self):
        await self.session.async_close()
    async def test_real_setup_backend_and_async_binding_complete_paused_sequence(self):
        result=await self.session.async_run('install')
        self.assertEqual(result,{'ok':True,'state':'ready_paused'})
        self.assertEqual([r['operation'] for r in self.calls],['preflight','initialize','stage','activate'])
        state=self.controller.public_status()
        self.assertEqual(self.calls[-1]['target'],state['requests']['stage'])
        self.assertEqual(self.calls[-1]['request_id'],state['requests']['activate'])
        self.assertNotIn('T'*64,str(result)+str(state))
    async def test_real_setup_can_observe_initialize_before_activation(self):
        self.assertTrue((await self.session.async_run('initialize'))['ok'])
        target=self.calls[-1]['request_id']
        await self.session.async_run('status')
        self.assertEqual(self.calls[-1]['target'],target)
    async def test_real_setup_unknown_outcome_retains_id_and_does_not_activate(self):
        self.fail_stage=True
        result=await self.session.async_run('install')
        self.assertEqual(result['outcome'],'unknown')
        self.assertEqual([r['operation'] for r in self.calls],['preflight','initialize','stage'])
        restart=self.setup_module.GuidedInstallerSetup(self.backend,self.state)
        self.assertEqual(restart.public_status()['requests']['stage'],self.calls[-1]['request_id'])
    async def test_restart_keeps_exact_setup_identity_without_dispatch_on_constructor(self):
        await self.session.async_run('initialize')
        target=self.calls[-1]['request_id']
        count=len(self.calls)
        fresh=self.setup_module.GuidedInstallerSetup(self.backend,self.state)
        self.assertEqual(len(self.calls),count)
        fresh.run('initialize')
        self.assertEqual(self.calls[-1]['request_id'],target)
    async def test_mutated_saved_result_is_not_forwarded_to_ui(self):
        value=json.loads(self.controller.path.read_bytes())
        value['last_result']={'ok':True,'secret':'must-not-leak'}
        self.controller.path.write_bytes(json.dumps(value).encode())
        result=await self.session.async_run('preflight')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error'],'invalid_setup_state')
        self.assertNotIn('must-not-leak',str(result))
        self.assertEqual(self.calls,[])


if __name__=='__main__':unittest.main()
