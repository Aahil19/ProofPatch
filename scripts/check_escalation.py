"""Prove that a green repository cannot be claimed as a repaired failure."""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix="proofpatch-green-") as temp:
    repository = Path(temp)
    (repository / "tests").mkdir()
    (repository / "tests" / "test_green.py").write_text(
        "def test_green():\n    assert 2 + 2 == 4\n"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "proofpatch",
            str(repository),
            "--provider",
            "demo",
            "--trusted-local",
            "--output",
            str(args.output),
        ],
        check=False,
    )
report = json.loads((args.output / "report.json").read_text())
assert result.returncode == 1
assert report["status"] == "escalated"
assert report["attempts"] == 0
assert "No valid failing test evidence" in report["reason"]
assert not (args.output / "verified.patch").exists()
print("Escalation checked: no reproduced failure means no verified repair claim.")
