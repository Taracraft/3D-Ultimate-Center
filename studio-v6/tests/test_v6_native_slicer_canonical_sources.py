from __future__ import annotations

from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy" / "homeassistant"
HOST = DEPLOY / "host" / "3d-printer-slicing-server"
BRIDGE = DEPLOY / "custom_components" / "printer_slicing_server"
V6_COMPONENT = DEPLOY / "custom_components" / "ultimate_3d_studio_v6"

HOST_HASHES = {
    "server.py": "22634e914916103918ac2495c0a88ede4f438fc7254551dba7557c3d0d6330dc",
    "dispatch-job.sh": "a683be8cbf4679d41f410e434824c0b97d03100dc4068765ccb92f94c1972e75",
    "progress-pipe-reader.py": "f5e46d2ffb866d8864b153045eb251982340e502c32ef9339eee1f0a5cee3bad",
    "refresh-state.sh": "7af4bc256bf1d1f4861ecb7740c5f5861cbb8eab8c54e80d8f9503e049fc301d",
    "append-slicing-journal.sh": "9798d21528828c901be4e0f3726908d027c8af60580af88981656c88496d5239",
    "systemd/3d-printer-slicing-server.service": "92607dcdbd2f8cdd61a0de9c4ec0e84033b725d6838fe6bf5d27432adf253ecb",
    "systemd/3d-printer-slicing-dispatch.service": "d7448af9596dddfcf7ea23a8cbb3049e019420303082d1e909efb459874faeed",
    "systemd/3d-printer-slicing-dispatch.timer": "e1d582e1b8a21f7b8adaad1cc19df8b9eccb0fe68c437e4fceba5faa69c78d91",
    "systemd/3d-printer-slicing-refresh.service": "424fa03a956321130ac2f65dee3b9a77d35bc1c5eb3fb8374323c84696d88eaa",
    "systemd/3d-printer-slicing-refresh.timer": "557c7d18b5757a73e346b9f1244ff3fff10942a575c72c8e920502e6f917feed",
}

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

DEPENDENCY_HASHES = {
    "bed-temperature-contract.sh": "f753aac8c0223c6bd69a51107d5b5300d00e11e9f0a90c7d9904cf37dcc69b7d",
    "materialize-bambu-machine.py": "d14dfba152a2b9afc830c5b7eacedb1a653d8a59d1c50431a47624d6e4711c02",
    "materialize-bambu-multimaterial.py": "b484c3a8cf08af931e51fea7d8895017d184bf0ed296d10ec1a939fe65171596",
    "three_mf_mesh_graph.py": "5169c8b0dcc95e0b3f200d4b0b394caa15d16e7cebacda6a7fcb029416d7c969",
    "filament_parameter_contract.py": "39eed60f40638ef04eeeb15bf26397a45938e1aef00b0531b4936b36e77c7563",
    "native_filament_defaults.json": "cbf628b9724e232bb17c31728e8b1cc390f9f9c920def036cc8ca1254a0109a1",
    "slicer_execution_contract.py": "4e454fe926f1b9be887538bd59ad8dd4bf34accf67eabb770cd754f87882f033",
    "gcode_artifact_validation.py": "e513d9fdef3ddda3b7ad4cc6dadffdca8b7af1153e90bea77623c5c50252d237"
}


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_native_slicer_sources_are_exact_live_alpha5_snapshot() -> None:
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


def test_native_slicer_dependencies_still_match_live_contract() -> None:
    dependency_lines = {
        line.strip()
        for line in (HOST / "DEPENDENCY-SHA256SUMS").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    assert len(dependency_lines) == len(DEPENDENCY_HASHES)
    for relative, expected in DEPENDENCY_HASHES.items():
        path = V6_COMPONENT / relative
        assert path.is_file(), relative
        assert _digest(path) == expected, relative
        assert f"{expected}  {relative}" in dependency_lines


def test_native_package_contains_no_runtime_secrets_or_job_data() -> None:
    forbidden = [
        HOST / "config.json",
        HOST / "data",
        HOST / "engines",
        HOST / "profiles",
        HOST / "run",
        HOST / "last_job.json",
    ]
    assert not any(path.exists() for path in forbidden)


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
    source = (ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6/slicer_plate_views_v2.py").read_text(encoding="utf-8")
    assert 'support_style = request.query.get("support_style", "standard").casefold()' in source
    assert '"support_style": support_style' in source
    assert '"tree_slim", "tree_strong", "tree_hybrid", "tree_organic"' in source
