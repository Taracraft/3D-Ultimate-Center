"""Synthetic Git handoff regressions; no GitHub, engines or live services."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest
SPEC = importlib.util.spec_from_file_location("delivery_contract", Path(__file__).resolve().parents[1] / "tools/studio_delivery_contract.py")
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)

@pytest.fixture
def delivery(tmp_path):
    path = tmp_path / "studio/core/example.py"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic input\n")
    row = {"path": "studio/core/example.py", "bytes": path.stat().st_size,
           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {"schema": 1, "reviewed_for_git_delivery": True,
                "production_approved": False, "protected_component_tree": contract.PROTECTED_TREE,
                "review_evidence": {n: {"verified": True, "sha256": "1" * 64} for n in contract.REVIEW_NAMES},
                "files": [row]}
    tracked = {row["path"], contract.MANIFEST}
    return tmp_path, manifest, tracked

def test_exact_reviewed_delivery_passes_without_production_approval(delivery):
    root, m, tracked = delivery
    assert contract.verify(root,m,tracked,contract.PROTECTED_TREE)["production_approved"] is False

@pytest.mark.parametrize("field,value", [("reviewed_for_git_delivery",False),("production_approved",True),
                                       ("schema",True),("protected_component_tree","2"*40)])
def test_missing_or_incompatible_approval_is_denied(delivery,field,value):
    root,m,tracked=delivery
    m[field]=value
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)

def test_drift_after_review_fails(delivery):
    root,m,tracked=delivery
    (root/m["files"][0]["path"]).write_bytes(b"modified input\n")
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)

@pytest.mark.parametrize("change",["extra","missing"])
def test_git_tracked_set_must_equal_manifest(delivery,change):
    root,m,tracked=delivery
    if change=="extra": tracked.add("studio/unreviewed.py")
    else: tracked.remove(m["files"][0]["path"])
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)

@pytest.mark.parametrize("name",["../outside","/absolute","studio//core/a","studio/./core/a",
                                "studio\\core\\a","C:/absolute"])
def test_unsafe_manifest_paths_fail_before_read(delivery,name):
    root,m,tracked=delivery
    m["files"][0]["path"]=name
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)

@pytest.mark.parametrize("name",["studio/LIVE_WORKLOG.md","studio/docs/private.md",
                                "studio/backups/original.py","studio/secrets.yaml",
                                "studio/deploy/homeassistant/host/service",
                                "studio/tests/large_model.stl","studio/a.pem"])
def test_private_material_is_not_allowed_in_reviewed_manifest(delivery,name):
    root,m,tracked=delivery
    m["files"][0]["path"]=name
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)

def test_case_collisions_are_rejected(delivery):
    root,m,tracked=delivery
    other=copy.deepcopy(m["files"][0]);other["path"]="studio/core/EXAMPLE.py";m["files"].append(other)
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)

def test_protected_component_must_match_actual_git_tree(delivery):
    root,m,tracked=delivery
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,"2"*40)

@pytest.mark.parametrize("mutation",["absent","unverified","zero","unknown"])
def test_reviews_require_exact_nonempty_evidence(delivery,mutation):
    root,m,tracked=delivery
    evidence=m["review_evidence"]
    if mutation=="absent":del evidence["credentials"]
    elif mutation=="unverified":evidence["credentials"]["verified"]=False
    elif mutation=="zero":evidence["credentials"]["sha256"]="0"*64
    else:evidence["extra"]={"verified":True,"sha256":"1"*64}
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)

def test_duplicate_json_fields_fail_closed():
    with pytest.raises(contract.DeliveryError): json.loads('{"schema":1,"schema":1}',object_pairs_hook=contract.no_duplicates)

def test_linked_directory_is_not_trusted(delivery,tmp_path):
    root,m,tracked=delivery
    target=tmp_path/"outside";target.mkdir()
    folder=root/"studio/core"
    (folder/"example.py").unlink();folder.rmdir()
    try:folder.symlink_to(target,target_is_directory=True)
    except OSError:pytest.skip("symlink privilege unavailable")
    with pytest.raises(contract.DeliveryError): contract.verify(root,m,tracked,contract.PROTECTED_TREE)


@pytest.mark.parametrize("name", contract.HOST_RUNTIME_NAMES)
def test_exact_docker_runtime_dependencies_remain_deliverable(delivery,name):
    root,m,tracked=delivery
    rel=contract.HOST_PREFIX+name
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b"synthetic dependency")
    row={"path":rel,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    m["files"].append(row);tracked.add(rel)
    assert contract.verify(root,m,tracked,contract.PROTECTED_TREE)["files"]==2

@pytest.mark.parametrize("name", ["extra.py","profiles/private.json","private-token",
                                 "ultimate-slicer-server.service","ultimate-slicer-dispatch.timer"])
def test_unlisted_host_files_and_units_stay_blocked(delivery,name):
    root,m,tracked=delivery
    m["files"][0]["path"]=contract.HOST_PREFIX+name
    with pytest.raises(contract.DeliveryError):contract.verify(root,m,tracked,contract.PROTECTED_TREE)


NATIVE_REVIEWED_PATHS = (
    "studio/deploy/homeassistant/host/release/fresh-install-preflight.sh",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/deploy-native-slicer.sh",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-server.service",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-dispatch.service",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-dispatch.timer",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-refresh.service",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-refresh.timer",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-server.service",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-dispatch.service",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-dispatch.timer",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-refresh.service",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-refresh.timer",
)

@pytest.mark.parametrize("rel", NATIVE_REVIEWED_PATHS)
def test_exact_reviewed_native_test_sources_are_deliverable(delivery,rel):
    root,m,tracked=delivery
    p=root/rel
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(b"synthetic source only; never executed\n")
    row={"path":rel,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
    m["files"].append(row);tracked.add(rel)
    result=contract.verify(root,m,tracked,contract.PROTECTED_TREE)
    assert result["files"]==2 and result["production_approved"] is False

@pytest.mark.parametrize("rel", [
    "studio/packages/ultimate-slicer-server/systemd/another.service",
    "studio/packages/ultimate-slicer-server/systemd/ultimate-slicer-server-copy.service",
    "studio/deploy/homeassistant/host/release/another-preflight.sh",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/systemd/another.service",
    "studio/deploy/homeassistant/host/3d-printer-slicing-server/deploy-native-slicer-copy.sh",
])
def test_native_test_scope_does_not_expand_to_other_sources(delivery,rel):
    root,m,tracked=delivery
    m["files"][0]["path"]=rel
    with pytest.raises(contract.DeliveryError):
        contract.verify(root,m,tracked,contract.PROTECTED_TREE)


@pytest.mark.parametrize('name', contract.PUBLIC_GUIDE_PATHS)
def test_only_individually_reviewed_setup_guides_are_deliverable(delivery,name):
    root,m,tracked=delivery
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'synthetic public guide')
    m['files'].append({'path':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    tracked.add(name)
    assert contract.verify(root,m,tracked,contract.PROTECTED_TREE)['files']==2

@pytest.mark.parametrize('name',[
    'studio/docs/X1C_SETUP-private.md','studio/docs/branding/private.svg',
    'studio/docs/ROADMAP.md','studio/DOCS/private.md','STUDIO/docs/X1C_SETUP.md',contract.HOST_PREFIX+'bambu_lab_x1c_04-copy.json',
    contract.HOST_PREFIX+'profiles/printers/bambu_lab_x1c_04-copy.json'])
def test_public_setup_allowlist_does_not_include_similar_private_paths(delivery,name):
    root,m,tracked=delivery;m['files'][0]['path']=name
    with pytest.raises(contract.DeliveryError):contract.verify(root,m,tracked,contract.PROTECTED_TREE)
