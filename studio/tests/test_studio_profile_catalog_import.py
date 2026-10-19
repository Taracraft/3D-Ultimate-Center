"""Import the complete profile graph in a fresh process; never starts HA or jobs."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

COMPONENT = Path(__file__).resolve().parents[1] / 'deploy/homeassistant/custom_components/ultimate_3d_studio'

PROBE = r'''
import importlib,json,sys,types
from copy import deepcopy
from pathlib import Path
root=Path(sys.argv[1]);case=sys.argv[2]
for name in ('homeassistant','homeassistant.core','homeassistant.helpers','homeassistant.helpers.storage'):
    sys.modules[name]=types.ModuleType(name)
sys.modules['homeassistant.core'].HomeAssistant=object
sys.modules['homeassistant.helpers.storage'].Store=object
package=types.ModuleType('profile_catalog_probe');package.__path__=[str(root)]
sys.modules[package.__name__]=package
const=types.ModuleType(package.__name__+'.const');const.DOMAIN='ultimate_3d_studio'
sys.modules[const.__name__]=const
def load(name):return importlib.import_module(package.__name__+'.'+name)
if case=='runtime':
    runtime=load('profile_runtime_v2')
    counts={model:sum(p['kind']=='filament' and p['payload'].get('printer_model')==model for p in runtime.STATIC_PROFILES) for model in ('A1','H2S','X1C')}
    print(json.dumps({'counts':counts,'profiles':len(runtime.STATIC_PROFILES),'unique_ids':len(runtime.STATIC_PROFILE_IDS)}))
else:
    enrichment=load('profile_catalog_enrichment')
    x1c=load('x1c_profiles').X1C_PROFILES
    h2s=load('h2s_profiles').H2S_PROFILES
    if case=='native':
        raw=(*h2s,*x1c);actual=enrichment.enrich_static_profiles(raw)
        print(json.dumps({'unchanged':raw==actual,'filaments':sum(p['kind']=='filament' for p in actual)}))
    elif case=='references':
        model=load('printer_model_contract');authority=model.x1c_defaults()
        before=deepcopy(authority);checked=0;chambers=0;ranges=0
        for row in x1c:
            if row['kind']!='filament':continue
            payload=row['payload'];original=authority['filaments'][payload['native_profile_name']]['settings']
            chamber=original.get('chamber_temperatures',['0'])[:1]
            high=original.get('nozzle_temperature_range_high',[])[:1]
            if any(float(v)!=0 for v in chamber):
                assert payload['manufacturer_chamber_temperatures']==chamber
                assert payload['chamber_temperatures']==['0'];chambers+=1
            if any(float(v)>300 for v in high):
                assert payload['manufacturer_nozzle_temperature_range_high']==high
                assert max(map(float,payload['nozzle_temperature_range_high']))==300;ranges+=1
            checked+=1
        print(json.dumps({'authority_unchanged':authority==before,'checked':checked,'chambers':chambers,'ranges':ranges}))
    else:
        fil=deepcopy(next(p for p in x1c if p['kind']=='filament' and (case!='ams' or not p['payload']['ams_compatible'])))
        payload=fil['payload']
        if case=='wrong_basis':
            payload['inherits']=payload['native_profile_name']=next(p['payload']['native_profile_name'] for p in h2s if p['kind']=='filament')
        elif case=='material':payload['material']='invented-material'
        elif case=='ams':payload['ams_compatible']=True
        elif case=='nozzle':payload.update(nozzle_temperature=['320'],nozzle_temperature_initial_layer=['320'],nozzle_temperature_range_low=['200'],nozzle_temperature_range_high=['350'])
        elif case=='bed':payload.update(hot_plate_temp=['111'],hot_plate_temp_initial_layer=['111'])
        elif case=='chamber':payload['chamber_temperatures']=['1']
        else:raise AssertionError(case)
        try:enrichment.enrich_static_profiles([fil])
        except ValueError as error:print(json.dumps({'rejected':True,'error':str(error)}))
        else:print(json.dumps({'rejected':False}))
'''


def catalog_probe(source_root, case):
    result = subprocess.run([sys.executable, '-B', '-c', PROBE, str(source_root), case],
                            capture_output=True, text=True, timeout=30, check=False)
    if result.returncode:
        raise AssertionError('Complete profile graph failed to import:\n' + result.stderr[:2200])
    return json.loads(result.stdout)


class ProfileCatalogImportTests(unittest.TestCase):
    def test_complete_runtime_import_builds_all_models(self):
        result=catalog_probe(COMPONENT,'runtime')
        self.assertEqual(result['counts']['X1C'],183)
        self.assertEqual(result['counts']['H2S'],37)
        self.assertGreater(result['counts']['A1'],0)
        self.assertEqual(result['profiles'],result['unique_ids'])

    def test_native_catalog_preserves_both_model_payloads(self):
        result=catalog_probe(COMPONENT,'native')
        self.assertTrue(result['unchanged'])
        self.assertEqual(result['filaments'],220)

    def test_x1c_rejects_an_h2s_native_basis(self):
        result=catalog_probe(COMPONENT,'wrong_basis')
        self.assertTrue(result['rejected'])
        self.assertIn('invalid native X1C basis',result['error'])

    def test_x1c_safe_factory_overrides_keep_original_manufacturer_references(self):
        result=catalog_probe(COMPONENT,'references')
        self.assertTrue(result['authority_unchanged'])
        self.assertEqual(result['checked'],183)
        self.assertGreater(result['chambers'],0)
        self.assertGreater(result['ranges'],0)

    def test_native_material_and_ams_authority_cannot_be_promoted(self):
        for case,reason in [('material','native X1C material family mismatch'),('ams','unverified X1C AMS family')]:
            with self.subTest(case=case):
                result=catalog_probe(COMPONENT,case)
                self.assertTrue(result['rejected'])
                self.assertIn(reason,result['error'])

    def test_x1c_hardware_limits_and_absent_chamber_heater_remain_enforced(self):
        for case in ('nozzle','bed','chamber'):
            with self.subTest(case=case):
                result=catalog_probe(COMPONENT,case)
                self.assertTrue(result['rejected'])
                self.assertNotIn('invalid native H2S basis',result['error'])
                self.assertIn('local.filament.x1c_',result['error'])


if __name__=='__main__':unittest.main()
