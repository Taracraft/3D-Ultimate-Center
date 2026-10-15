# Python dependencies for source CI

Source CI uses CPython 3.13. requirements-ci.txt pins runtime, test and editable-build dependencies to the inspected PC versions, including their active transitive dependencies: 18 packages on Windows and 17 on Linux. colorama is Windows-only.

Linux CI installs requirements-ci-linux.txt with --require-hashes, --only-binary=:all: and --no-deps. Each of its 17 entries permits exactly one downloaded and SHA-256-verified PyPI wheel for Linux x86_64 or a platform-independent wheel. Selected native wheels use CPython/abi3 and manylinux tags with a glibc baseline no newer than 2.28. Other architectures and unavailable artifacts fail; no source-build fallback is enabled.

The dependency contract checks installed versions and active dependency closure against requirements-ci.txt. The local project is then installed with --no-deps --no-build-isolation, and pip check validates the environment. setuptools and wheel are included in the hashed Linux pin set.

Run from the Studio source directory:

    python tools/studio_ci_dependencies.py --root .

## Verified artifact evidence

On 14 October 2026, all 17 wheels (5,397,901 bytes total) were fetched from files.pythonhosted.org using version-specific metadata from https://pypi.org/pypi/<package>/<version>/json. Downloaded sizes and SHA-256 values matched that metadata. Wheel names, package versions, compatibility tags and active Requires-Dist closure were checked without importing package code. Metadata is integrity evidence, not an independent signed provenance attestation.

An offline pip dry run selected all 17 verified wheels. A separate wrong-hash fixture was rejected. Neither check installed packages or ran Linux code. Raw metadata, wheel archives and private reports remain outside Git delivery.

## Remaining acceptance boundaries

A clean Linux install, actual ABI/runtime behavior, remote GitHub CI and complete source/profile license review remain open. Windows uses version pins only; the Linux artifact lock is not a Windows wheel lock. No engine, plugin, base image or OS-package lock is implied. Previously granted licenses and the narrower Slicer-Server license scope remain unchanged.

The dependency checker only reads metadata and files. It does not install packages, contact services, run an engine or operate a printer. The workflow has no deployment step.
