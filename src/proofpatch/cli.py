import argparse
import os
import sys
from pathlib import Path
from uuid import uuid4

from proofpatch.providers import DemoProvider, OpenAIProvider
from proofpatch.workflow import Workflow


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] in ("approve", "reject"):
        from proofpatch.approval import decide

        decision = argv[0]
        gate = argparse.ArgumentParser(description=f"{decision} a reviewed verified patch")
        gate.add_argument("output", type=Path)
        gate.add_argument("--actor", required=True, help="Human reviewer identity")
        gate.add_argument("--reason", default="", help="Required for rejection")
        review = gate.parse_args(argv[1:])
        try:
            incident = decide(review.output, review.actor, decision == "approve", review.reason)
        except (ValueError, OSError) as error:
            print(f"ProofPatch approval error: {error}", file=sys.stderr)
            return 2
        print(f"ProofPatch approval — {incident.approval['status'].upper()}")
        return 0
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
    parser.add_argument("--budget-usd", default="0.50", help="Maximum estimated live LLM USD")
    parser.add_argument("--input-price-per-million", help="Operator supplied input token price")
    parser.add_argument("--output-price-per-million", help="Operator supplied output token price")
    parser.add_argument("--deadline", type=float, default=600, help="Active incident seconds")
    parser.add_argument("--resume", action="store_true", help="Resume an interrupted checkpoint")
    parser.add_argument("--no-mlflow", action="store_true", help="Disable local MLflow spans")
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
            "Local mode executes repository code on this machine. Review it and pass --trusted-local."
        )
    if args.timeout <= 0 or args.timeout > 600:
        parser.error("--timeout must be greater than zero and at most 600 seconds")
    if args.deadline <= 0 or args.deadline > 3600:
        parser.error("--deadline must be greater than zero and at most 3600 seconds")
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
    if args.provider == "openai" and (
        args.input_price_per_million is None or args.output_price_per_million is None
    ):
        parser.error("Live mode requires both operator-supplied token prices for its budget")
    if args.resume and args.output is None:
        parser.error("--resume requires the original --output directory")
    try:
        provider = (
            DemoProvider()
            if args.provider == "demo"
            else OpenAIProvider(
                args.model,
                args.max_calls,
                budget_usd=args.budget_usd,
                input_rate=args.input_price_per_million,
                output_rate=args.output_price_per_million,
            )
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
                resume=args.resume,
                deadline=args.deadline,
                mlflow_enabled=not args.no_mlflow,
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
                deadline=args.deadline,
                mlflow_enabled=not args.no_mlflow,
            ).run(resume=args.resume)
    except (ValueError, OSError) as error:
        print(f"ProofPatch configuration error: {error}", file=sys.stderr)
        return 2
    print(
        f"ProofPatch — {incident.status.upper()}\n{incident.reason}\nReport: {output / 'report.md'}"
    )
    return 0 if incident.status == "verified" else 1
