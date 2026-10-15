"""Deterministic, secret-free Linux test-server package checks."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SLICER = ROOT / "Slicer-Server"


def module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SLICER / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = module("studio_testserver_package_builder", "prepare_test_server_package.py")
verifier = builder.verifier
context = builder.context


def source(root: Path) -> Path:
    def put(relative: str, data: bytes) -> None:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    host_hashes: dict[str, str] = {}
    dependency_hashes: dict[str, str] = {}
    for name in context.HOST_FILES:
        data = ("synthetic-host:" + name + "\n").encode()
        put(context.HOST + "/" + name, data)
        (dependency_hashes if name == "job_control.py" else host_hashes)[name] = context.digest(data)
    for name in context.COMPONENT_FILES:
        data = ("synthetic-component:" + name + "\n").encode()
        put(context.COMPONENT + "/" + name, data)
        dependency_hashes[name] = context.digest(data)
    put(
        context.HOST + "/SHA256SUMS",
        "".join(value + "  " + key + "\n" for key, value in host_hashes.items()).encode(),
    )
    put(
        context.HOST + "/DEPENDENCY-SHA256SUMS",
        "".join(value + "  " + key + "\n" for key, value in dependency_hashes.items()).encode(),
    )
    put(
        "packages/ultimate-slicer-server/release.json",
        b'{"version":"0.1.0-test","api_protocol":2}\n',
    )
    for name in context.SUPPORT_FILES:
        put("Slicer-Server/" + name, ("fixture:" + name + "\n").encode())
    for relative in builder.PACKAGE_FILES:
        if relative.endswith("/verify_test_server_package.py"):
            data = (SLICER / "verify_test_server_package.py").read_bytes()
        else:
            data = ("test-package-fixture:" + relative + "\n").encode()
        put(relative, data)
    for name in (*context.LICENSE_FILES, "PAYLOAD_PROVENANCE.json", context.PROFILE_SOURCE_FILE):
        put("Slicer-Server/" + name, (ROOT / "Slicer-Server" / name).read_bytes())
    provenance_path = root / "Slicer-Server/PAYLOAD_PROVENANCE.json"
    provenance = json.loads(provenance_path.read_text())
    for row in provenance["payload_files"]:
        row["sha256"] = context.digest((root / row["source"]).read_bytes())
    provenance_path.write_text(json.dumps(provenance))
    return root


def test_package_is_byte_deterministic_and_self_verified(tmp_path):
    root = source(tmp_path / "source")
    first = builder.build(root, tmp_path / "first")
    second = builder.build(root, tmp_path / "second")
    assert first["archive_sha256"] == second["archive_sha256"]
    assert first["manifest_sha256"] == second["manifest_sha256"]
    for name in (builder.ARCHIVE_NAME, builder.VERIFIER_NAME, builder.SUMS_NAME):
        assert (tmp_path / "first" / name).read_bytes() == (tmp_path / "second" / name).read_bytes()
    result = verifier.verify_package_dir(tmp_path / "first")
    assert result["verified"] is True and result["sidecar_verified"] is True
    assert result["container_deploy_ready"] is False
    assert result["engine_included"] is False
    assert result["secret_files_included"] is False


def test_archive_contains_only_manifested_secret_free_files(tmp_path):
    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    archive_path = tmp_path / "package" / builder.ARCHIVE_NAME
    with tarfile.open(archive_path, "r:gz") as archive:
        names = [member.name for member in archive.getmembers() if member.isreg()]
        manifest = json.loads(
            archive.extractfile(f"{builder.ROOT_NAME}/{builder.MANIFEST_NAME}").read()
        )
    expected = {
        f"{builder.ROOT_NAME}/{row['path']}" for row in manifest["files"]
    } | {f"{builder.ROOT_NAME}/{builder.MANIFEST_NAME}"}
    assert set(names) == expected
    assert manifest["container_deploy_ready"] is False
    assert manifest["engine_included"] is False
    assert manifest["secret_files_included"] is False
    assert "clean_host_preflight.py" in {row["path"] for row in manifest["files"]}
    assert "compose.candidate.yaml" in {row["path"] for row in manifest["files"]}
    assert "linux_test_evidence.py" in {row["path"] for row in manifest["files"]}
    assert not any("api-token" == row["path"] or row["path"].endswith(".key") for row in manifest["files"])


def test_verified_extraction_is_new_target_and_hash_exact(tmp_path):
    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    archive_path = tmp_path / "package" / builder.ARCHIVE_NAME
    result = verifier.extract_verified(archive_path, tmp_path / "extracted")
    assert result["extracted"] is True
    assert verifier.verify_extracted(tmp_path / "extracted")["verified"] is True
    with pytest.raises(verifier.PackageError, match="extract_target_exists"):
        verifier.extract_verified(archive_path, tmp_path / "extracted")


@pytest.mark.parametrize(
    "payload,error",
    [
        (b"-----BEGIN PRIVATE KEY-----\nnot-a-real-key\n", "private_key_material_rejected"),
        (b"https://slicer.internal/example\n", "private_domain_rejected"),
        (b"AKIAABCDEFGHIJKLMNOP\n", "cloud_credential_pattern_rejected"),
        (b"ghp_abcdefghijklmnopqrstuvwxyz0123456789\n", "github_credential_pattern_rejected"),
    ],
)
def test_secret_patterns_are_rejected_before_output(tmp_path, payload, error):
    root = source(tmp_path / "source")
    (root / "Slicer-Server/LINUX_TEST_SERVER_RUNBOOK.md").write_bytes(payload)
    with pytest.raises(verifier.PackageError, match=error):
        builder.build(root, tmp_path / "package")
    assert not (tmp_path / "package").exists()


def test_sidecar_detects_archive_tampering(tmp_path):
    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    archive_path = tmp_path / "package" / builder.ARCHIVE_NAME
    archive_path.chmod(0o644)
    archive_path.write_bytes(archive_path.read_bytes() + b"tamper")
    with pytest.raises(verifier.PackageError, match="package_sidecar_mismatch"):
        verifier.verify_package_dir(tmp_path / "package")


def test_existing_or_in_source_output_is_rejected_without_change(tmp_path):
    root = source(tmp_path / "source")
    existing = tmp_path / "existing"
    existing.mkdir()
    keep = existing / "keep"
    keep.write_bytes(b"keep")
    with pytest.raises(builder.BuildError, match="output_already_exists"):
        builder.build(root, existing)
    assert keep.read_bytes() == b"keep"
    with pytest.raises(builder.BuildError, match="output_must_be_outside_source"):
        builder.build(root, root / "generated")
    assert not (root / "generated").exists()


def test_verifier_rejects_unexpected_neighbor(tmp_path):
    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    (tmp_path / "package" / "unexpected.txt").write_text("unexpected")
    with pytest.raises(verifier.PackageError, match="package_directory_file_set_mismatch"):
        verifier.verify_package_dir(tmp_path / "package")


def test_real_source_archive_is_repeatable_without_writes():
    first_payload, first_manifest = builder.collect(ROOT)
    second_payload, second_manifest = builder.collect(ROOT)
    first = builder.archive_bytes(first_payload)
    second = builder.archive_bytes(second_payload)
    assert first == second
    assert first_manifest == second_manifest
    assert builder.digest(first) == builder.digest(second)

@pytest.mark.parametrize(
    "payload",
    [
        b"https://slicer.internal/example",
        b"HTTPS://SLICER.INTERNAL:9443/example",
        b"https://slicer.internal./example",
        b"https://worker.lab.local/api",
        b'{"host": "worker.lab.internal"}',
        b"slicer.internal",
        b"(worker.local)",
    ],
)
def test_internal_hostnames_are_rejected(payload):
    with pytest.raises(verifier.PackageError, match="private_domain_rejected"):
        verifier._secret_free(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"https://slicer.internal.example/example",
        b"https://worker.local.example/api",
        b"https://internal.example/example",
        b"https://slicer.example/example",
        b"Internal package paths and local files are documented.",
    ],
)
def test_public_examples_and_local_prose_are_not_private_hostnames(payload):
    verifier._secret_free(payload)

@pytest.mark.parametrize(
    "payload",
    [
        b"https://unreviewed.invalid/path",
        b"https://192.168.50.10:9443/api",
        b"https://127.0.0.1/api",
        b"https://[::1]/api",
        b"https://github.com.unreviewed.invalid/path",
        b"https://user@github.com/path",
        b"https://user:synthetic@github.com/path",
        b"https://github.com:9443/path",
        b"http://github.com/path",
        b"https://github.com/path?token=synthetic",
        b"https://github%2ecom/path",
        b"https://github.com:bad/path",
        b"https://[not-an-ip]/path",
        b"https://",
        b"https://github.com\\\\unreviewed.invalid/path",
        b"unreviewed.invalid",
        b"header\nunreviewed.invalid\nfooter",
    ],
)
def test_unreviewed_network_references_are_rejected(payload):
    with pytest.raises(verifier.PackageError, match="private_domain_rejected"):
        verifier._secret_free(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"https://github.com/bambulab/BambuStudio/blob/master/LICENSE",
        b"https://GITHUB.COM.:443/example#section",
        b"https://opensource.org/license/mit",
        b"https://docs.github.com/en/example",
        b"https://docs.docker.com/reference/compose-file/services/).",
        b"http://schemas.microsoft.com/3dmanufacturing/core/2015/02",
        b"https://slicer.example/api",
        b"slicer.example",
        b"docs.github.com",
    ],
)
def test_reviewed_public_references_and_synthetic_examples_are_allowed(payload):
    verifier._secret_free(payload)


def test_unreviewed_url_is_rejected_before_package_output(tmp_path):
    root = source(tmp_path / "source")
    (root / "Slicer-Server/LINUX_TEST_SERVER_RUNBOOK.md").write_bytes(
        b"https://unreviewed.invalid/api"
    )
    with pytest.raises(verifier.PackageError, match="private_domain_rejected"):
        builder.build(root, tmp_path / "package")
    assert not (tmp_path / "package").exists()

@pytest.mark.parametrize("representation", ["archive", "extracted"])
def test_matching_hashes_do_not_approve_unreviewed_network_references(tmp_path, representation):
    root = source(tmp_path / "source")
    payload, manifest = builder.collect(root)
    relative = "CONTAINER_TESTING.md"
    payload[relative] = b"https://unreviewed.invalid/api"
    row = next(row for row in manifest["files"] if row["path"] == relative)
    row["size_bytes"] = len(payload[relative])
    row["sha256"] = builder.digest(payload[relative])
    payload[builder.MANIFEST_NAME] = (
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    ).encode()
    if representation == "archive":
        archive = tmp_path / "candidate.tar.gz"
        archive.write_bytes(builder.archive_bytes(payload))
        with pytest.raises(verifier.PackageError, match="private_domain_rejected"):
            verifier.verify_archive(archive)
    else:
        extracted = tmp_path / "extracted"
        for relative, data in payload.items():
            target = extracted / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        with pytest.raises(verifier.PackageError, match="private_domain_rejected"):
            verifier.verify_extracted(extracted)


@pytest.mark.parametrize("name,expected", [
    ("licenses/MIT-Studio.txt", "2cd47d14537993c48a899d2a3e6b30cf764ea31e18a468b662263e1f14027708"),
    ("licenses/AGPL-BambuStudio.txt", "57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6"),
])
def test_real_package_preserves_exact_inherited_license_notices(tmp_path, name, expected):
    result = builder.build(ROOT, tmp_path / "package")
    with tarfile.open(tmp_path / "package" / builder.ARCHIVE_NAME, "r:gz") as archive:
        data = archive.extractfile(builder.ROOT_NAME + "/context/" + name).read()
    assert builder.digest(data) == expected
    assert result["container_deploy_ready"] is False


def test_real_context_carries_profile_origins_and_transformations():
    payload, manifest = context.collect(ROOT)
    provenance = json.loads(payload["PAYLOAD_PROVENANCE.json"])
    assert len(provenance["payload_files"]) == 19
    assert len(provenance["profiles"]) == 54
    assert len(provenance["upstream_files"]) == 118
    assert provenance["upstream_commit"] == "42d319c6692fa8e64790fddf0cdaafd2a4254bcc"
    assert provenance["publication_approved"] is False
    for row in provenance["payload_files"]:
        assert builder.digest(payload[row["path"]]) == row["sha256"]
    scopes = {row["path"]: row["license_scope"] for row in manifest["files"]}
    assert scopes["licenses/MIT-Studio.txt"] == "inherited-license-notice"
    assert scopes["licenses/AGPL-BambuStudio.txt"] == "third-party-license-notice"
    assert "first upstream vector element" in provenance["transformations"]["process_fields"]
    assert "sound" in provenance["transformations"]["machine_gcode"]


@pytest.mark.parametrize("name", ["licenses/MIT-Studio.txt", "licenses/AGPL-BambuStudio.txt"])
@pytest.mark.parametrize("mutation", ["missing", "changed"])
def test_missing_or_changed_license_blocks_package_before_output(tmp_path, name, mutation):
    root = source(tmp_path / "source")
    path = root / "Slicer-Server" / name
    if mutation == "missing":
        path.unlink()
        error = FileNotFoundError
        match = None
    else:
        path.write_bytes(path.read_bytes() + b"changed")
        error = context.ContextError
        match = "license_notice_digest_mismatch"
    with pytest.raises(error, match=match):
        builder.build(root, tmp_path / "package")
    assert not (tmp_path / "package").exists()


@pytest.mark.parametrize("reference", [
    b"http://www.gnu.org/licenses/",
    b"http://fsf.org/",
])
def test_exact_upstream_license_origins_are_allowed(reference):
    verifier._secret_free(reference)


@pytest.mark.parametrize("reference", [
    b"https://www.gnu.org/licenses/",
    b"http://www.gnu.org.unreviewed.invalid/licenses/",
    b"http://fsf.org:8080/",
    b"http://user@fsf.org/",
    b"http://fsf.org/?token=synthetic",
])
def test_license_origin_extension_keeps_authority_restrictions(reference):
    with pytest.raises(verifier.PackageError, match="private_domain_rejected"):
        verifier._secret_free(reference)


def test_docker_delivery_keeps_license_and_provenance_paths():
    dockerfile = (SLICER / "Dockerfile").read_text()
    ignore = (SLICER / ".dockerignore").read_text().splitlines()
    assert "COPY --chown=65532:65532 licenses/ ./licenses/" in dockerfile
    assert "THIRD_PARTY_NOTICES.md PAYLOAD_PROVENANCE.json ./" in dockerfile
    assert {"!licenses/", "!licenses/**", "!PAYLOAD_PROVENANCE.json"} <= set(ignore)


@pytest.mark.parametrize("mutation", ["stale_hash", "missing_row", "duplicate_row", "release_flag"])
def test_stale_or_incomplete_provenance_blocks_package_before_output(tmp_path, mutation):
    root = source(tmp_path / "source")
    path = root / "Slicer-Server/PAYLOAD_PROVENANCE.json"
    provenance = json.loads(path.read_text())
    if mutation == "stale_hash":
        provenance["payload_files"][0]["sha256"] = "0" * 64
    elif mutation == "missing_row":
        provenance["payload_files"].pop()
    elif mutation == "duplicate_row":
        provenance["payload_files"][-1] = provenance["payload_files"][0]
    else:
        provenance["publication_approved"] = True
    path.write_text(json.dumps(provenance))
    with pytest.raises(context.ContextError, match="payload_provenance_mismatch"):
        builder.build(root, tmp_path / "package")
    assert not (tmp_path / "package").exists()


def test_extraction_uses_writable_staging_then_postorder_final_modes(tmp_path, monkeypatch):
    """Synthetic POSIX owner-write model; not an actual Linux/UID acceptance."""
    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    output = tmp_path / "extracted"
    modes = {}
    finalized = []
    verified = []
    original_mkdir, original_open, original_chmod = Path.mkdir, Path.open, Path.chmod
    original_verify = verifier.verify_extracted

    def mkdir(path, mode=0o777, parents=False, exist_ok=False):
        if not path.exists() and path.parent in modes:
            assert modes[path.parent] & 0o200, "parent must remain writable during creation"
        result = original_mkdir(path, mode=mode, parents=parents, exist_ok=exist_ok)
        if path == output or output in path.parents:
            modes.setdefault(path, mode)
        return result

    def open_file(path, mode="r", *args, **kwargs):
        if "x" in mode and path.parent in modes:
            assert modes[path.parent] & 0o200, "parent must remain writable during extraction"
        return original_open(path, mode, *args, **kwargs)

    def chmod(path, mode, *args, **kwargs):
        if path in modes:
            if mode == 0o555:
                assert verified, "verify bytes before final directory protection"
                finalized.append(path)
            modes[path] = mode
        return original_chmod(path, mode, *args, **kwargs)

    def verify(path):
        result = original_verify(path)
        verified.append(path)
        return result

    with monkeypatch.context() as patch:
        patch.setattr(Path, "mkdir", mkdir)
        patch.setattr(Path, "open", open_file)
        patch.setattr(Path, "chmod", chmod)
        patch.setattr(verifier, "verify_extracted", verify)
        assert verifier.extract_verified(tmp_path / "package" / builder.ARCHIVE_NAME, output)["extracted"]
    assert modes[output] == 0o700
    assert set(finalized) == set(modes) - {output}
    assert [len(p.parts) for p in finalized] == sorted(
        (len(p.parts) for p in finalized), reverse=True
    )
    assert all(mode == 0o555 for path, mode in modes.items() if path != output)


@pytest.mark.parametrize("phase", ["readback", "verify", "finalize"])
def test_extraction_failure_removes_only_owned_tree(tmp_path, monkeypatch, phase):
    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    output = tmp_path / "extracted"
    neighbor = tmp_path / "keep"
    neighbor.write_bytes(b"unrelated")
    regular, chmod = verifier._regular_bytes, Path.chmod

    def readback(path, limit):
        if phase == "readback" and output in path.parents:
            raise OSError("injected_readback")
        return regular(path, limit)

    def verify(path):
        raise OSError("injected_verify")

    def finalize(path, mode, *args, **kwargs):
        if phase == "finalize" and mode == 0o555 and path.is_dir() and output in path.parents:
            raise OSError("injected_finalize")
        return chmod(path, mode, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(verifier, "_regular_bytes", readback)
        if phase == "verify":
            patch.setattr(verifier, "verify_extracted", verify)
        patch.setattr(Path, "chmod", finalize)
        with pytest.raises(OSError, match="injected_" + phase):
            verifier.extract_verified(tmp_path / "package" / builder.ARCHIVE_NAME, output)
    assert not output.exists()
    assert neighbor.read_bytes() == b"unrelated"


def test_extraction_cleanup_failure_is_reported_not_silenced(tmp_path, monkeypatch):
    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    output = tmp_path / "extracted"
    original_unlink = Path.unlink

    def reject_verify(path):
        raise OSError("injected_verify")

    def reject_unlink(path, *args, **kwargs):
        if output in path.parents:
            raise PermissionError("injected_cleanup")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(verifier, "verify_extracted", reject_verify)
        patch.setattr(Path, "unlink", reject_unlink)
        with pytest.raises(verifier.PackageError, match="extract_cleanup_failed"):
            verifier.extract_verified(tmp_path / "package" / builder.ARCHIVE_NAME, output)
    assert output.exists()  # Explicit failure leaves evidence for the operator.


# Manifest and archive names must keep the same meaning on Windows and POSIX.
@pytest.mark.parametrize("name", [
    r"..\outside.txt",
    r"nested\..\outside.txt",
    r"C:\outside.txt",
    "C:outside.txt",
    "nested/file:stream",
    "nested/\x00file",
])
def test_manifest_rejects_nonportable_path_syntax(name):
    with pytest.raises(verifier.PackageError, match="invalid_manifest_path"):
        verifier._canonical_relative(name)


@pytest.mark.parametrize("name", [
    r"..\outside.txt",
    r"nested\..\outside.txt",
    r"C:\outside.txt",
    "C:outside.txt",
    "nested/file:stream",
    "nested/\x00file",
])
def test_archive_member_rejects_nonportable_path_syntax(name):
    member = tarfile.TarInfo(verifier.ROOT_NAME + "/" + name)
    with pytest.raises(verifier.PackageError, match="unsafe_archive_path"):
        verifier._member_name(member)


@pytest.mark.parametrize("name", ["profiles/example.json", "nested/file-name.txt", "file_name"])
def test_portable_posix_names_remain_exact(name):
    assert verifier._canonical_relative(name) == name
    member = tarfile.TarInfo(verifier.ROOT_NAME + "/" + name)
    assert verifier._member_name(member) == verifier.ROOT_NAME + "/" + name


@pytest.mark.parametrize("name", [r"..\outside.txt", "C:outside.txt", "file:stream"])
def test_matching_manifest_and_archive_do_not_approve_nonportable_names(tmp_path, name, monkeypatch):
    import copy
    import io

    root = source(tmp_path / "source")
    builder.build(root, tmp_path / "package")
    original = tmp_path / "package" / builder.ARCHIVE_NAME
    with tarfile.open(original, "r:gz") as archive:
        members = archive.getmembers()
        payloads = {m.name: archive.extractfile(m).read() for m in members if m.isreg()}
    manifest_name = verifier.ROOT_NAME + "/" + verifier.MANIFEST_NAME
    manifest = json.loads(payloads[manifest_name])
    row = next(row for row in manifest["files"] if "/" not in row["path"])
    old_name = verifier.ROOT_NAME + "/" + row["path"]
    new_name = verifier.ROOT_NAME + "/" + name
    row["path"] = name
    payloads[manifest_name] = json.dumps(manifest, sort_keys=True).encode()
    payloads[new_name] = payloads.pop(old_name)
    rewritten = tmp_path / "matching-nonportable.tar.gz"
    with tarfile.open(rewritten, "w:gz") as archive:
        for original_member in members:
            member = copy.copy(original_member)
            if member.name == old_name:
                member.name = new_name
            if member.isreg():
                data = payloads[member.name]
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            else:
                archive.addfile(member)
    # Only verify metadata/bytes. Never extract an archive accepted by the old code.
    with pytest.raises(verifier.PackageError, match="unsafe_archive_path|invalid_manifest_path"):
        verifier.verify_archive(rewritten)

    # A changed verifier must reject before even creating the outer output directory.
    def no_output_creation(*args, **kwargs):
        raise AssertionError("invalid archive reached filesystem mutation")
    monkeypatch.setattr(verifier.Path, "mkdir", no_output_creation)
    with pytest.raises(verifier.PackageError, match="unsafe_archive_path|invalid_manifest_path"):
        verifier.extract_verified(rewritten, tmp_path / "must-not-exist")
