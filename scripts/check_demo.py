"""Run the real CLI and assert the evidence, not just its exit status."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
subprocess.run(
    [
        sys.executable,
        "-m",
        "proofpatch",
        "examples/buggy_stats",
        "--provider",
        "demo",
        "--trusted-local",
        "--output",
        str(args.output),
    ],
    check=True,
)
report = json.loads((args.output / "report.json").read_text())
assert report["status"] == "verified"
assert list(report["runs"][0]["outcomes"].values()).count("failed") == 5
assert len(report["runs"][-1]["collected"]) == 9
assert set(report["runs"][-1]["outcomes"].values()) == {"passed"}
assert (args.output / "verified.patch").stat().st_size > 0
print("Evidence checked: 5 failures reproduced; 9 regression tests passed.")
