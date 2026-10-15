import json
import os
import subprocess
import sys
from pathlib import Path


def test_standalone_container_plugin_records_real_pytest_outcomes(tmp_path):
    (tmp_path / "test_sample.py").write_text("def test_sample():\n    assert False\n")
    evidence = tmp_path / "evidence.json"
    support = Path(__file__).resolve().parents[1] / "src" / "proofpatch"
    env = dict(
        os.environ,
        PYTHONPATH=str(support),
        PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
        PROOFPATCH_EVIDENCE=str(evidence),
        PYTHONDONTWRITEBYTECODE="1",
    )
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-p",
            "pytest_capture",
            "-p",
            "no:cacheprovider",
            "-q",
            "test_sample.py",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    data = json.loads(evidence.read_text())
    assert data["collected"] == ["test_sample.py::test_sample"]
    assert data["outcomes"] == {"test_sample.py::test_sample": "failed"}
