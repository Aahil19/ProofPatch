import json
import tempfile
from pathlib import Path

from proofpatch.github import GitHub, RunURL
from proofpatch.mcp_client import MCPTools
from proofpatch.mcp_server import relative_path
from proofpatch.models import Incident
from proofpatch.workflow import Workflow


def investigate_run(
    url,
    output,
    provider,
    targets,
    subdir=".",
    image="proofpatch-runner:0.2",
    timeout=60,
    max_attempts=2,
    token=None,
    github=None,
):
    run = RunURL.parse(url)
    relative_path(subdir)
    if output.exists():
        raise FileExistsError("Output directory already exists")
    api = github or GitHub(token)
    context = {}
    try:
        context = api.incident(run)
        context["subdir"] = subdir
        with tempfile.TemporaryDirectory(prefix="proofpatch-github-") as temp:
            checkout = Path(temp) / "checkout"
            api.checkout(context, checkout)
            repository = (checkout / subdir).resolve()
            if not repository.is_relative_to(checkout) or not repository.is_dir():
                raise ValueError("Selected repository subdirectory does not exist")
            factory = lambda work, out, seconds: MCPTools(
                work, out, seconds, image, targets, context
            )
            incident = Workflow(
                repository,
                output,
                provider,
                targets,
                timeout,
                max_attempts,
                tool_factory=factory,
                ci_context=context,
            ).run()
    except Exception as error:  # noqa: BLE001 - ingestion failures need a human-readable report
        output.mkdir(parents=True, exist_ok=True)
        incident = Incident(
            provider=provider.name,
            scope=targets,
            status="escalated",
            reason=f"GitHub ingestion: {type(error).__name__}: {error}",
            execution="docker-via-mcp",
            provenance={k: v for k, v in context.items() if k != "logs"},
        )
        (output / "report.json").write_text(incident.model_dump_json(indent=2))
        (output / "report.md").write_text(f"# ProofPatch — ESCALATED\n\n{incident.reason}\n")
    finally:
        api.close()
    (output / "github-incident.json").write_text(json.dumps(context, indent=2))
    return incident
