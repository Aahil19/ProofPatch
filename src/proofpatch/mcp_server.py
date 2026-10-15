"""An incident-scoped stdio MCP server with exactly four tools and no shell tool."""

import argparse
import difflib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from proofpatch.docker_runner import DockerRunner
from proofpatch.workspace import inventory, writable


def relative_path(value: str) -> Path:
    path = Path(value)
    if (
        not value
        or value.startswith("-")
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in value
    ):
        raise ValueError("Only repository-relative paths are allowed")
    return path


class IncidentTools:
    def __init__(self, config: dict):
        self.root = Path(config["workspace"]).resolve()
        self.artifacts = Path(config["artifacts"]).resolve()
        self.original = inventory(self.root)
        self.config = config
        self.protected = set()
        self.labels = set()
        self.calls = 0
        self.runner = None

    def audit(self, name, arguments, operation):
        start = time.monotonic()
        record = {
            "tool": name,
            "arguments": arguments,
            "status": "ok",
            "started_at": datetime.now(UTC).isoformat(),
        }
        try:
            return operation()
        except Exception as error:
            record.update(status="error", error=f"{type(error).__name__}: {error}")
            raise
        finally:
            record["duration_s"] = round(time.monotonic() - start, 3)
            with (self.artifacts / "mcp-tools.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")

    def get_ci_logs(self) -> dict:
        return self.audit("get_ci_logs", {}, lambda: self.config.get("ci_context", {}))

    def read_file(self, path: str) -> dict:
        def read():
            relative_path(path)
            if path not in self.original or not path.endswith(".py"):
                raise ValueError("Only snapshotted Python files may be read")
            target = self.root / path
            if target.resolve() != target or target.is_symlink():
                raise ValueError("Symlink reads are forbidden")
            if target.stat().st_size > 100_000:
                raise ValueError("Source file exceeds 100 KB")
            return {"path": path, "content": target.read_text()}

        return self.audit("read_file", {"path": path}, read)

    def run_tests(self, label: str, targets: list[str]) -> dict:
        def run():
            if not re.fullmatch(
                r"baseline|reproduction|attempt-[12]-(?:focused|regression)", label
            ):
                raise ValueError("Unsupported test stage")
            if label in self.labels or self.calls >= 6:
                raise ValueError("Test stage already executed or six-run limit reached")
            if not targets or len(targets) > 200:
                raise ValueError("Expected 1–200 test selectors")
            for target in targets:
                file = target.split("::")[0]
                relative_path(file)
                if len(target) > 1000 or "\x00" in target:
                    raise ValueError("Invalid test selector")
                scopes = self.config["scope"]
                if not any(
                    target == scope
                    or target.startswith(scope + "::")
                    or ("::" in scope and target.startswith(scope + "["))
                    or (
                        "::" not in scope
                        and (scope == "." or file.startswith(scope.rstrip("/") + "/"))
                    )
                    for scope in scopes
                ):
                    raise ValueError("Test selector is outside the incident scope")
                resolved = (self.root / file).resolve()
                if not resolved.is_relative_to(self.root):
                    raise ValueError("Test path escapes workspace")
            self.labels.add(label)
            self.calls += 1
            if self.runner is None:
                self.runner = DockerRunner(
                    self.root, self.artifacts, self.config["timeout"], self.config["image"]
                )
            result = self.runner.run(label, targets)
            self.protected.update(node.split("::")[0] for node in result.collected)
            return {"run": result.model_dump(), "image_id": self.runner.image}

        return self.audit("run_tests", {"label": label, "targets": targets}, run)

    def get_diff(self) -> dict:
        def diff():
            current = inventory(self.root)
            if current.keys() != self.original.keys():
                raise ValueError("Added or removed repository files are not allowed")
            patch = ""
            for name in sorted(current):
                if current[name] == self.original[name]:
                    continue
                if name in self.protected or not writable(name, self.config["scope"]):
                    raise ValueError("Protected file changed")
                patch += "".join(
                    difflib.unified_diff(
                        self.original[name].decode().splitlines(True),
                        current[name].decode().splitlines(True),
                        fromfile=f"a/{name}",
                        tofile=f"b/{name}",
                    )
                )
            if len(patch.encode()) > 30_000:
                raise ValueError("Diff exceeds 30 KB")
            return {"diff": patch}

        return self.audit("get_diff", {}, diff)


def make_server(config: dict):
    tools = IncidentTools(config)
    server = FastMCP("ProofPatch incident tools")

    @server.tool(structured_output=True)
    def get_ci_logs() -> dict[str, Any]:
        """Read the fixed GitHub incident context and failed-job logs."""
        return tools.get_ci_logs()

    @server.tool(structured_output=True)
    def read_file(path: str) -> dict[str, Any]:
        """Read a bounded Python file from this incident's repository snapshot."""
        return tools.read_file(path)

    @server.tool(structured_output=True)
    def run_tests(label: str, targets: list[str]) -> dict[str, Any]:
        """Run incident-scoped pytest selectors in a restricted disposable Docker container."""
        return tools.run_tests(label, targets)

    @server.tool(structured_output=True)
    def get_diff() -> dict[str, Any]:
        """Read a bounded source diff against the original snapshot; reject protected edits."""
        return tools.get_diff()

    return server


def main():
    parser = argparse.ArgumentParser(description="Restricted incident MCP server (stdio only)")
    parser.add_argument(
        "--config", type=Path, required=True, help="Operator-owned incident configuration"
    )
    args = parser.parse_args()
    make_server(json.loads(args.config.read_text())).run(transport="stdio")


if __name__ == "__main__":
    main()
