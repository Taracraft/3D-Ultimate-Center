"""Run the isolated production-controller contracts and retain source-bound evidence."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def test_viewer_and_makerworld_modal_contracts():
    root = Path(__file__).resolve().parents[1]
    node = shutil.which("node") or shutil.which("node.exe")
    assert node, "Node is required for the existing frontend and this controller contract."
    paths = ["frontend/slicer-toolpath-viewer.ts", "frontend/makerworld-detail-dialog-studio.ts",
             "frontend/toolpath-material-colors.ts", "frontend-tests/viewer-modal-contract.test.mjs"]
    def hashes():
        return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in paths}
    before = hashes()
    started = datetime.now().astimezone().isoformat()
    result = subprocess.run(
        [node, "--test", "--test-reporter=tap", str(root / paths[-1])],
        cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
    )
    after = hashes()
    counts = {key: int(value) for key, value in re.findall(
        r"^# (tests|pass|fail|skipped) (\d+)$", result.stdout, re.MULTILINE)}
    passed = result.returncode == 0 and counts.get("tests", 0) > 0 and counts.get("fail") == 0 and counts.get("skipped") == 0
    evidence = {"started_at": started, "completed_at": datetime.now().astimezone().isoformat(),
                "success": passed and before == after, "returncode": result.returncode,
                "counts": counts, "source_sha256_before": before, "source_sha256_after": after,
                "sources_unchanged": before == after, "browser_acceptance": False,
                "stdout": result.stdout, "stderr": result.stderr}
    target = root / ".test-results" / "viewer-modal-node-contract.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    assert before == after, "Source changed during controller tests; rerun on a stable snapshot."
    assert passed, result.stdout + result.stderr
