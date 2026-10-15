"""Offline profile persistence contract; no container, engine or printer started."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "deploy/homeassistant/host/3d-printer-slicing-server"
spec = importlib.util.spec_from_file_location("persistent_profile_service", ROOT / "Slicer-Server/container_service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

@pytest.fixture
def store(tmp_path):
    base, seed = tmp_path / "volume", tmp_path / "seed"
    base.mkdir()
    seed.mkdir()
    (seed / "fixture.json").write_text(json.dumps({"id": "fixture", "name": "original"}))
    return base, seed

def test_initialize_preserves_edits_and_does_not_adopt_new_image_seeds(store):
    base, seed = store
    assert service.initialize_profiles(base, seed=seed)["initialized"]
    path = base / "printers/fixture.json"
    path.write_text(json.dumps({"id": "fixture", "name": "user edit"}))
    before = path.read_bytes()
    receipt = (base / "PROFILE_STATE.json").read_bytes()
    (seed / "fixture.json").write_text(json.dumps({"id": "fixture", "name": "new image"}))
    assert service.initialize_profiles(base, seed=seed) == {"initialized": False, "state": "ready"}
    assert path.read_bytes() == before
    assert (base / "PROFILE_STATE.json").read_bytes() == receipt
    assert service.persistent_profiles(base) == base / "printers"

def test_missing_mount_and_unprepared_runtime_are_rejected(store):
    base, seed = store
    with pytest.raises(ValueError, match="directory_required"):
        service.initialize_profiles(base / "absent", seed=seed)
    assert not (base / "absent").exists()
    with pytest.raises(ValueError):
        service.configure_environment(base, base)
    with pytest.raises(ValueError, match="absolute_path"):
        service.initialize_profiles(Path("relative"), seed=seed)

def test_foreign_contents_are_not_adopted(store):
    base, seed = store
    foreign = base / "keep.txt"
    foreign.write_bytes(b"unchanged")
    with pytest.raises(ValueError, match="foreign_contents"):
        service.initialize_profiles(base, seed=seed)
    assert foreign.read_bytes() == b"unchanged"
    assert not (base / "PROFILE_STATE.json").exists()

@pytest.mark.parametrize("raw", [
    b'[]', b'{"id":"wrong"}', b'{"id":"fixture","id":"fixture"}',
    b'{"id":"fixture","value":NaN}', b"x" * 65537,
], ids=["array", "wrong-id", "duplicate-key", "nonfinite", "oversized"])
def test_invalid_seed_does_not_create_receipt(store, raw):
    base, seed = store
    (seed / "fixture.json").write_bytes(raw)
    with pytest.raises((ValueError, UnicodeError)):
        service.initialize_profiles(base, seed=seed)
    assert not (base / "PROFILE_STATE.json").exists()

@pytest.mark.parametrize("name", ["UPPER.json", "bad.txt", "fixtureXjson", ".hidden.json"])
def test_unsafe_seed_names(store, name):
    base, seed = store
    (seed / "fixture.json").rename(seed / name)
    with pytest.raises(ValueError, match="filename"):
        service.initialize_profiles(base, seed=seed)

def test_seed_count_is_bounded(store):
    base, seed = store
    for i in range(256):
        (seed / f"p{i}.json").write_text(json.dumps({"id": f"p{i}"}))
    with pytest.raises(ValueError, match="count_limit"):
        service.initialize_profiles(base, seed=seed)

def test_interrupted_initialization_is_retained_and_blocks_restart(store, monkeypatch):
    base, seed = store
    original = service._profile_write
    def fail(path, raw):
        if path.parent.name == "printers":
            raise OSError("synthetic interrupted write")
        original(path, raw)
    monkeypatch.setattr(service, "_profile_write", fail)
    with pytest.raises(OSError):
        service.initialize_profiles(base, seed=seed)
    assert json.loads((base / "PROFILE_STATE.json").read_text())["state"] == "preparing"
    monkeypatch.setattr(service, "_profile_write", original)
    with pytest.raises(ValueError, match="recovery_required"):
        service.initialize_profiles(base, seed=seed)
    assert (base / "printers").is_dir()

@pytest.mark.parametrize("mutation", ["state", "digest", "missing", "extra"])
def test_damaged_receipt_or_store_blocks_consumers(store, mutation):
    base, seed = store
    service.initialize_profiles(base, seed=seed)
    receipt = base / "PROFILE_STATE.json"
    value = json.loads(receipt.read_text())
    if mutation == "state":
        value["state"] = "preparing"
    elif mutation == "digest":
        value["seed_sha256"]["fixture.json"] = "bad"
    elif mutation == "missing":
        (base / "printers/fixture.json").unlink()
    else:
        (base / "foreign.txt").write_text("keep")
    receipt.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        service.persistent_profiles(base)

@pytest.mark.skipif(os.name != "posix", reason="POSIX link and lock contract")
@pytest.mark.parametrize("target", ["base", "seed", "profile", "receipt", "lock"])
def test_links_are_rejected(store, target):
    base, seed = store
    if target in {"profile", "receipt", "lock"}:
        service.initialize_profiles(base, seed=seed)
        path = {"profile": base / "printers/fixture.json",
                "receipt": base / "PROFILE_STATE.json",
                "lock": base / ".profile-init.lock"}[target]
        original = path.with_name(path.name + ".saved")
        path.rename(original)
        path.symlink_to(original)
        with pytest.raises((ValueError, OSError)):
            service.initialize_profiles(base, seed=seed)
    else:
        path = base.parent / "alias"
        path.symlink_to(base if target == "base" else seed, target_is_directory=True)
        with pytest.raises(ValueError, match="link_rejected"):
            service.initialize_profiles(path if target == "base" else base,
                                        seed=path if target == "seed" else seed)

@pytest.mark.skipif(os.name != "posix", reason="POSIX hardlink contract")
def test_hardlinked_profile_rejected(store):
    base, seed = store
    os.link(seed / "fixture.json", seed.parent / "alias.json")
    with pytest.raises(ValueError, match="regular_bounded"):
        service.initialize_profiles(base, seed=seed)

def test_second_initializer_cannot_take_lock(store):
    base, seed = store
    with service._profile_lock(base):
        with pytest.raises(OSError):
            service.initialize_profiles(base, seed=seed)
    assert not (base / "PROFILE_STATE.json").exists()

def test_api_and_worker_use_same_persistent_tree(store, monkeypatch):
    base, _ = store
    service.initialize_profiles(base, seed=HOST / "profiles/printers")
    for name in ["STUDIO_WORKER_BASE", "STUDIO_WORKER_SOURCE_ROOT", "STUDIO_WORKER_PROFILE_ROOT",
                 "STUDIO_WORKER_H2S_PROFILE", "STUDIO_BAMBU_ROOT", "STUDIO_WORKER_ISOLATION"]:
        monkeypatch.delenv(name, raising=False)
    data = base.parent / "data"
    data.mkdir()
    service.initialize_data(data)
    service.configure_environment(data, base)
    token, cert, key = [base.parent / name for name in ("token", "cert", "key")]
    token.write_text("s" * 48)
    cert.write_text("synthetic")
    key.write_text("synthetic")
    config = service.api_configuration(data, token, cert, key, base)
    assert config["persistent_profiles"] is True
    assert config["profile_root"] == os.environ["STUDIO_WORKER_PROFILE_ROOT"] == str(base / "printers")
    assert os.environ["STUDIO_WORKER_H2S_PROFILE"] == str(base / "printers/bambu_lab_h2s_04.json")
    # Execute only the pure path-selection assignment, never import/start the server.
    tree = ast.parse((HOST / "server.py").read_text(encoding="utf-8"))
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "H2S_PROFILE" for t in n.targets))
    context = {"CONFIG": config, "PROFILES": Path(config["profile_root"]), "SOURCE_ROOT": HOST}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), "<path selection>", "exec"), context)
    assert context["H2S_PROFILE"] == base / "printers/bambu_lab_h2s_04.json"
    context["CONFIG"] = {}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), "<legacy path selection>", "exec"), context)
    assert context["H2S_PROFILE"] == HOST / "bambu_lab_h2s_04.json"

@pytest.mark.skipif(os.name != "posix", reason="shell expression contract")
def test_dispatch_h2s_override_and_legacy_default():
    text = (HOST / "dispatch-job.sh").read_text()
    line = next(line for line in text.splitlines() if "STUDIO_WORKER_H2S_PROFILE" in line)
    for value, expected in [("", "/synthetic/source/bambu_lab_h2s_04.json"), ("/synthetic/profiles/custom.json", "/synthetic/profiles/custom.json")]:
        env = dict(os.environ, PRINTER="bambu_lab_h2s_04", CODE_ROOT="/synthetic/source",
                   STUDIO_WORKER_H2S_PROFILE=value)
        result = subprocess.run(["/bin/sh", "-c", line + '\nprintf "%s" "$PROFILE_FILE"'],
                                env=env, text=True, capture_output=True, check=True)
        assert result.stdout == expected

def test_compose_init_is_offline_and_consumers_read_only():
    services = json.loads((ROOT / "Slicer-Server/compose.candidate.yaml").read_text())["services"]
    init = services["profile-init"]
    assert init["command"] == ["init-profiles"]
    assert init["network_mode"] == "none" and init["read_only"] is True
    assert init["user"] == "65532:65532" and init["restart"] == "no"
    assert init["cap_drop"] == ["ALL"] and init["pull_policy"] == "never"
    assert len(init["volumes"]) == 1 and init["volumes"][0]["read_only"] is False
    assert services["api"]["depends_on"]["profile-init"]["condition"] == "service_completed_successfully"
    mounts = []
    for role in ("profile-init", "api", "worker"):
        mount = next(v for v in services[role]["volumes"] if v["target"] == service.PROFILE_BASE.as_posix())
        assert mount["bind"]["create_host_path"] is False
        assert mount["read_only"] is (role != "profile-init")
        mounts.append(mount["source"])
    assert len(set(mounts)) == 1
