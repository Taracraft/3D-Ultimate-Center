"""Build and verify the complete reviewed slicer source projection; no live actions."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat

SOURCE_PATHS = (
    "Slicer-Server/.dockerignore",
    "Slicer-Server/API.md",
    "Slicer-Server/BAMBU_BUILD_REFERENCE.json",
    "Slicer-Server/CONTAINER_TESTING.md",
    "Slicer-Server/DATA_PERSISTENCE.md",
    "Slicer-Server/DOCKER_QUICKSTART.md",
    "Slicer-Server/Dockerfile",
    "Slicer-Server/ENGINE_CATALOG.md",
    "Slicer-Server/ENGINE_LAYOUT.md",
    "Slicer-Server/ENGINE_PROVENANCE.md",
    "Slicer-Server/HA_INSTALLATION_PLAN.md",
    "Slicer-Server/HANDBUCH.md",
    "Slicer-Server/HOST_LIFECYCLE.md",
    "Slicer-Server/HOST_PAIRING.md",
    "Slicer-Server/HOST_STORAGE.md",
    "Slicer-Server/INSTALLATION.md",
    "Slicer-Server/INSTALLER_HOST_CHANNEL_DECISION.md",
    "Slicer-Server/INSTALLER_TRANSPORT.md",
    "Slicer-Server/LICENSE",
    "Slicer-Server/LINUX_SETUP.md",
    "Slicer-Server/MAINTENANCE.md",
    "Slicer-Server/MIGRATION.md",
    "Slicer-Server/OPERATIONS.md",
    "Slicer-Server/PACKAGE_ACTIVATION.md",
    "Slicer-Server/PACKAGE_STAGING.md",
    "Slicer-Server/PAYLOAD_PROVENANCE.json",
    "Slicer-Server/PERSISTENT_PROFILES.md",
    "Slicer-Server/PROFILE_SOURCE_BUNDLE.json",
    "Slicer-Server/README.md",
    "Slicer-Server/REPOSITORY_CONTENTS.md",
    "Slicer-Server/REPOSITORY_NOTICES.md",
    "Slicer-Server/REPOSITORY_README.md",
    "Slicer-Server/RELEASE_STATUS.md",
    "Slicer-Server/SUPERVISOR_APP_SETUP.md",
    "Slicer-Server/RESOURCE_VALIDATION.md",
    "Slicer-Server/RESTRICTED_INSTALLER.md",
    "Slicer-Server/RUNTIME_INSTALLATION.md",
    "Slicer-Server/RUNTIME_PERMISSIONS.md",
    "Slicer-Server/IMAGE_EVIDENCE.md",
    "Slicer-Server/verify_image_evidence.py",
    "Slicer-Server/TARGET_BASE_REFERENCE.json",
    "Slicer-Server/TARGET_IMAGE_REFERENCE.json",
    "Slicer-Server/THIRD_PARTY_NOTICES.md",
    "Slicer-Server/Ultimate_Slicer_Server_Handbuch.pdf",
    "Slicer-Server/assets/ASSET_NOTICES.md",
    "Slicer-Server/assets/slicer-hero.png",
    "Slicer-Server/assets/taracraft-mark.png",
    "Slicer-Server/build_repository.py",
    "Slicer-Server/ENGINE_BUNDLE_BUILD.md",
    "Slicer-Server/ENGINE_BUNDLE_REFERENCE.json",
    "Slicer-Server/build_engine_bundle.py",
    "Slicer-Server/prepare_engine_distribution.py",
    "Slicer-Server/ENGINE_DISTRIBUTION.md",
    "tests/test_studio_engine_distribution.py",
    "Slicer-Server/prepare_catalog_selection.py",
    "tests/test_studio_engine_bundle.py",
    "tests/test_studio_catalog_selection.py",
    "Slicer-Server/clean_host_preflight.py",
    "Slicer-Server/compose.candidate.yaml",
    "Slicer-Server/compose.preview.yaml",
    "Slicer-Server/container_check.py",
    "Slicer-Server/container_engines.py",
    "Slicer-Server/container_probe.py",
    "Slicer-Server/container_runtime.py",
    "Slicer-Server/container_service.py",
    "Slicer-Server/cura_definitions.py",
    "Slicer-Server/docker_host_adapter.py",
    "Slicer-Server/engine_catalog.json",
    "Slicer-Server/engine_catalog.py",
    "Slicer-Server/first_install.py",
    "Slicer-Server/host_lifecycle.py",
    "Slicer-Server/host_storage.py",
    "Slicer-Server/installer_handoff.py",
    "Slicer-Server/installer_lifecycle.py",
    "Slicer-Server/installer_transport.py",
    "Slicer-Server/licenses/AGPL-BambuStudio.txt",
    "Slicer-Server/licenses/MIT-Studio.txt",
    "Slicer-Server/linux_test_evidence.py",
    "Slicer-Server/package_activation.py",
    "Slicer-Server/package_staging.py",
    "Slicer-Server/pairing_registry.py",
    "Slicer-Server/prepare_context.py",
    "Slicer-Server/prepare_test_server_package.py",
    "Slicer-Server/requirements-test.txt",
    "Slicer-Server/restricted_installer.py",
    "Slicer-Server/slicer-source-contract.yml",
    "Slicer-Server/target_image_sbom.py",
    "Slicer-Server/verify_profile_sources.py",
    "Slicer-Server/verify_test_server_package.py",
    "Slicer-Server/wiki/Architektur.md",
    "Slicer-Server/wiki/Betrieb-und-Wiederherstellung.md",
    "Slicer-Server/wiki/Build-und-Tests.md",
    "Slicer-Server/wiki/Docker-Installation.md",
    "Slicer-Server/wiki/Engine-Bestand.md",
    "Slicer-Server/wiki/Fehlerdiagnose.md",
    "Slicer-Server/wiki/Home-Assistant.md",
    "Slicer-Server/wiki/Home.md",
    "Slicer-Server/wiki/Lizenz-und-Nutzung.md",
    "Slicer-Server/wiki/Profile-und-Engines.md",
    "Slicer-Server/wiki/Quellumfang.md",
    "Slicer-Server/wiki/Entwicklungsstand.md",
    "Slicer-Server/wiki/_Sidebar.md",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/bed-temperature-contract.sh",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/filament_parameter_contract.py",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/gcode_artifact_validation.py",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/h2s_native_defaults.json",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/materialize-bambu-machine.py",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/materialize-bambu-multimaterial.py",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/native_filament_defaults.json",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/printer_model_contract.py",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/slicer_execution_contract.py",
    "deploy/homeassistant/custom_components/ultimate_3d_studio/three_mf_mesh_graph.py",
    "deploy/homeassistant/host/3d-printer-slicing-server/DEPENDENCY-SHA256SUMS",
    "deploy/homeassistant/host/3d-printer-slicing-server/SHA256SUMS",
    "deploy/homeassistant/host/3d-printer-slicing-server/append-slicing-journal.sh",
    "deploy/homeassistant/host/3d-printer-slicing-server/bambu_lab_h2s_04.json",
    "deploy/homeassistant/host/3d-printer-slicing-server/deploy-native-slicer.sh",
    "deploy/homeassistant/host/3d-printer-slicing-server/dispatch-job.sh",
    "deploy/homeassistant/host/3d-printer-slicing-server/job_control.py",
    "deploy/homeassistant/host/3d-printer-slicing-server/profiles/printers/bambu_lab_a1_04.json",
    "deploy/homeassistant/host/3d-printer-slicing-server/profiles/printers/bambu_lab_h2s_04.json",
    "deploy/homeassistant/host/3d-printer-slicing-server/progress-pipe-reader.py",
    "deploy/homeassistant/host/3d-printer-slicing-server/refresh-state.sh",
    "deploy/homeassistant/host/3d-printer-slicing-server/server.py",
    "deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-dispatch.service",
    "deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-dispatch.timer",
    "deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-refresh.service",
    "deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-refresh.timer",
    "deploy/homeassistant/host/3d-printer-slicing-server/systemd/3d-printer-slicing-server.service",
    "packages/ultimate-slicer-server/README.md",
    "packages/ultimate-slicer-server/LINUX_TESTING.md",
    "packages/ultimate-slicer-server/build_native_package.py",
    "packages/ultimate-slicer-server/build_target_testkit.py",
    "packages/ultimate-slicer-server/check_target_host.sh",
    "packages/ultimate-slicer-server/install_native.py",
    "packages/ultimate-slicer-server/release.json",
    "packages/ultimate-slicer-server/run_isolated_test.sh",
    "packages/ultimate-slicer-server/systemd/ultimate-slicer-dispatch.service",
    "packages/ultimate-slicer-server/systemd/ultimate-slicer-dispatch.timer",
    "packages/ultimate-slicer-server/systemd/ultimate-slicer-refresh.service",
    "packages/ultimate-slicer-server/systemd/ultimate-slicer-refresh.timer",
    "packages/ultimate-slicer-server/systemd/ultimate-slicer-server.service",
    "tests/native_linux_install_sandbox.py",
    "tests/native_slicer_https_probe.py",
    "tests/native_slicer_tls_acceptance.ps1",
    "tests/test_studio_clean_host_preflight.py",
    "tests/test_studio_container_engines.py",
    "tests/test_studio_engine_image_layout.py",
    "tests/test_studio_image_build_pipeline.py",
    "tests/test_studio_image_evidence.py",
    "tests/test_studio_container_maintenance.py",
    "tests/test_studio_docker_context.py",
    "tests/test_studio_docker_host_adapter.py",
    "tests/test_studio_docker_lifecycle_integration.py",
    "tests/test_studio_engine_catalog.py",
    "tests/test_studio_engine_provenance.py",
    "tests/test_studio_host_lifecycle.py",
    "tests/test_studio_host_storage.py",
    "tests/test_studio_installer_handoff.py",
    "tests/test_studio_installer_lifecycle.py",
    "tests/test_studio_installer_transport.py",
    "tests/test_studio_native_install_transaction.py",
    "tests/test_studio_native_installer.py",
    "tests/test_studio_native_namespace_contract.py",
    "tests/test_studio_native_network_namespace_contract.py",
    "tests/test_studio_native_package.py",
    "tests/test_studio_native_release_metadata.py",
    "tests/test_studio_native_service_units.py",
    "tests/test_studio_native_work_host_testkit.py",
    "tests/test_studio_package_activation.py",
    "tests/test_studio_package_staging.py",
    "tests/test_studio_pairing_registry.py",
    "tests/test_studio_profile_sources.py",
    "tests/test_studio_restricted_installer.py",
    "tests/test_studio_slicer_repository.py",
    "tests/test_studio_release_documentation.py",
    "tests/test_studio_target_image_sbom.py",
    "tests/test_studio_testserver_package.py",
)
ALIASES = {
    "README.md": "Slicer-Server/REPOSITORY_README.md",
    "SOURCE_NOTICES.md": "Slicer-Server/REPOSITORY_NOTICES.md",
    "LICENSE": "Slicer-Server/licenses/MIT-Studio.txt",
    "requirements-test.txt": "Slicer-Server/requirements-test.txt",
    ".github/workflows/slicer-source-contract.yml": "Slicer-Server/slicer-source-contract.yml",
    "assets/ASSET_NOTICES.md": "Slicer-Server/assets/ASSET_NOTICES.md",
    "assets/slicer-hero.png": "Slicer-Server/assets/slicer-hero.png",
    "assets/taracraft-mark.png": "Slicer-Server/assets/taracraft-mark.png",
}
GENERATED = {
    ".gitattributes": b"* -text\n",
    ".gitignore": b"__pycache__/\n.pytest_cache/\n.venv/\n*.pyc\n.env\n.env.*\n!*.example\n",
}
MANIFEST = "slicer-source-manifest.json"
MAX_BYTES = 16 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or p.as_posix() != name or ".." in p.parts or "\\" in name:
        raise ValueError("unsafe_source_path")
    return name


def regular(root, name):
    path = Path(root)
    for p in [path, *path.parents]:
        if p.is_symlink() or getattr(p, "is_junction", lambda: False)():
            raise ValueError("linked_source")
    for part in PurePosixPath(safe_name(name)).parts:
        path /= part
        if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
            raise ValueError("linked_source")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_BYTES:
        raise ValueError("regular_bounded_source_required")
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError("source_changed")
    if len(raw) != before.st_size:
        raise ValueError("source_changed")
    return raw


def collect(root):
    result = {name: (regular(root, name), name) for name in SOURCE_PATHS}
    for name, source in ALIASES.items():
        result[name] = (regular(root, source), source)
    for name, raw in GENERATED.items():
        result[name] = (raw, None)
    return result


def build(root, output):
    root = Path(root).resolve(strict=True)
    output = Path(output)
    if not output.is_absolute() or output.exists() or output.is_symlink():
        raise ValueError("new_absolute_output_required")
    boundary = next((p for p in [root, *root.parents] if (p / '.git').exists()), root)
    if output.resolve().is_relative_to(boundary):
        raise ValueError("output_must_be_outside_source")
    for p in [output.parent, *output.parent.parents]:
        if p.is_symlink() or getattr(p, 'is_junction', lambda: False)():
            raise ValueError('linked_output_parent')
    items = collect(root)
    rows = [{"path": name, "source_path": source, "bytes": len(raw), "sha256": digest(raw),
             "mode": "100755" if name.endswith(".sh") else "100644"}
            for name, (raw, source) in sorted(items.items())]
    manifest = {"schema": 1, "component": "ultimate-slicer-server",
                "scope": "complete reviewed component source and build/test dependency closure",
                "source_paths": len(SOURCE_PATHS), "payload_files": len(rows), "files": rows,
                "engine_binaries_included": False, "private_runtime_data_included": False,
                "native_deploy_ready": False, "container_deploy_ready": False,
                "production_approved": False, "github_wiki_published": False}
    output.mkdir(parents=True)
    for name, (raw, _) in items.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        if name.endswith(".sh"):
            target.chmod(0o755)
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with (output / MANIFEST).open("xb") as stream:
        stream.write(raw)
    return verify(output)


def verify(root):
    root = Path(root).absolute()
    raw = regular(root, MANIFEST)
    value = json.loads(raw)
    if value.get("schema") != 1 or value.get("component") != "ultimate-slicer-server":
        raise ValueError("manifest_schema_mismatch")
    for field in ("engine_binaries_included", "private_runtime_data_included",
                  "native_deploy_ready", "container_deploy_ready", "production_approved",
                  "github_wiki_published"):
        if value.get(field) is not False:
            raise ValueError("unapproved_release_flag")
    rows = value["files"]
    names = [safe_name(row["path"]) for row in rows]
    expected = set(SOURCE_PATHS) | set(ALIASES) | set(GENERATED)
    if len(names) != len(set(names)) or set(names) != expected or value["payload_files"] != len(rows):
        raise ValueError("source_closure_mismatch")
    for row in rows:
        data = regular(root, row["path"])
        if len(data) != row["bytes"] or digest(data) != row["sha256"]:
            raise ValueError("source_digest_mismatch:" + row["path"])
    return {"verified": True, "source_paths": len(SOURCE_PATHS),
            "payload_files": len(rows), "manifest_sha256": digest(raw),
            "source_bytes": sum(row["bytes"] for row in rows),
            "engine_executed": False, "installation_performed": False,
            "production_approved": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if args.verify and not (args.source_root or args.output):
        result = verify(args.verify)
    elif args.source_root and args.output and not args.verify:
        result = build(args.source_root, args.output)
    else:
        parser.error("use --verify ROOT or --source-root ROOT --output NEW_ABSOLUTE_PATH")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()


