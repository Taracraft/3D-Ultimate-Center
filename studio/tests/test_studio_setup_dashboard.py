"""Native HA dashboard registration boundary; no live HA writes."""
import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

COMPONENT=Path(__file__).resolve().parents[1]/'deploy/homeassistant/custom_components/ultimate_3d_studio'

class DashboardTests(unittest.TestCase):
    def setUp(self):
        ns='studio_dashboard_contract'
        pkg=ModuleType(ns);pkg.__path__=[str(COMPONENT)]
        const=ModuleType(ns+'.const');const.DOMAIN='ultimate_3d_studio'
        self.panels={};self.calls=[]
        frontend=ModuleType('homeassistant.components.frontend')
        frontend.async_panel_exists=lambda h,p:p in self.panels
        def register(h,name,**kw):
            self.calls.append(kw);self.panels[kw['frontend_url_path']]=kw
        frontend.async_register_built_in_panel=register
        frontend.async_remove_panel=lambda h,p:self.panels.pop(p,None)
        class YAML:
            def __init__(self,h,path,cfg):self.config=cfg
            async def async_load(self,force):
                return json.loads(Path(self.config['filename']).read_text())
        dashboard=ModuleType('homeassistant.components.lovelace.dashboard');dashboard.LovelaceYAML=YAML
        comps=ModuleType('homeassistant.components');comps.frontend=frontend
        modules={ns:pkg,ns+'.const':const,'homeassistant.components':comps,
                 'homeassistant.components.frontend':frontend,
                 'homeassistant.components.lovelace.dashboard':dashboard}
        self.patcher=patch.dict(sys.modules,modules);self.patcher.start();self.addCleanup(self.patcher.stop)
        spec=importlib.util.spec_from_file_location(ns+'.setup_dashboard',COMPONENT/'setup_dashboard.py')
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.hass=SimpleNamespace(data={'lovelace':SimpleNamespace(dashboards={})})
    def call(self,on=True):return asyncio.run(self.module.async_setup_dashboard(self.hass,on))
    def test_register_and_reload_are_idempotent(self):
        self.assertEqual(self.call(),'registered');self.assertEqual(self.call(),'already_registered')
        self.assertEqual(len(self.calls),1)
        cfg=asyncio.run(self.hass.data['lovelace'].dashboards[self.module.URL_PATH].async_load(False))
        self.assertEqual(cfg['views'][0]['cards'][0]['type'],'custom:ultimate-3d-studio-card')
    def test_existing_user_dashboard_is_preserved(self):
        own=object();self.hass.data['lovelace'].dashboards[self.module.URL_PATH]=own
        self.assertEqual(self.call(),'existing_dashboard_preserved');self.assertFalse(self.calls)
        self.call(False);self.assertIs(self.hass.data['lovelace'].dashboards[self.module.URL_PATH],own)
    def test_unrelated_frontend_panel_is_preserved(self):
        self.panels[self.module.URL_PATH]={'foreign':True}
        self.assertEqual(self.call(),'existing_dashboard_preserved');self.assertFalse(self.calls)
    def test_disable_removes_only_own_panel(self):
        self.call();self.assertEqual(self.call(False),'disabled')
        self.assertNotIn(self.module.URL_PATH,self.hass.data['lovelace'].dashboards)
    def test_disabled_does_not_create_panel(self):
        self.assertEqual(self.call(False),'disabled');self.assertFalse(self.calls)
    def test_not_loaded_is_explicit(self):
        self.hass.data.clear();self.assertEqual(self.call(),'lovelace_not_loaded')

if __name__=='__main__':unittest.main()
