#!/usr/bin/env python3
"""Validate generated Bambu G-code against the selected build-plate profile."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_plate_contract import validate_generated_bed_temperature


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"Ungültige JSON-Datei: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--process", required=True, type=Path)
    parser.add_argument("--gcode", required=True, type=Path)
    args = parser.parse_args()

    job = _json(args.job)
    overrides = job.get("process_overrides")
    if not isinstance(overrides, dict):
        overrides = {}
    bed_type = str(overrides.get("bambu_bed_type") or "").strip()
    if not bed_type:
        print(json.dumps({"validated": False, "reason": "no_bed_type_contract"}))
        return
    process = _json(args.process)
    result = validate_generated_bed_temperature(
        args.gcode.read_bytes(),
        process,
        bed_type,
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()