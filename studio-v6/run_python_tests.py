"""Reproducible Python preflight and pytest runner for V6."""

from __future__ import annotations

import compileall
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULT_DIRECTORY = ROOT / ".test-results"
RESULT_FILE = RESULT_DIRECTORY / "python-test-status.json"
PROGRESS_FILE = RESULT_DIRECTORY / "python-pytest-progress.log"
PYCACHE_ROOT = RESULT_DIRECTORY / "python-cache" / str(os.getpid())
sys.pycache_prefix = str(PYCACHE_ROOT)


def _print_header(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def _run_compileall() -> bool:
    _print_header("1. Python syntax preflight")
    excluded = re.compile(
        r"[\\/](?:\.git|\.runtime|\.venv|\.test-build|\.test-results|backups|dist|node_modules|__pycache__)[\\/]"
    )
    ok = compileall.compile_dir(
        ROOT,
        quiet=1,
        force=True,
        rx=excluded,
    )
    print("Syntax preflight:", "OK" if ok else "FAILED")
    return ok


def _run_import_preflight() -> tuple[bool, list[dict[str, str]]]:
    _print_header("2. Core import preflight")
    modules = (
        "core.database",
        "core.bootstrap",
        "core.mesh_parsers",
        "core.makerworld_import_service",
        "core.slice_service",
        "core.gcode_parser",
        "core.version",
        "api.application",
        "api.makerworld_application",
        "api.slicing_application",
        "api.http_server",
        "api.server",
    )
    ok = True
    results: list[dict[str, str]] = []
    for module_name in modules:
        try:
            module = importlib.import_module(module_name)
            module_file = Path(module.__file__).resolve()
            if not module_file.is_relative_to(ROOT.resolve()):
                raise ImportError(f"Module loaded outside project root: {module_file}")
            print(f"OK     {module_name}")
            results.append({"module": module_name, "status": "ok", "message": "", "path": str(module_file)})
        except Exception as error:
            ok = False
            message = f"{error.__class__.__name__}: {error}"
            print(f"FAILED {module_name}: {message}")
            results.append({"module": module_name, "status": "failed", "message": message})
    return ok, results


def _run_pytest() -> int:
    _print_header("3. Pytest")
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-vv",
        "-ra",
        "--tb=short",
        str(ROOT / "tests"),
    ]
    print("Command:", " ".join(command))
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with PROGRESS_FILE.open("w", encoding="utf-8", newline="\n") as progress:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env={
                **os.environ,
                "PYTHONPATH": str(ROOT),
                "PYTHONUNBUFFERED": "1",
                "PYTHONPYCACHEPREFIX": str(PYCACHE_ROOT),
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            progress.write(line)
            progress.flush()
        return process.wait()


def _write_result(
    *,
    syntax_ok: bool,
    imports_ok: bool,
    import_results: list[dict[str, str]],
    pytest_code: int,
) -> bool:
    success = syntax_ok and imports_ok and pytest_code == 0
    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    payload = {
        "success": success,
        "phase": "completed",
        "syntax_ok": syntax_ok,
        "imports_ok": imports_ok,
        "imports": import_results,
        "pytest_code": pytest_code,
        "python_version": sys.version,
        "python_executable": sys.executable,
        "project_root": str(ROOT),
    }
    RESULT_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("Result file:", RESULT_FILE)
    return success


def main() -> int:
    _print_header("Ultimate 3D Printing Studio V6 - Python Test Runner")
    print("Python:", sys.version.replace("\n", " "))
    print("Executable:", sys.executable)
    print("Project root:", ROOT)

    RESULT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text(
        json.dumps(
            {
                "success": False,
                "phase": "running",
                "python_version": sys.version,
                "python_executable": sys.executable,
                "project_root": str(ROOT),
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    syntax_ok = _run_compileall()
    imports_ok = False
    import_results: list[dict[str, str]] = []
    if syntax_ok:
        imports_ok, import_results = _run_import_preflight()
    pytest_code = _run_pytest() if syntax_ok and imports_ok else -1

    success = _write_result(
        syntax_ok=syntax_ok,
        imports_ok=imports_ok,
        import_results=import_results,
        pytest_code=pytest_code,
    )

    _print_header("Result")
    print("Syntax:", "OK" if syntax_ok else "FAILED")
    print("Imports:", "OK" if imports_ok else "FAILED")
    if pytest_code == -1:
        print("Pytest: SKIPPED because a preflight step failed")
    else:
        print("Pytest:", "OK" if pytest_code == 0 else f"FAILED with code {pytest_code}")
    print()
    print("Terminal bleibt offen.")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
