"""Selected 3MF build instances and recursive parts retain geometry and identity."""
from __future__ import annotations
from io import BytesIO
import hashlib
import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import pytest

COMPONENT=Path(__file__).resolve().parents[1]/"deploy/homeassistant/custom_components/ultimate_3d_studio"
@pytest.fixture
def scene():
    spec=importlib.util.spec_from_file_location("studio_instance_contract_scene",COMPONENT/"three_mf_scene.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

CORE="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
PROD="http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
IDENTITY="1 0 0 0 1 0 0 0 1 0 0 0"
def node(name,**attributes):
    return ET.Element("{"+CORE+"}"+name,{k:str(v) for k,v in attributes.items()})
def add(parent,name,**attributes):
    child=node(name,**attributes);parent.append(child);return child
def mesh_object(resources,object_id):
    obj=add(resources,"object",id=object_id)
    mesh=add(obj,"mesh");vertices=add(mesh,"vertices")
    for x,y,z in [(0,0,0),(5,0,0),(0,5,0)]:
        add(vertices,"vertex",x=x,y=y,z=z)
    add(add(mesh,"triangles"),"triangle",v1=0,v2=1,v3=2)
    return obj
def metadata(parent,key,value):
    ET.SubElement(parent,"metadata",{"key":key,"value":str(value)})
def archive(files):
    out=BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for name,data in files: z.writestr(name,data)
    return out.getvalue()
def project(plates=None,nested=None,repeat=True,wrapper_metadata=False,direct=False):
    main=node("model");resources=add(main,"resources")
    if direct: mesh_object(resources,"10")
    else:
        obj=add(resources,"object",id="10");parts=add(obj,"components")
        component=add(parts,"component",objectid="11" if nested else "1")
        if not nested: component.set("{"+PROD+"}path","/3D/Objects/a.model")
        else:
            component.set("transform","0 1 0 -1 0 0 0 0 1 0 0 0")
            middle=add(resources,"object",id="11")
            leaf=add(add(middle,"components"),"component",objectid="1",transform="1 0 0 0 1 0 0 0 1 5 0 0")
            if nested=="external": leaf.set("{"+PROD+"}path","/3D/Objects/a.model")
            else: mesh_object(resources,"1")
    obj=add(resources,"object",id="20")
    c=add(add(obj,"components"),"component",objectid="2")
    c.set("{"+PROD+"}path","/3D/Objects/b.model")
    build=add(main,"build")
    # Interleaving proves instance indices are per object, not global build indices.
    transform="2 0 0 0 3 0 0 0 1 20 0 0" if nested else "1 0 0 0 1 0 0 0 1 20 0 0"
    add(build,"item",objectid="10",transform=transform)
    add(build,"item",objectid="20",transform="1 0 0 0 1 0 0 0 1 100 0 0")
    if repeat: add(build,"item",objectid="10",transform="1 0 0 0 1 0 0 0 1 50 0 0")
    settings=ET.Element("config")
    for object_id,part_id,extruder,name in [("10","11" if wrapper_metadata else ("10" if direct else "1"),2,"Body"),("20","2",1,"Anchor")]:
        obj=ET.SubElement(settings,"object",{"id":object_id})
        metadata(obj,"name",name);metadata(obj,"extruder",1)
        part=ET.SubElement(obj,"part",{"id":part_id})
        metadata(part,"name",name+" part");metadata(part,"extruder",extruder)
    if plates is None:
        plates=[[( "10","0"),("10","1"),("20","0")]] if repeat else [[("10","0"),("20","0")]]
    for number,instances in enumerate(plates,1):
        plate=ET.SubElement(settings,"plate");metadata(plate,"plater_id",number)
        for object_id,instance_id in instances:
            inst=ET.SubElement(plate,"model_instance");metadata(inst,"object_id",object_id)
            if instance_id is not None: metadata(inst,"instance_id",instance_id)
    a=node("model");mesh_object(add(a,"resources"),"1")
    b=node("model");mesh_object(add(b,"resources"),"2")
    return [("3D/3dmodel.model",ET.tostring(main)),("3D/Objects/a.model",ET.tostring(a)),("3D/Objects/b.model",ET.tostring(b)),("Metadata/model_settings.config",ET.tostring(settings))]

def edit(files,path,callback):
    result=[]
    for name,data in files:
        if name==path:
            root=ET.fromstring(data);callback(root);data=ET.tostring(root)
        result.append((name,data))
    return result
def find(root,path):
    return root.find("/".join("{"+CORE+"}"+item for item in path.split("/")))
def all_find(root,path):
    return root.findall("/".join("{"+CORE+"}"+item for item in path.split("/")))

def test_repeated_object_has_distinct_ids_and_thirty_mm_gap(scene):
    data=archive(project());before=hashlib.sha256(data).hexdigest()
    result=scene.extract_scene("selected.3mf",data,0);a,b,anchor=result["instances"]
    assert b["positions"][0]-a["positions"][0]==30
    assert anchor["positions"][0]-a["positions"][0]==80
    assert len({x["id"] for x in result["instances"]})==3
    assert [a["instance_id"],b["instance_id"],anchor["instance_id"]]==[0,1,0]
    assert [a["extruder"],b["extruder"],anchor["extruder"]]==[2,2,1]
    assert a["name"]==b["name"]=="Body part"
    assert result["triangle_count"]==3 and hashlib.sha256(data).hexdigest()==before

@pytest.mark.parametrize("plate,gap",[(0,80),(1,50)])
def test_same_object_instances_on_different_plates_use_exact_build_item(scene,plate,gap):
    data=archive(project(plates=[[("10","0"),("20","0")],[("10","1"),("20","0")]]))
    result=scene.extract_scene("selected.3mf",data,plate);obj,anchor=result["instances"]
    assert anchor["positions"][0]-obj["positions"][0]==gap
    assert obj["instance_id"]==plate and obj["extruder"]==2
    assert result["plate_index"]==plate

@pytest.mark.parametrize("nested",["same","external"])
@pytest.mark.parametrize("wrapper_metadata",[False,True])
def test_nested_components_compose_rotation_scale_and_translation(scene,nested,wrapper_metadata):
    result=scene.extract_scene("selected.3mf",archive(project(nested=nested,repeat=False,wrapper_metadata=wrapper_metadata)),0)
    obj,anchor=result["instances"];p=obj["positions"]
    assert [p[i+3]-p[i] for i in range(3)]==[0,15,0]
    assert [p[i+6]-p[i] for i in range(3)]==[-10,0,0]
    assert anchor["positions"][0]-p[0]==80
    assert anchor["positions"][1]-p[1]==-15
    assert obj["extruder"]==2 and obj["name"]=="Body part"
    assert obj["part_id"]==("11" if wrapper_metadata else "1")

def test_direct_selected_mesh_is_rendered(scene):
    result=scene.extract_scene("selected.3mf",archive(project(repeat=False,direct=True)),0)
    obj,anchor=result["instances"]
    assert obj["part_id"]=="10" and obj["triangle_count"]==1
    assert anchor["positions"][0]-obj["positions"][0]==80

@pytest.mark.parametrize("instance_id",["-1","2","1.5","oops",""])
def test_invalid_instance_index_is_rejected(scene,instance_id):
    with pytest.raises(ValueError):
        scene.extract_scene("selected.3mf",archive(project(plates=[[("10",instance_id)]])),0)

def test_missing_instance_id_is_accepted_only_for_single_build_instance(scene):
    result=scene.extract_scene("selected.3mf",archive(project(plates=[[("10",None)]],repeat=False)),0)
    assert len(result["instances"])==1
    with pytest.raises(ValueError):
        scene.extract_scene("selected.3mf",archive(project(plates=[[("10",None)]])),0)

def test_duplicate_instance_selection_is_rejected(scene):
    with pytest.raises(ValueError):
        scene.extract_scene("selected.3mf",archive(project(plates=[[("10","0"),("10","0")]])),0)

def test_missing_selected_build_item_is_rejected(scene):
    files=edit(project(repeat=False),"3D/3dmodel.model",lambda r:find(r,"build").remove(all_find(r,"build/item")[0]))
    with pytest.raises(ValueError):scene.extract_scene("selected.3mf",archive(files),0)

@pytest.mark.parametrize("kind",["missing-object","duplicate-object","cycle","bad-path","duplicate-archive-model","empty-object"])
def test_invalid_component_graph_is_rejected(scene,kind):
    files=project(repeat=False)
    def mutate(root):
        res=find(root,"resources");obj=list(res)[0];component=find(obj,"components/component")
        if kind=="missing-object": component.set("objectid","999")
        elif kind=="duplicate-object":res.append(ET.fromstring(ET.tostring(obj)))
        elif kind=="cycle":component.attrib.pop("{"+PROD+"}path");component.set("objectid","10")
        elif kind=="bad-path":component.set("{"+PROD+"}path","/3D/../outside.model")
        elif kind=="empty-object":obj.remove(find(obj,"components"))
    if kind=="duplicate-archive-model": files.append(files[1])
    else:files=edit(files,"3D/3dmodel.model",mutate)
    with pytest.raises(ValueError):scene.extract_scene("selected.3mf",archive(files),0)

def test_repeated_component_reference_preserves_two_parts_with_distinct_ids(scene):
    files=project(repeat=False)
    def mutate(root):
        parts=find(list(find(root,"resources"))[0],"components")
        second=ET.fromstring(ET.tostring(list(parts)[0]));second.set("transform","1 0 0 0 1 0 0 0 1 12 0 0")
        parts.append(second)
    files=edit(files,"3D/3dmodel.model",mutate)
    result=scene.extract_scene("selected.3mf",archive(files),0);a,b,anchor=result["instances"]
    assert b["positions"][0]-a["positions"][0]==12
    assert a["id"]!=b["id"] and a["extruder"]==b["extruder"]==2

@pytest.mark.parametrize("nested",["same","external"])
def test_nested_settings_matrix_does_not_double_authoritative_component_transform(scene,nested):
    files=project(nested=nested,repeat=False)
    def mutate(root):
        part=root.find("object/part")
        metadata(part,"matrix","1 0 0 0 1 0 0 0 1 5 0 0")
    files=edit(files,"Metadata/model_settings.config",mutate)
    result=scene.extract_scene("selected.3mf",archive(files),0)
    obj,anchor=result["instances"]
    assert anchor["positions"][0]-obj["positions"][0]==80
    assert anchor["positions"][1]-obj["positions"][1]==-15

@pytest.mark.parametrize("depth,allowed",[(2,False),(3,True)])
def test_recursive_graph_depth_is_bounded(scene,monkeypatch,depth,allowed):
    monkeypatch.setattr(scene,"_MAX_GRAPH_DEPTH",depth)
    data=archive(project(nested="same",repeat=False))
    if allowed:
        assert len(scene.extract_scene("selected.3mf",data,0)["instances"])==2
    else:
        with pytest.raises(ValueError):scene.extract_scene("selected.3mf",data,0)

def test_selected_instance_expansion_is_bounded(scene,monkeypatch):
    monkeypatch.setattr(scene,"_MAX_PARTS",2)
    with pytest.raises(ValueError):scene.extract_scene("selected.3mf",archive(project()),0)

def test_scene_identity_is_stable_between_plate_selections(scene):
    data=archive(project(plates=[[("10","0"),("20","0")],[("10","1"),("20","0")]]))
    left=scene.extract_scene("selected.3mf",data,0)["instances"]
    right=scene.extract_scene("selected.3mf",data,1)["instances"]
    assert left[0]["id"]!=right[0]["id"]
    assert left[1]["id"]==right[1]["id"]=="20:2"
