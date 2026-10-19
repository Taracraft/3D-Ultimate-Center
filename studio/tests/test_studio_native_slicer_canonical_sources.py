from __future__ import annotations

from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "homeassistant"
HOST = DEPLOY / "host" / "3d-printer-slicing-server"
BRIDGE = DEPLOY / "custom_components" / "printer_slicing_server"
STUDIO_COMPONENT = DEPLOY / "custom_components" / "ultimate_3d_studio"

# Reviewed cancellation package, X1C source contracts and container profile paths.
# Remaining files retain the previously reviewed baseline.
HOST_HASHES = {'server.py': 'ee114a76ae263a9c78abc83378186fb446f367b182b9b3da6e5f109fadcd5013', 'dispatch-job.sh': 'ce033fc47ee0b072c7c4cd47463f12da3b2d4a4444db6e2f3a4c93fffd44cd24', 'progress-pipe-reader.py': 'f5e46d2ffb866d8864b153045eb251982340e502c32ef9339eee1f0a5cee3bad', 'refresh-state.sh': 'd0d1c3301e33d1aecb02928ea491bedd03b68ca22bbf2d495659af07af17523e', 'append-slicing-journal.sh': '9681d2081d85beaddcc7553fc151aa5f878d6c3d65a5c64c9ae0d85528e6f46f', 'systemd/3d-printer-slicing-server.service': '92607dcdbd2f8cdd61a0de9c4ec0e84033b725d6838fe6bf5d27432adf253ecb', 'systemd/3d-printer-slicing-dispatch.service': 'd7448af9596dddfcf7ea23a8cbb3049e019420303082d1e909efb459874faeed', 'systemd/3d-printer-slicing-dispatch.timer': 'e1d582e1b8a21f7b8adaad1cc19df8b9eccb0fe68c437e4fceba5faa69c78d91', 'systemd/3d-printer-slicing-refresh.service': '424fa03a956321130ac2f65dee3b9a77d35bc1c5eb3fb8374323c84696d88eaa', 'systemd/3d-printer-slicing-refresh.timer': '557c7d18b5757a73e346b9f1244ff3fff10942a575c72c8e920502e6f917feed', 'bambu_lab_h2s_04.json': '22e0839d2cd43e262b28082cb05b1fec68f3692aafcb1193198d193e99118363', 'profiles/printers/bambu_lab_a1_04.json': '6e14440bb058ea99f252f967210333ca06287a2dd0be390e855929fc305a9ed5', 'profiles/printers/bambu_lab_h2s_04.json': '22e0839d2cd43e262b28082cb05b1fec68f3692aafcb1193198d193e99118363', 'bambu_lab_x1c_04.json': 'd15235abdebf86742fb57a7d587512517b6a735f89db299880a2159104d341ef', 'profiles/printers/bambu_lab_x1c_04.json': 'd15235abdebf86742fb57a7d587512517b6a735f89db299880a2159104d341ef'}

BRIDGE_HASHES = {
    "__init__.py": "2b9a59b5438d9e4e31e05fad5de883c83ea158404bbb87c2eba94dcaf8892a18",
    "api.py": "72e9adcd1e635ca51e33814a886eb5971497983fce68ce45acf32eded1dd5bdf",
    "binary_sensor.py": "2eac9472696dc216f6eccb04cebd3e34f78c900e3298f66c9b4a7d6669d4f278",
    "config_flow.py": "e702a1cc872597e444002e2683ebd34f57d64139ffcf54ff9c67ca0fbf20cac1",
    "const.py": "1abb221ae34c34b515ffb0b9ecdd171b27a50bf46aea5065f18951f1d882569c",
    "coordinator.py": "77a8c0495b6adf7d8dd8e206973789090763fa785d33242882c27b6e70c6e0e4",
    "entity.py": "e507cf6ea2742316c4b606c01e32ddc7f1a9c8142d6f42d93b37bb3766fd2d26",
    "frontend.py": "605bdb3facc8ef42eafa1dd6b9af05e953629ccaeb454565bc9cce44bc71b86e",
    "frontend/panel.js": "3f96f70f0b37251a6afbc3713b5f7bc651bd51bc2a335f696b25f8e36d3d9a1a",
    "manifest.json": "395b3a1530ba9ab6926db94c225a1ea5a4d0f00fa1b7b8f10127a235a05e5233",
    "sensor.py": "53dfa3f236aff3d81372cc3967cb6effa8d88d109a0131779c2cd9a39ad96f89",
    "services.yaml": "85c1a01a5655fbcd428c92a7d5726cab920c917f501059dad434045f4e9a54b1",
    "websocket_api.py": "399de25f73c31e4fa90f22fa5f0a416c0ebacf43a9ba998fb09ad23438582ab2",
}

