import json

import pytest

from proofpatch.mcp_client import MCPTools
from proofpatch.mcp_server import IncidentTools


@pytest.fixture
def config(tmp_path):
    root, output = tmp_path / "repo", tmp_path / "out"
    root.mkdir()
    output.mkdir()
    (root / "app.py").write_text("x = 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_app.py").write_text("def test_a():\n    assert False\n")
    return {
        "workspace": str(root),
        "artifacts": str(output),
        "timeout": 2,
        "image": "proofpatch-runner:0.2",
        "scope": ["tests"],
        "ci_context": {"run_id": 123},
    }


def test_real_stdio_handshake_tools_reads_and_diff(config):
    with MCPTools(
        config["workspace"], config["artifacts"], 2, ci_context={"run_id": 123}
    ) as client:
        assert client.names == {"get_ci_logs", "read_file", "run_tests", "get_diff"}
        assert client.read_file("app.py") == "x = 1\n"
        assert client.get_ci_logs()["run_id"] == 123
        assert client.get_diff() == ""
        from pathlib import Path

        (Path(config["workspace"]) / "app.py").write_text("x = 2\n")
        assert "+x = 2" in client.get_diff()
        with pytest.raises(ValueError, match="rejected"):
            client.read_file("../secret.py")
    assert not client.thread.is_alive()
    assert len((Path(config["artifacts"]) / "mcp-tools.jsonl").read_text().splitlines()) == 5


@pytest.mark.parametrize(
    "path", ["../secret.py", "/etc/passwd", ".env", "missing.py", "tests/../../x.py"]
)
def test_restricted_file_reads(config, path):
    with pytest.raises(ValueError):
        IncidentTools(config).read_file(path)


@pytest.mark.parametrize("targets", [["../tests"], ["--help"], ["app.py"], ["/tmp/test.py"], []])
def test_test_scope_before_docker_execution(config, targets):
    with pytest.raises(ValueError):
        IncidentTools(config).run_tests("baseline", targets)


def test_no_arbitrary_command_labels(config):
    with pytest.raises(ValueError):
        IncidentTools(config).run_tests("../../overwrite", ["tests"])


def test_protected_diff(config):
    from pathlib import Path

    service = IncidentTools(config)
    (Path(config["workspace"]) / "tests" / "test_app.py").write_text("def test_a(): pass\n")
    with pytest.raises(ValueError, match="Protected"):
        service.get_diff()
    record = json.loads((Path(config["artifacts"]) / "mcp-tools.jsonl").read_text())
    assert record["status"] == "error"


def test_symlink_read_after_snapshot(config, tmp_path):
    from pathlib import Path

    service = IncidentTools(config)
    path = Path(config["workspace"]) / "app.py"
    path.unlink()
    path.symlink_to(tmp_path / "outside.py")
    with pytest.raises(ValueError, match="Symlink"):
        service.read_file("app.py")
