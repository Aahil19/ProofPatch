import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from proofpatch.models import TestRun


class DockerRunner:
    def __init__(self, workspace: Path, artifacts: Path, timeout=60, image="proofpatch-runner:0.2"):
        self.workspace, self.artifacts, self.timeout = workspace, artifacts, timeout
        if not shutil.which("docker"):
            raise ValueError(
                "Docker is required; no host-execution fallback. Build docker/Dockerfile first."
            )
        inspected = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        self.image = inspected.stdout.strip()
        if inspected.returncode or not re.fullmatch(r"sha256:[a-f0-9]{64}", self.image):
            raise ValueError("Docker image is unavailable; build the trusted runner image first")

    def command(self, name, targets):
        return [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--user",
            "65534:65534",
            "--pids-limit",
            "128",
            "--memory",
            "512m",
            "--memory-swap",
            "512m",
            "--cpus",
            "1",
            "--ulimit",
            "nofile=256:256",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=64m,mode=1777",
            "--workdir",
            "/workspace",
            "--mount",
            f"type=bind,source={self.workspace},target=/workspace,readonly",
            "--mount",
            f"type=bind,source={Path(__file__).parent.resolve()},target=/support,readonly",
            "--entrypoint",
            "python",
            self.image,
            "-I",
            "/support/container_entry.py",
            *targets,
        ]

    def run(self, label, targets) -> TestRun:
        name = "proofpatch-" + uuid4().hex
        command = self.command(name, targets)
        start, timed_out = time.monotonic(), False
        raw = self.artifacts / f"{label}-container.log"
        data = {"exit_code": -1, "log": "", "collected": [], "outcomes": {}, "errors": []}
        try:
            with raw.open("w") as stream:
                process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
                try:
                    code = process.wait(timeout=self.timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    code = -1
                    subprocess.run(
                        ["docker", "rm", "-f", name], capture_output=True, timeout=15, check=False
                    )
                    process.kill()
                    process.wait(timeout=5)
            if not timed_out and code == 0 and raw.stat().st_size <= 2_000_000:
                data = json.loads(raw.read_text())
            else:
                data["errors"].append("Container timed out or failed; inspect container log")
        finally:
            subprocess.run(
                ["docker", "rm", "-f", name], capture_output=True, timeout=15, check=False
            )
        log = self.artifacts / f"{label}.log"
        log.write_text(data.pop("log"))
        evidence = self.artifacts / f"{label}.json"
        evidence.write_text(json.dumps(data, indent=2))
        return TestRun(
            label=label,
            command=command,
            duration_s=round(time.monotonic() - start, 3),
            log=log.name,
            evidence=evidence.name,
            timed_out=timed_out,
            **data,
        )
