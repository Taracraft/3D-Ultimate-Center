from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("STUDIO_PROJECT_ROOT", str(Path(__file__).resolve().parent)))
RESULT_ROOT = PROJECT_ROOT / ".test-results"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
NODE_EXE = Path(r"C:\Program Files\nodejs\node.exe")

COMMANDS = {
    "python": (
        PYTHON_EXE,
        PROJECT_ROOT / "run_python_tests.py",
        RESULT_ROOT / "python-test-status.json",
    ),
    "frontend": (
        NODE_EXE,
        PROJECT_ROOT / "run_frontend_tests.mjs",
        RESULT_ROOT / "frontend-test-status.json",
    ),
}


def _load_status(path: Path) -> tuple[dict | None, str]:
    if not path.is_file():
        return None, f"Status file was not created: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as error:
        return None, f"Invalid status file: {error.__class__.__name__}: {error}"
    if not isinstance(payload, dict):
        return None, "Status file is not a JSON object"
    return payload, ""


def _environment(name: str) -> tuple[dict[str, str], str | None]:
    environment = os.environ.copy()
    if name != "python":
        return environment, None

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    workspace = RESULT_ROOT / "connector-runtime" / run_id
    pycache = workspace / "pycache"
    workspace.mkdir(parents=True, exist_ok=False)
    pycache.mkdir(parents=True, exist_ok=False)
    environment.update(
        {
            "TMP": str(workspace),
            "TEMP": str(workspace),
            "TMPDIR": str(workspace),
            "PYTHONPYCACHEPREFIX": str(pycache),
            "PYTEST_ADDOPTS": "-p no:cacheprovider",
        }
    )
    return environment, str(workspace)


def register_studio_gate(mcp) -> None:
    @mcp.tool()
    def run_studio_project_gate(gate: str = "combined") -> dict:
        """Runs the fixed Studio Python, frontend or combined project gate."""
        if gate not in {"python", "frontend", "combined"}:
            raise ValueError("gate must be python, frontend or combined")

        names = ("python", "frontend") if gate == "combined" else (gate,)
        runs = []

        for name in names:
            executable, runner, status_file = COMMANDS[name]
            status_file.unlink(missing_ok=True)
            environment, workspace = _environment(name)
            completed = subprocess.run(
                [str(executable), str(runner)],
                cwd=str(PROJECT_ROOT),
                env=environment,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=900,
                shell=False,
                check=False,
            )
            status, status_error = _load_status(status_file)
            reported_success = bool(status and status.get("success") is True)
            success = completed.returncode == 0 and reported_success and not status_error
            runs.append(
                {
                    "name": name,
                    "success": success,
                    "returncode": completed.returncode,
                    "stdout": completed.stdout[-200000:],
                    "stderr": completed.stderr[-200000:],
                    "status_file": str(status_file),
                    "status": status,
                    "status_error": status_error,
                    "workspace": workspace,
                }
            )

        return {
            "success": bool(runs) and all(item["success"] for item in runs),
            "gate": gate,
            "project_root": str(PROJECT_ROOT),
            "runs": runs,
            "fixed_commands": True,
            "status_validated": True,
            "connector_temp_isolated": True,
            "shell": False,
        }
