#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_METADATA = {"name", "type", "from", "instantiation", "inherits", "include"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Ungültiges Profil: {path}")
    return value


def find_profile(machine_dir: Path, name: str) -> Path:
    direct = machine_dir / f"{name}.json"
    if direct.is_file():
        return direct
    matches = list(machine_dir.glob(f"**/{name}.json"))
    if len(matches) != 1:
        raise FileNotFoundError(f"Profil nicht eindeutig gefunden: {name}")
    return matches[0]


def resolve(machine_dir: Path, path: Path, seen: set[Path]) -> dict[str, Any]:
    path = path.resolve()
    if path in seen:
        raise ValueError(f"Zyklische Profilvererbung: {path.name}")
    seen.add(path)
    payload = load_json(path)
    merged: dict[str, Any] = {}

    parent = str(payload.get("inherits") or "").strip()
    if parent:
        merged.update(resolve(machine_dir, find_profile(machine_dir, parent), seen))

    for key, value in payload.items():
        if key not in {"inherits", "include"}:
            merged[key] = value

    includes = payload.get("include")
    if isinstance(includes, list):
        for include_name in includes:
            include_path = find_profile(machine_dir, str(include_name))
            include_payload = load_json(include_path)
            for key, value in include_payload.items():
                if key not in _METADATA:
                    merged[key] = value

    seen.remove(path)
    return merged


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: materialize-bambu-machine.py PROFILE_ROOT MACHINE_REL OUTPUT")
    profile_root = Path(sys.argv[1])
    machine_path = profile_root / sys.argv[2]
    output = Path(sys.argv[3])
    machine_dir = profile_root / "BBL" / "machine"
    resolved = resolve(machine_dir, machine_path, set())
    resolved.pop("inherits", None)
    resolved.pop("include", None)
    output.write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
