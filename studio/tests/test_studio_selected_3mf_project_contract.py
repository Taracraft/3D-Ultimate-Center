"""Selected 3MF parts and material metadata survive archive ordering."""
from __future__ import annotations
from io import BytesIO
import hashlib
import importlib.util
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import pytest

COMPONENT=Path(__file__).resolve().parents[1]/"deploy/homeassistant/custom_components/ultimate_3d_studio"
@pytest.fixture
def modules():
    def load(name):
        spec=importlib.util.spec_from_file_location("studio_project_contract_"+name,COMPONENT/(name+".py"))
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    return load("three_mf_inspector"),load("three_mf_scene")

def archive(files):
    result=BytesIO()
    with zipfile.ZipFile(result,"w",zipfile.ZIP_DEFLATED) as output:
        for name,content in files:
            output.writestr(name,content)
    return result.getvalue()

def mesh(object_id="1", triangle=("0","1","2"), vertex="0", duplicate=False, omit=None):
    root=ET.Element("model")
    resources=ET.SubElement(root,"resources")
    for _ in range(2 if duplicate else 1):
        obj=ET.SubElement(resources,"object",{"id":object_id})
        node=ET.SubElement(obj,"mesh")
        vertices=ET.SubElement(node,"vertices")
        first={"x":vertex,"y":"0","z":"0"}
        if omit=="vertex": first.pop("x")
        for point in [first,{"x":"5","y":"0","z":"0"},{"x":"0","y":"5","z":"0"}]:
            ET.SubElement(vertices,"vertex",point)
        triangles=ET.SubElement(node,"triangles")
        attrs=dict(zip(("v1","v2","v3"),triangle))
        if omit=="triangle": attrs.pop("v1")
        ET.SubElement(triangles,"triangle",attrs)
    return ET.tostring(root)

def project(shared_plate=False, geometry=()):
    main='''<model xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"><resources>
<object id="10"><components><component objectid="1" p:path="/3D/Objects/a.model"/></components></object>
<object id="20"><components><component objectid="2" p:path="/3D/Objects/b.model"/></components></object>
</resources><build><item objectid="10" transform="1 0 0 0 1 0 0 0 1 20 0 0"/><item objectid="20" transform="1 0 0 0 1 0 0 0 1 50 0 0"/></build></model>'''
    root=ET.Element("config")
    for object_id,part_id,name,extruder in [("10","1","Body","1"),("20","2","Letters","2")]:
        obj=ET.SubElement(root,"object",{"id":object_id})
        ET.SubElement(obj,"metadata",{"key":"name","value":name})
        ET.SubElement(obj,"metadata",{"key":"extruder","value":extruder})
        part=ET.SubElement(obj,"part",{"id":part_id})
        ET.SubElement(part,"metadata",{"key":"name","value":name+" part"})
        ET.SubElement(part,"metadata",{"key":"extruder","value":extruder})
    for number,ids in ([(1,["10","20"])] if shared_plate else [(1,["10"]),(2,["20"])]):
        plate=ET.SubElement(root,"plate")
        ET.SubElement(plate,"metadata",{"key":"plater_id","value":str(number)})
        for object_id in ids:
            instance=ET.SubElement(plate,"model_instance")
            ET.SubElement(instance,"metadata",{"key":"object_id","value":object_id})
            ET.SubElement(instance,"metadata",{"key":"instance_id","value":"0"})
    settings=[
        ("Metadata/model_settings.config",ET.tostring(root)),
        ("Metadata/project_settings.config",json.dumps({"filament_colour":["#000000FF","#FFFFFF"],"filament_type":["PLA","PLA"],"filament_settings_id":["Black","White"]})),
        ("Metadata/plate_1.json",json.dumps({"plate_index":1,"plate_name":"Bodies"})),
        ("Metadata/plate_2.json",json.dumps({"plate_index":2,"plate_name":"Letters"})),
    ]
    return [("[Content_Types].xml","<Types/>"),("3D/3dmodel.model",main),("3D/Objects/a.model",mesh()),("3D/Objects/b.model",mesh("2")),*geometry],settings

