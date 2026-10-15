"""Component source projection tests; no deployment, engine or printer actions."""
from pathlib import Path
import importlib.util
import json
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('slicer_repository_builder', ROOT / 'Slicer-Server/build_repository.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_complete_projection_is_reproducible_and_offline(tmp_path):
    a, b = tmp_path / 'first', tmp_path / 'second'
    first = builder.build(ROOT, a)
    second = builder.build(ROOT, b)
    assert first == second
    assert first['verified'] and not first['engine_executed']
    manifest = json.loads((a / builder.MANIFEST).read_text())
    assert {row['path'] for row in manifest['files']} == set(builder.SOURCE_PATHS) | set(builder.ALIASES) | set(builder.GENERATED)
    assert all(manifest[field] is False for field in ['production_approved', 'native_deploy_ready', 'container_deploy_ready', 'engine_binaries_included', 'private_runtime_data_included'])
    assert (a / 'Slicer-Server/PROFILE_SOURCE_BUNDLE.json').read_bytes() == (ROOT / 'Slicer-Server/PROFILE_SOURCE_BUNDLE.json').read_bytes()


def test_existing_and_relative_output_are_rejected(tmp_path):
    target = tmp_path / 'keep'
    target.mkdir()
    sentinel = target / 'keep.txt'
    sentinel.write_text('keep')
    with pytest.raises(ValueError, match='new_absolute_output_required'):
        builder.build(ROOT, target)
    with pytest.raises(ValueError, match='new_absolute_output_required'):
        builder.build(ROOT, Path('relative-output'))
    assert sentinel.read_text() == 'keep'


def test_source_tree_output_is_rejected():
    with pytest.raises(ValueError, match='outside_source'):
        builder.build(ROOT, ROOT / 'never-create-this-output')


def test_tampering_and_missing_source_fail_closed(tmp_path):
    root = tmp_path / 'projection'
    builder.build(ROOT, root)
    target = root / 'README.md'
    original = target.read_bytes()
    target.write_bytes(original + b'changed')
    with pytest.raises(ValueError, match='source_digest_mismatch'):
        builder.verify(root)
    target.write_bytes(original)
    missing = root / 'Slicer-Server/Dockerfile'
    missing.unlink()
    with pytest.raises(FileNotFoundError):
        builder.verify(root)
