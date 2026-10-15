import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from proofpatch.models import TestRun


class LocalRunner:
    """Trusted code only: a subprocess is NOT a security sandbox."""

    def __init__(self, workspace: Path, artifacts: Path, timeout: float = 60):
        self.workspace, self.artifacts, self.timeout = workspace, artifacts, timeout

    def run(self, label: str, targets: list[str]) -> TestRun:
        evidence = self.artifacts / f"{label}.json"
        log = self.artifacts / f"{label}.log"
        # Do not inherit credentials, pytest options, or model tracing settings.
        env = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "TMPDIR") if k in os.environ}
        env.update(
            PYTHONPATH=os.pathsep.join(
                [
                    str(Path(__file__).resolve().parents[1]),
                    str(self.workspace),
                    str(self.workspace / "src"),
                ]
            ),
            PYTEST_DISABLE_PLUGIN_AUTOLOAD="1",
            PYTHONDONTWRITEBYTECODE="1",
            PROOFPATCH_EVIDENCE=str(evidence),
        )
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-p",
            "proofpatch.pytest_capture",
            "-p",
            "no:cacheprovider",
            "-o",
            "addopts=",
            "--rootdir=.",
            "-q",
            *targets,
        ]
        start = time.monotonic()
        timed_out = False
        with log.open("w", encoding="utf-8") as output:
            process = subprocess.Popen(
                command,
                cwd=self.workspace,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                code = process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
        data = {"outcomes": {}, "collected": [], "errors": []}
        try:
            data = json.loads(evidence.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data["errors"].append("Missing or malformed pytest evidence")
        return TestRun(
            label=label,
            command=command,
            exit_code=code,
            duration_s=round(time.monotonic() - start, 3),
            log=log.name,
            evidence=evidence.name,
            timed_out=timed_out,
            **data,
        )
