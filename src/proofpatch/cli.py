import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

from proofpatch.providers import DemoProvider, OpenAIProvider
from proofpatch.workflow import Workflow


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="ProofPatch: reproduce, repair, and prove Python fixes"
    )
    parser.add_argument("repository", help="Local repository path or GitHub Actions run URL")
    parser.add_argument("--provider", choices=["openai", "demo"], default="openai")
    parser.add_argument("--model", help="Explicit OpenAI model ID for live runs")
    parser.add_argument(
        "--tests", nargs="+", default=["tests"], help="Relative pytest paths / node IDs"
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-attempts", type=int, choices=[1, 2], default=2)
    parser.add_argument("--max-calls", type=int, choices=range(1, 13), default=12)
    parser.add_argument("--execution", choices=["local", "docker"], default=None)
    parser.add_argument(
        "--image", default="proofpatch-runner:0.2", help="Prebuilt trusted Docker runner image"
    )
    parser.add_argument(
        "--subdir", default=".", help="Project directory within a GitHub repository"
    )
    parser.add_argument(
        "--trusted-local",
        action="store_true",
        help="Acknowledge execution of trusted repository code on this machine",
    )
    args = parser.parse_args(argv)
    is_url = args.repository.startswith("https://") or "://" in args.repository
    execution = args.execution or ("docker" if is_url else "local")
    if is_url and execution != "docker":
        parser.error("GitHub run investigations require Docker; local fallback is forbidden")
    if execution == "local" and not args.trusted_local:
        parser.error(
            "Week 1 executes code locally. Review the repository and pass --trusted-local."
        )
    if args.timeout <= 0 or args.timeout > 600:
        parser.error("--timeout must be greater than zero and at most 600 seconds")
    for target in args.tests:
        path = Path(target.split("::")[0])
        if target.startswith("-") or path.is_absolute() or ".." in path.parts:
            parser.error("--tests accepts only repository-relative paths or node IDs, not flags")
    args.tests = [
        Path(t.split("::")[0]).as_posix() + ("::" + t.split("::", 1)[1] if "::" in t else "")
        for t in args.tests
    ]
    if args.provider == "openai" and not args.model:
        parser.error("Specify --model for live mode")
    try:
        provider = (
            DemoProvider()
            if args.provider == "demo"
            else OpenAIProvider(args.model, args.max_calls)
        )
        output = (args.output or Path("artifacts") / uuid4().hex[:12]).resolve()
        if is_url:
            from proofpatch.ingest import investigate_run

            incident = investigate_run(
                args.repository,
                output,
                provider,
                args.tests,
                args.subdir,
                args.image,
                args.timeout,
                args.max_attempts,
                token=os.environ.get("GITHUB_TOKEN"),
            )
        else:
            from proofpatch.mcp_client import MCPTools

            factory = None
            if execution == "docker":
                factory = lambda work, out, timeout: MCPTools(
                    work, out, timeout, args.image, args.tests
                )
            incident = Workflow(
                Path(args.repository).resolve(),
                output,
                provider,
                args.tests,
                args.timeout,
                args.max_attempts,
                tool_factory=factory,
            ).run()
    except (ValueError, OSError) as error:
        print(f"ProofPatch configuration error: {error}", file=sys.stderr)
        return 2
    print(
        f"ProofPatch — {incident.status.upper()}\n{incident.reason}\nReport: {output / 'report.md'}"
    )
    return 0 if incident.status == "verified" else 1
