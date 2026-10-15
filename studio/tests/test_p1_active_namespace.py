"""Fail closed on active P1/V6 namespace residues in the public source scope."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "studio_source_fingerprint_for_p1_namespace",
    ROOT / "tools" / "studio_source_fingerprint.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FORBIDDEN = re.compile(
    r"ultimate_3d_studio_v6|ultimate-3d-studio-v6|3d_studio_v6|3d-studio-v6|"
    r"3D Studio V6|Ultimate3DStudioV6|api_v6_commands|\bV6\b",
    re.IGNORECASE,
)

# Historical release documentation and the exact self-referential P1
# regression fixtures are not active runtime namespaces.
HISTORICAL_AND_SELF_REFERENCE = frozenset({
    "AGENTS.md",
    "LIVE_WORKLOG.md",
    "CHANGELOG.md",
    "CHANGELOG-DE.md",
    "frontend-tests/storage-upgrade.test.ts",
    "tests/test_p1_active_namespace.py",
    "tests/test_source_fingerprint.py",
    "tools/studio_source_fingerprint.py",
})
ALLOWED_LEGACY_LINES = {
    "tests/test_studio_native_slicer_only.py": (
        "apply_v6_native_slicer_telemetry_20260811.mjs",
    ),
}


def test_active_public_scope_has_no_unapproved_v6_namespace_residuals() -> None:
    violations: list[str] = []
    for path in MODULE.source_paths(ROOT):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("docs/") or relative in HISTORICAL_AND_SELF_REFERENCE:
            continue
        if path.suffix.lower() not in {
            ".py", ".ts", ".mjs", ".js", ".sh", ".ps1", ".json",
            ".yaml", ".yml", ".toml", ".md", ".txt",
        }:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        allowed = ALLOWED_LEGACY_LINES.get(relative, ())
        for line_number, line in enumerate(text.splitlines(), 1):
            if not FORBIDDEN.search(line):
                continue
            if allowed and any(fragment in line for fragment in allowed):
                continue
            violations.append(f"{relative}:{line_number}:{line.strip()}")
    assert not violations, "Active P1 namespace residues:\n" + "\n".join(violations)
