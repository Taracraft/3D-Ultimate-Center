"""Verify exact CI versions and active dependency closure without installation."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
from pathlib import Path
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version

ROOTS = frozenset(("aiohttp", "pytest", "pytest-asyncio", "setuptools", "wheel"))

def parse_pins(text, environment):
    if environment["python_version"] != "3.13" or environment["sys_platform"] not in {"linux", "win32"}:
        raise ValueError("unsupported_ci_environment")
    seen = set()
    pins = {}
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        req = Requirement(raw)
        name = canonicalize_name(req.name)
        specs = list(req.specifier)
        if (name in seen or req.url or req.extras or len(specs) != 1
                or specs[0].operator != "==" or "*" in specs[0].version
                or (req.marker and "extra" in str(req.marker))):
            raise ValueError("exact_unique_pins_required")
        seen.add(name)
        Version(specs[0].version)
        if not req.marker or req.marker.evaluate(dict(environment, extra="")):
            pins[name] = specs[0].version
    if not ROOTS <= pins.keys():
        raise ValueError("missing_ci_roots")
    return pins

def verify(text, installed, environment):
    pins = parse_pins(text, environment)
    for name, version in pins.items():
        package = installed.get(name)
        if package is None or Version(package["version"]) != Version(version):
            raise ValueError("installed_version_drift")
        for raw in package.get("requires", []):
            req = Requirement(raw)
            if req.marker and not req.marker.evaluate(dict(environment, extra="")):
                continue
            dep = canonicalize_name(req.name)
            if req.url or req.extras or dep not in pins or Version(pins[dep]) not in req.specifier:
                raise ValueError("active_dependency_not_closed")
    return {"verified": True, "packages": len(pins), "archive_hashes_verified": False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    try:
        installed = {
            canonicalize_name(d.metadata["Name"]): {"version": d.version, "requires": d.requires or []}
            for d in importlib.metadata.distributions()
        }
        result = verify((args.root / "requirements-ci.txt").read_text(encoding="utf-8"),
                        installed, default_environment())
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError):
        print(json.dumps({"verified": False, "error": "ci_dependency_contract_failed"}))
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
