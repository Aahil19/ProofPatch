"""Render artifact reports without broken relative links in the GitHub job summary."""

import os
import re
from pathlib import Path

summary = Path(os.environ["GITHUB_STEP_SUMMARY"])
with summary.open("a", encoding="utf-8") as stream:
    stream.write("Download this job's evidence bundle from the **Artifacts** section of this run.\n\n")
    for name in ("ci-demo", "ci-escalation"):
        report = Path("artifacts") / name / "report.md"
        if report.exists():
            # These filenames are relative to the downloaded artifact, not to a GitHub page.
            rendered = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"`\1`", report.read_text())
            stream.write(rendered + "\n\n")