DEPENDENCY_HASHES = {'bed-temperature-contract.sh': 'f753aac8c0223c6bd69a51107d5b5300d00e11e9f0a90c7d9904cf37dcc69b7d', 'materialize-bambu-machine.py': 'cdbf69b11b26045d75c73a72d92d8e36a90cef28080ea3d4b96ff665de6aa525', 'materialize-bambu-multimaterial.py': '571de279233687fdb5c996b8fbdab05318b81be5f2a18bb48a427ceee278e721', 'three_mf_mesh_graph.py': '5169c8b0dcc95e0b3f200d4b0b394caa15d16e7cebacda6a7fcb029416d7c969', 'filament_parameter_contract.py': 'aa6b08a24b76ed0bffbf271772646bafe94a73cb9eda03699c1f37ad3c3833ac', 'native_filament_defaults.json': 'cbf628b9724e232bb17c31728e8b1cc390f9f9c920def036cc8ca1254a0109a1', 'slicer_execution_contract.py': 'e049c3856ca532b95606a25b4b70737691c1dfb027ed8edc1f5ddceeb79b8dae', 'gcode_artifact_validation.py': 'aee716cc01b0e25c70b801e1a2e6584484a421b4a8cde46072abd8f97957d5f1', 'printer_model_contract.py': '6a39dd8053329db742140c166c3540305737744d6896d748a43d0c73854c96fc', 'h2s_native_defaults.json': '959caa3c4a15c9f28aa0cd0a7397686153fccd641037644d6ef27aea60236ee4', 'x1c_native_defaults.json': 'c5a7c124103edeecb7709fcd24b7a07b92ccb7e2b70a98d662511f0372801496'}


# This new supervisor belongs to the native host, not to the HA component.
HOST_DEPENDENCY_HASHES = {'job_control.py': '922f905306aa33268416e1ca79628b0c3731c9fbe8fad50bbb4c04d7e232702a'}

def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_native_slicer_sources_match_reviewed_native_cancellation_package() -> None:
    assert HOST.is_dir()
    for relative, expected in HOST_HASHES.items():
        path = HOST / relative
        assert path.is_file(), relative
        assert _digest(path) == expected, relative

    manifest_lines = {
        line.strip()
        for line in (HOST / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert len(manifest_lines) == len(HOST_HASHES)
    for relative, expected in HOST_HASHES.items():
        assert f"{expected}  {relative}" in manifest_lines


def test_printer_slicing_server_bridge_is_exact_live_snapshot() -> None:
    assert BRIDGE.is_dir()
    for relative, expected in BRIDGE_HASHES.items():
        path = BRIDGE / relative
        assert path.is_file(), relative
        assert _digest(path) == expected, relative

    for path in BRIDGE.rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_native_slicer_dependencies_match_reviewed_native_contract() -> None:
    dependency_lines = {
        line.strip()
        for line in (HOST / "DEPENDENCY-SHA256SUMS").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert len(dependency_lines) == len(DEPENDENCY_HASHES) + len(HOST_DEPENDENCY_HASHES)
    for relative, expected in DEPENDENCY_HASHES.items():
        path = STUDIO_COMPONENT / relative
        assert path.is_file(), relative
        assert _digest(path) == expected, relative
        assert f"{expected}  {relative}" in dependency_lines
    for relative, expected in HOST_DEPENDENCY_HASHES.items():
        path = HOST / relative
        assert path.is_file(), relative
        assert _digest(path) == expected, relative
        assert f"{expected}  {relative}" in dependency_lines
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def test_native_package_contains_no_runtime_secrets_or_job_data() -> None:
    forbidden = [
        HOST / "config.json",
        HOST / "data",
        HOST / "engines",
        HOST / "run",
        HOST / "last_job.json",
    ]
    assert not any(path.exists() for path in forbidden)

    profiles = HOST / "profiles"
    allowed_profiles = {
        Path("printers/bambu_lab_a1_04.json"),
        Path("printers/bambu_lab_h2s_04.json"),
        Path("printers/bambu_lab_x1c_04.json"),
    }
    actual_profiles = {
        path.relative_to(profiles)
        for path in profiles.rglob("*")
        if path.is_file()
    } if profiles.is_dir() else set()
    assert actual_profiles == allowed_profiles
    assert not any(path.is_symlink() for path in profiles.rglob("*")) if profiles.is_dir() else True


def test_native_deployer_is_fail_closed_and_print_safe() -> None:
    deployer = (HOST / "deploy-native-slicer.sh").read_text(encoding="utf-8")
    required_guards = [
        "*.slicing.json",
        "*.queued.json",
        "dispatcher.lock",
        "created_date=$TODAY",
        "SHA256SUMS.before",
        "rollback()",
        "sha256sum -c SHA256SUMS",
        "DEPENDENCY-SHA256SUMS",
        "systemctl stop 3d-printer-slicing-dispatch.timer",
        "systemctl restart 3d-printer-slicing-server.service",
        'progress_source == "bambu_cli_pipe"',
        'runtime_summary == true',
        "Kein Slice und kein Druck wurde gestartet.",
    ]
    for marker in required_guards:
        assert marker in deployer, marker

    forbidden_actions = [
        "/print/start",
        "startDirectPrint",
        "prepareDirectPrint",
        "print_job",
    ]
    for marker in forbidden_actions:
        assert marker not in deployer, marker

def test_plate_slice_route_forwards_bambu_support_style() -> None:
    source = (ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio/slicer_plate_views_v2.py").read_text(encoding="utf-8")
    assert 'support_style = request.query.get("support_style", "standard").casefold()' in source
    assert '"support_style": support_style' in source
    assert '"tree_slim", "tree_strong", "tree_hybrid", "tree_organic"' in source



def test_curated_printer_profiles_only_claim_materialized_engines() -> None:
    import json
    for name in ("bambu_lab_a1_04.json", "bambu_lab_h2s_04.json"):
        profile = json.loads((HOST / "profiles" / "printers" / name).read_text(encoding="utf-8"))
        compatible = set(profile.get("compatible_engines") or [])
        materialized = set((profile.get("engine_profiles") or {}).keys())
        assert compatible == materialized, name
        assert profile.get("preferred_engine") in materialized, name
