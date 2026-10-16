"""Explicit human release gate for a technically verified patch."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from proofpatch.models import Incident


def decide(output: Path, actor: str, approve: bool, reason: str = "") -> Incident:
    if not actor.strip() or len(actor) > 100:
        raise ValueError("An operator name is required")
    report = output / "report.json"
    incident = Incident.model_validate_json(report.read_text())
    if incident.status != "verified" or incident.approval.get("status") != "pending":
        raise ValueError("Only a pending, technically verified patch can be decided")
    patch = (output / "verified.patch").read_bytes()
    digest = hashlib.sha256(patch).hexdigest()
    if digest != incident.approval.get("patch_sha256"):
        raise ValueError("Verified patch digest changed after review")
    if (output / "approved.patch").exists():
        raise ValueError("An approved patch already exists")
    if not approve and not reason.strip():
        raise ValueError("A rejection reason is required")
    event = {
        "decision": "approved" if approve else "rejected",
        "actor": actor.strip(),
        "reason": reason.strip(),
        "patch_sha256": digest,
        "at": datetime.now(UTC).isoformat(),
    }
    incident.approval.update(event)
    incident.approval["status"] = event["decision"]
    with (output / "approval-events.jsonl").open("a") as stream:
        stream.write(json.dumps(event) + "\n")
    report.write_text(incident.model_dump_json(indent=2) + "\n")
    markdown = output / "report.md"
    if markdown.exists():
        markdown.write_text(
            markdown.read_text().replace(
                "Human approval: pending; only a reviewed decision creates `approved.patch`.",
                f"Human approval: {event['decision']} by {event['actor']} at {event['at']}.",
            )
        )
    if approve:
        (output / "approved.patch").write_bytes(patch)
    return incident
