import os
import subprocess
from pathlib import Path

import pytest

from proofpatch.docker_runner import DockerRunner
from proofpatch.mcp_client import MCPTools
from proofpatch.providers import DemoProvider
from proofpatch.workflow import Workflow

pytestmark = pytest.mark.skipif(
    os.environ.get("PROOFPATCH_DOCKER_TESTS") != "1",
    reason="Real Docker tests run explicitly in GitHub Actions",
)


def test_real_mcp_docker_repair(tmp_path):
    repo = Path(__file__).resolve().parents[1] / "examples" / "buggy_stats"
    result = Workflow(
        repo,
        tmp_path / "out",
        DemoProvider(),
        ["tests"],
        tool_factory=lambda work, out, timeout: MCPTools(work, out, timeout),
    ).run()
    assert result.status == "verified", result.reason
    assert len(result.runs[0].failures) == 5
    assert len(result.runs[-1].collected) == 9
    assert result.execution == "docker-via-mcp"
    assert result.provenance["runner_image_id"].startswith("sha256:")


def test_container_restrictions_and_secret_isolation(tmp_path, monkeypatch):
    root, output = tmp_path / "repo", tmp_path / "out"
    root.mkdir(mode=0o755)
    output.mkdir()
    (root / "test_security.py").write_text("""
import os
import socket
from pathlib import Path
import pytest

def test_controls():
    assert os.getuid() == 65534
    assert 'OPENAI_API_KEY' not in os.environ
    assert 'GITHUB_TOKEN' not in os.environ
    assert not Path('/var/run/docker.sock').exists()
    status = Path('/proc/self/status').read_text()
    assert 'NoNewPrivs:\\t1' in status
    assert 'CapEff:\\t0000000000000000' in status
    with pytest.raises(OSError):
        Path('/workspace/injected.py').write_text('bad')
    with pytest.raises(OSError):
        Path('/etc/injected').write_text('bad')
    with pytest.raises(OSError):
        socket.create_connection(('1.1.1.1', 80), timeout=1)
""")
    monkeypatch.setenv("OPENAI_API_KEY", "should-not-enter-container")
    monkeypatch.setenv("GITHUB_TOKEN", "should-not-enter-container")
    result = DockerRunner(root, output).run("baseline", ["test_security.py"])
    assert result.valid and result.exit_code == 0, (output / result.log).read_text()


def test_timeout_removes_container(tmp_path):
    root, output = tmp_path / "repo", tmp_path / "out"
    root.mkdir(mode=0o755)
    output.mkdir()
    (root / "test_hang.py").write_text("import time\ndef test_hang():\n    time.sleep(60)\n")
    result = DockerRunner(root, output, timeout=2).run("baseline", ["test_hang.py"])
    assert result.timed_out and not result.valid
    name = result.command[result.command.index("--name") + 1]
    listed = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name=^{name}$"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert not listed.stdout.strip()
