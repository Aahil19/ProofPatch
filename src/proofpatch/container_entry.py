"""Executed inside the container, never on the host. Stdlib-only evidence envelope."""

import json
import os
import subprocess
import sys
from pathlib import Path

env = dict(
    os.environ,
    PROOFPATCH_EVIDENCE="/tmp/evidence.json",
    PYTHONPATH="/support:/workspace:/workspace/src",
    PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
)
command = [
    sys.executable,
    "-B",
    "-m",
    "pytest",
    "-p",
    "pytest_capture",
    "-p",
    "no:cacheprovider",
    "-o",
    "addopts=",
    "--rootdir=.",
    "-q",
    *sys.argv[1:],
]
with open("/tmp/pytest.log", "w") as output:
    process = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
try:
    evidence = json.loads(Path("/tmp/evidence.json").read_text())
except (OSError, ValueError):
    evidence = {"collected": [], "outcomes": {}, "errors": ["Missing or malformed pytest evidence"]}
with open("/tmp/pytest.log") as log:
    text = log.read(1_000_000)
    if log.read(1):
        evidence["errors"].append("Test log exceeded 1 MB")
print(json.dumps({"exit_code": process.returncode, "log": text, **evidence}))
