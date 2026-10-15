"""H2S model, native family, plate, AMS and machine-section regressions."""
from copy import deepcopy
import importlib
from pathlib import Path
import sys
import types
import pytest

C = Path(__file__).resolve().parents[1] / 'deploy/homeassistant/custom_components/ultimate_3d_studio'
P = 'studio_h2s_contract_tests'
package = types.ModuleType(P); package.__path__ = [str(C)]; sys.modules[P] = package
H = importlib.import_module(P+'.h2s_profiles')
N = importlib.import_module(P+'.slicer_nozzle_profiles')
B = importlib.import_module(P+'.build_plate_contract')
K = importlib.import_module(P+'.slicer_compatibility_contract')
G = importlib.import_module(P+'.gcode_preset_contract')
E = importlib.import_module(P+'.slicer_execution_contract')
PROFILES = list(H.H2S_PROFILES)+list(G.GCODE_DEFAULT_PROFILES)
FILAMENTS = [p for p in PROFILES if p['kind']=='filament']

def resolve(filament, diameter=.4, surface='textured_pei', source='external_spool', size=None):
    profiles = deepcopy(PROFILES)
    fil = deepcopy(filament); profiles = [p for p in profiles if p['id'] != fil['id']]+[fil]
    printer = next(p for p in profiles if p['id']=='local.printer.h2s')
    if size:
        next(p for p in profiles if p['id']=='local.build_plate.h2s_'+surface)['payload'].update(width_mm=size[0],depth_mm=size[1])
    catalog = {'profiles':profiles, 'selection':{'printer_profile_id':printer['id'],
        'nozzle_profile_id':'local.nozzle.h2s_'+str(diameter).replace('.','_'),
        'build_plate_profile_id':'local.build_plate.h2s_'+surface, 'filament_profile_ids':[fil['id']]}}
    nozzle = N.resolve_nozzle_contract(catalog, {'model':'H2S'})
    plan = {'source':'authoritative_'+('ams' if source=='ams' else 'external_spool')+'_runtime',
            'filaments':[{'name':fil['name'], 'material':fil['payload']['material'], 'extruder':1}]}
    return K.validate_slicer_compatibility(catalog, nozzle, plan, B.selected_build_plate_options(catalog), printer)

@pytest.mark.parametrize('fil', FILAMENTS, ids=lambda f:f['name'])
@pytest.mark.parametrize('diameter', [.2,.4,.6,.8])
@pytest.mark.parametrize('surface', ['textured_pei','smooth_pei'])
@pytest.mark.parametrize('source', ['external_spool','ams'])
def test_every_native_filament_nozzle_plate_and_material_source(fil, diameter, surface, source):
    allowed = diameter in fil['payload']['compatible_nozzle_diameters_mm'] and (source!='ams' or fil['payload']['ams_compatible'])
    if not allowed:
        with pytest.raises(ValueError): resolve(fil,diameter,surface,source)
    else:
        plan, report = resolve(fil,diameter,surface,source)
        assert report['status']=='compatible' and report['limits']['max_chamber_temperature_c']==65
        assert report['filaments'][0]['selected_profile_sha256']==E.digest(plan['filaments'][0]['selected_profile'])

@pytest.mark.parametrize('size', [(256,256),(300,300),(341,320),(340,321)])
def test_unsupported_physical_plate_is_rejected(size):
    fil=next(f for f in FILAMENTS if f['name']=='Generic PLA @BBL H2S')
    with pytest.raises(ValueError): resolve(fil,size=size)

@pytest.mark.parametrize('key,value',[('nozzle_temperature',['351']),('textured_plate_temp',['121']),('chamber_temperatures',['66'])])
def test_selected_heater_limits_cannot_exceed_hardware(key,value):
    fil=deepcopy(next(f for f in FILAMENTS if f['name']=='Generic PLA @BBL H2S'))
    fil['payload'][key]=value
    with pytest.raises(ValueError): resolve(fil)

def test_machine_and_sound_defaults_are_model_specific():
    catalog={'profiles':PROFILES,'selection':{}}
    a1=G.resolve_gcode_presets(catalog,'A1'); h2s=G.resolve_gcode_presets(catalog,'H2S')
    assert a1['printer_model']=='A1' and h2s['printer_model']=='H2S'
    assert len(h2s['selected_profiles'])==4
    assert 'G150' in h2s['settings']['machine_start_gcode']
    catalog['selection']['gcode_preset_ids']={'gcode_1':'builtin.a1.gcode_1'}
    with pytest.raises(ValueError): G.resolve_gcode_presets(catalog,'H2S')

def test_unknown_models_never_inherit_large_printer_authority():
    authority=importlib.import_module(P+'.printer_model_contract')
    assert authority.hardware_limits('H2D') is None
    assert authority.hardware_limits('A1 H2S') is None


def test_engineering_filament_cannot_be_mapped_to_a_pla_channel():
    mapping=importlib.import_module(P+'.filament_profile_mapping')
    fil=next(f for f in FILAMENTS if f['name']=='Generic PPS @BBL H2S 0.4 nozzle')
    assert mapping._compatible(fil, {'material':'PLA'}) is False
    assert mapping._compatible(fil, {'material':'PPS'}) is True


def test_h2s_firmware_temperature_is_bound_to_the_pending_material():
    analysis=importlib.import_module(P+'.gcode_analysis')
    data=b'T0\nM620 S1A\nM620.10 A0 T240 P225\nM620.10 A1 T240 P229\nM620.15 C229\nT1\nM104 T0 S219 N0\n'
    commands=analysis.extract_heater_commands(data,printer_model='H2S')
    assert all(c['channel']==2 for c in commands if c['temperature_c']==229)
    assert not any(c['temperature_c']==225 for c in commands)
    assert any(c['channel']==2 and c['temperature_c']==219 for c in commands)
    assert not any(c['command'].startswith('M620') for c in analysis.extract_heater_commands(data))


def test_user_flag_cannot_promote_an_unverified_ams_family():
    fil=deepcopy(next(f for f in FILAMENTS if f['name']=='Generic PPS @BBL H2S 0.4 nozzle'))
    fil['payload']['ams_compatible']=True
    with pytest.raises(ValueError): resolve(fil,source='ams')


def test_static_catalog_import_validates_native_h2s_without_a1_metadata():
    enrichment=importlib.import_module(P+'.profile_catalog_enrichment')
    actual=enrichment.enrich_static_profiles(H.H2S_PROFILES)
    assert len([p for p in actual if p['kind']=='filament'])==37
    assert all(p['payload']['printer_model']=='H2S' for p in actual if p['kind']=='filament')
    bad=deepcopy(list(H.H2S_PROFILES));fil=next(p for p in bad if p['kind']=='filament');fil['payload']['inherits']='Generic PLA @BBL A1'
    with pytest.raises(ValueError): enrichment.enrich_static_profiles(bad)
