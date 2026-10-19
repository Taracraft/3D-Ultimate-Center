"""Verified HACS adapter: metadata registration only, no auth or downloads."""
import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch, AsyncMock
COMP=Path(__file__).resolve().parents[1]/'deploy/homeassistant/custom_components/ultimate_3d_studio'

class HacsSetupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        pkg=ModuleType('hacs_setup_test');pkg.__path__=[str(COMP)]
        const=ModuleType('hacs_setup_test.const');const.DOMAIN='ultimate_3d_studio';const.VERSION='6.0.5'
        self.modules=patch.dict(sys.modules,{'hacs_setup_test':pkg,'hacs_setup_test.const':const});self.modules.start();self.addCleanup(self.modules.stop)
        spec=importlib.util.spec_from_file_location('hacs_setup_test.setup_hacs',COMP/'setup_hacs.py')
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.repo=NS(data=NS(domain=const.DOMAIN,installed=False,installed_version=None,new=True),content=NS(path=NS(local=str(COMP))))
        self.stored=None
        async def register(**kwargs):
            self.assertEqual(kwargs,{'repository_full_name':self.module.REPOSITORY,'category':'integration'})
            self.stored=self.repo
        self.hacs=NS(integration=NS(version='2.0.5'),system=NS(disabled=False),stage='running',
            repositories=NS(get_by_full_name=lambda name:self.stored),async_register_repository=AsyncMock(side_effect=register),data=NS(async_write=AsyncMock()))
        async def execute(fn,*args):return fn(*args)
        self.hass=NS(data={'hacs':self.hacs},async_add_executor_job=execute)
    async def test_registers_and_adopts_already_loaded_own_integration_without_download(self):
        self.assertEqual(await self.module.async_register_studio_repository(self.hass),'registered')
        self.hacs.async_register_repository.assert_awaited_once();self.hacs.data.async_write.assert_awaited_once()
        self.assertTrue(self.repo.data.installed);self.assertEqual(self.repo.data.installed_version,'6.0.5')
    async def test_existing_installed_repository_keeps_version(self):
        self.stored=self.repo;self.repo.data.installed=True;self.repo.data.installed_version='existing'
        self.assertEqual(await self.module.async_register_studio_repository(self.hass),'registered')
        self.hacs.async_register_repository.assert_not_awaited();self.assertEqual(self.repo.data.installed_version,'existing')
    async def test_no_hacs_waits_for_personal_login(self):
        self.hass.data={};self.assertEqual(await self.module.async_register_studio_repository(self.hass),'awaiting_hacs_login')
    async def test_waits_for_running_hacs_and_does_not_change_disabled_instance(self):
        for stage,disabled in [('startup',False),('running',True)]:
            self.hacs.stage=stage;self.hacs.system.disabled=disabled
            self.assertEqual(await self.module.async_register_studio_repository(self.hass),'awaiting_hacs_ready')
        self.hacs.async_register_repository.assert_not_awaited()
    async def test_unsupported_version_is_not_called(self):
        self.hacs.integration.version='9.0.0'
        self.assertEqual(await self.module.async_register_studio_repository(self.hass),'unsupported_hacs_version')
        self.hacs.async_register_repository.assert_not_awaited()
    async def test_different_domain_or_local_path_not_adopted(self):
        for domain,path in [('other',str(COMP)),('ultimate_3d_studio','/unrelated')]:
            self.stored=self.repo;self.repo.data.domain=domain;self.repo.content.path.local=path
            self.assertEqual(await self.module.async_register_studio_repository(self.hass),'repository_path_mismatch')
        self.assertFalse(self.repo.data.installed);self.hacs.data.async_write.assert_not_awaited()
    async def test_registration_error_is_sanitized(self):
        self.hacs.async_register_repository.side_effect=RuntimeError('secret-not-for-ui')
        self.assertEqual(await self.module.async_register_studio_repository(self.hass),'repository_registration_failed')
    async def test_cancellation_is_propagated(self):
        self.hacs.async_register_repository.side_effect=asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):await self.module.async_register_studio_repository(self.hass)
    async def test_no_silent_success_when_hacs_validation_does_not_register(self):
        self.hacs.async_register_repository.side_effect=None
        self.assertEqual(await self.module.async_register_studio_repository(self.hass),'repository_not_registered')

    async def test_login_stage_event_registers_once_and_unload_removes_listeners(self):
        listeners={};removed=[];cleanup=[];tasks=[]
        core=ModuleType('homeassistant.core');core.callback=lambda f:f
        dispatch=ModuleType('homeassistant.helpers.dispatcher')
        def subscribe(hass,signal,fn):
            listeners[signal]=fn
            return lambda:removed.append(signal)
        dispatch.async_dispatcher_connect=subscribe
        def schedule(coro):
            task=asyncio.create_task(coro);tasks.append(task);return task
        self.hass.async_create_task=schedule
        entry=NS(async_on_unload=cleanup.append)
        self.hacs.stage='startup'
        with patch.dict(sys.modules,{'homeassistant':ModuleType('homeassistant'),
                'homeassistant.core':core,'homeassistant.helpers':ModuleType('homeassistant.helpers'),
                'homeassistant.helpers.dispatcher':dispatch}):
            await self.module.async_setup_hacs(self.hass,entry,True)
            await asyncio.gather(*tasks)
            self.assertEqual(self.hass.data['ultimate_3d_studio']['hacs_setup_status'],'awaiting_hacs_ready')
            self.hacs.stage='running'
            listeners['hacs_dispatch_stage']({'stage':'running'})
            listeners['hacs_dispatch_status']({})
            await asyncio.gather(*tasks)
            self.hacs.async_register_repository.assert_awaited_once()
            count=len(tasks);listeners['hacs_dispatch_status']({});self.assertEqual(len(tasks),count)
            for fn in cleanup:fn()
            self.assertEqual(set(removed),set(listeners))

if __name__=='__main__':unittest.main()
