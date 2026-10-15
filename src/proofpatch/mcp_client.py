"""Synchronous graph adapter backed by a real, persistent MCP stdio session."""

import asyncio
import json
import os
import sys
import threading
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from proofpatch.models import TestRun


class MCPTools:
    def __init__(
        self,
        workspace,
        artifacts,
        timeout,
        image="proofpatch-runner:0.2",
        scope=None,
        ci_context=None,
    ):
        self.config = {
            "workspace": str(workspace),
            "artifacts": str(artifacts),
            "timeout": timeout,
            "image": image,
            "scope": scope or ["tests"],
            "ci_context": ci_context or {},
        }
        self.artifacts = Path(artifacts)
        self.timeout = timeout + 45
        self.ready = threading.Event()
        self.error = None
        self.image = None

    async def _serve(self):
        self.loop = asyncio.get_running_loop()
        self.stop = asyncio.Event()
        config = self.artifacts / "mcp-config.json"
        config.write_text(json.dumps(self.config))
        # SDK inherits a small default environment. Explicitly omit GitHub/OpenAI credentials.
        env = {
            key: os.environ[key]
            for key in ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONTEXT")
            if key in os.environ
        }
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "proofpatch.mcp_server", "--config", str(config)],
            env=env,
        )
        try:
            with (self.artifacts / "mcp-server.log").open("w") as errors:
                async with stdio_client(params, errlog=errors) as (read, write):  # noqa: SIM117
                    async with ClientSession(read, write) as session:
                        self.session = session
                        async with asyncio.timeout(15):
                            await session.initialize()
                            self.names = {tool.name for tool in (await session.list_tools()).tools}
                        if self.names != {"get_ci_logs", "read_file", "run_tests", "get_diff"}:
                            raise ValueError("Unexpected MCP tool surface")
                        self.ready.set()
                        await self.stop.wait()
        except Exception as error:  # noqa: BLE001 - surface server startup/transport errors to graph
            self.error = error
            self.ready.set()

    def __enter__(self):
        self.thread = threading.Thread(target=lambda: asyncio.run(self._serve()), daemon=True)
        self.thread.start()
        if not self.ready.wait(20):
            if hasattr(self, "loop"):
                self.loop.call_soon_threadsafe(self.stop.set)
            raise TimeoutError("MCP server did not initialize within 20 seconds")
        if self.error:
            raise RuntimeError(f"MCP startup failed: {self.error}")
        return self

    def __exit__(self, *args):
        if self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.stop.set)
            self.thread.join(timeout=20)
        if self.thread.is_alive():
            raise TimeoutError("MCP server did not shut down cleanly")

    def call(self, name, arguments=None):
        if self.error or not self.thread.is_alive():
            raise RuntimeError("MCP server is unavailable")
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(name, arguments or {}), self.loop
        )
        try:
            result = future.result(timeout=self.timeout)
        except TimeoutError:
            future.cancel()
            raise TimeoutError(f"MCP tool {name} timed out") from None
        if result.isError:
            raise ValueError(
                "MCP tool rejected request: "
                + " ".join(item.text for item in result.content if hasattr(item, "text"))
            )
        if result.structuredContent is None:
            raise ValueError("MCP tool returned no structured result")
        return result.structuredContent

    def run(self, label, targets):
        result = self.call("run_tests", {"label": label, "targets": targets})
        self.image = result["image_id"]
        return TestRun.model_validate(result["run"])

    def read_file(self, path):
        return self.call("read_file", {"path": path})["content"]

    def get_ci_logs(self):
        return self.call("get_ci_logs")

    def get_diff(self):
        return self.call("get_diff")["diff"]