@pytest.mark.parametrize("order",["geometry-first","metadata-first","interleaved"])
def test_geometry_budget_never_hides_plate_material_metadata(modules,monkeypatch,order):
    inspector,_=modules
    monkeypatch.setattr(inspector,"_MAX_METADATA_BYTES",4096)
    geometry,metadata=project(geometry=[("3D/Objects/c.model",b"<model>"+b" "*3000+b"</model>"),("3D/Objects/d.model",b"<model>"+b" "*3000+b"</model>")])
    files=geometry+metadata if order=="geometry-first" else metadata+geometry if order=="metadata-first" else geometry[:5]+metadata[:1]+geometry[5:]+metadata[1:]
    payload=archive(files)
    digest=hashlib.sha256(payload).hexdigest()
    result=inspector.inspect_model("selected.3mf",payload)
    assert [(x["name"],x["color"]) for x in result["filaments"]]==[("Black","#000000"),("White","#FFFFFF")]
    assert result["plate_count"]==2
    assert [(x["object_id"],x["plate_index"],x["extruder"]) for x in result["objects"]]==[("10",0,1),("20",1,2)]
    assert [x["object_count"] for x in result["plates"]]==[1,1]
    assert [x["name"] for x in result["plates"]]==["Bodies","Letters"]
    assert result["used_extruders"]==[1,2]
    assert hashlib.sha256(payload).hexdigest()==digest

@pytest.mark.parametrize("kind",["single-required","aggregate-required"])
def test_metadata_budget_overflow_is_rejected_instead_of_partial_success(modules,monkeypatch,kind):
    inspector,_=modules
    monkeypatch.setattr(inspector,"_MAX_METADATA_BYTES",1024)
    if kind=="single-required":
        files=[("Metadata/project_settings.config",json.dumps({"filament_colour":["#000000"],"padding":" "*1100}))]
    else:
        files=[("Metadata/project_settings.config",json.dumps({"filament_colour":["#000000"],"padding":" "*700})),("Metadata/plate_1.json",json.dumps({"plate_index":1,"padding":" "*700}))]
    with pytest.raises(ValueError):
        inspector.inspect_model("selected.3mf",archive(files))

@pytest.mark.parametrize("plate,object_id,extruder",[(0,"10",1),(1,"20",2)])
def test_selected_plate_scene_keeps_exact_object_part_and_extruder(modules,plate,object_id,extruder):
    _,scene=modules
    geometry,metadata=project()
    payload=archive(geometry+metadata)
    result=scene.extract_scene("selected.3mf",payload,plate)
    assert result["plate_index"]==plate and result["triangle_count"]==1
    assert len(result["instances"])==1
    instance=result["instances"][0]
    assert instance["object_id"]==object_id and instance["extruder"]==extruder
    assert instance["part_id"]==str(extruder)
    assert instance["name"]==("Body part" if plate==0 else "Letters part")

def test_same_plate_preserves_relative_positions_and_separate_material_parts(modules):
    _,scene=modules
    geometry,metadata=project(shared_plate=True)
    result=scene.extract_scene("selected.3mf",archive(geometry+metadata),0)
    left,right=result["instances"]
    assert [left["id"],right["id"]]==["10:1","20:2"]
    assert [left["extruder"],right["extruder"]]==[1,2]
    assert right["positions"][0]-left["positions"][0]==30
    assert left["positions"][3]-left["positions"][0]==5
    assert right["positions"][3]-right["positions"][0]==5

@pytest.mark.parametrize("options",[
    {"object_id":"999"}, {"duplicate":True},
    {"triangle":("-1","1","2")},{"triangle":("3","1","2")},
    {"vertex":"nan"},{"vertex":"inf"},{"vertex":"-inf"},
    {"omit":"vertex"},{"omit":"triangle"},{"vertex":"oops"},
    {"triangle":("1.5","1","2")},
])
def test_invalid_or_ambiguous_selected_mesh_never_becomes_a_different_part(modules,options):
    _,scene=modules
    with pytest.raises(ValueError):
        scene._parse_mesh(mesh(**options),"1")

def test_scene_boundary_rejects_bad_triangle_instead_of_indexerror(modules):
    _,scene=modules
    geometry,metadata=project()
    geometry=[(name,mesh(triangle=("3","1","2")) if name=="3D/Objects/a.model" else data) for name,data in geometry]
    with pytest.raises(ValueError):
        scene.extract_scene("selected.3mf",archive(geometry+metadata),0)

def test_scene_rejects_nonfinite_result_from_finite_transform(modules):
    _,scene=modules
    geometry,metadata=project()
    geometry=[(name,data.replace('transform="1 0 0 0 1 0 0 0 1 20 0 0"','transform="1e308 0 0 0 1 0 0 0 1 0 0 0"') if name=="3D/3dmodel.model" else data) for name,data in geometry]
    with pytest.raises(ValueError):
        scene.extract_scene("selected.3mf",archive(geometry+metadata),0)
