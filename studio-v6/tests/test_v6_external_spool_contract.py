from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "deploy/homeassistant/custom_components/ultimate_3d_studio_v6"
FRONTEND = ROOT / "frontend"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def test_external_spool_is_an_explicit_single_material_slice_source() -> None:
    source = _text(COMPONENT / "slicer_plate_views_v2.py")
    assert 'source == "external_spool"' in source
    assert 'len(filaments) != 1' in source
    assert 'any(value != 1 for value in assignments.values())' in source
    assert 'purge["enabled"] = False' in source
    assert '"source": "authoritative_external_spool_runtime"' in source
    assert '"use_ams": False' in source


def test_direct_print_uses_only_the_server_resolved_source() -> None:
    source = _text(COMPONENT / "direct_print_views.py")
    assert '"use_ams": resolved.use_ams' in source
    assert '"ams_mapping": list(resolved.mapping)' in source
    assert 'if resolved.use_ams and not bool(ams.get("available"))' in source
    assert '"external_spool_fallback": False' in source


def test_bambu_command_keeps_external_spool_and_ams_distinct() -> None:
    source = _text(COMPONENT / "bambu_direct_print.py")
    assert 'if use_ams:' in source
    assert '"use_ams": bool(use_ams)' in source
    assert '"ams_mapping": mapping' in source


def test_plate_source_and_external_profile_are_persisted() -> None:
    source = _text(FRONTEND / "studio-mega-workspace-v2.ts")
    persistence = _text(FRONTEND / "studio-persistence.ts")
    assert 'materialSource: "ams" | "external_spool"' in source
    assert 'externalFilamentProfileId: string' in source
    assert 'source: "external_spool"' in source
    assert 'purge_tower: { enabled: false }' in source
    assert 'materialSource?: "ams" | "external_spool"' in persistence
    assert 'externalFilamentProfileId?: string' in persistence

