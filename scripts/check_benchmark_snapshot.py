#!/usr/bin/env python3
"""Validate benchmark outcomes while ignoring machine-dependent timing fields."""

import json
import sys
from pathlib import Path


def signature(path: Path) -> dict:
    data = json.loads(path.read_text())
    return {
        "scenarios": data["summary"]["scenarios"],
        "projects": data["summary"]["projects"],
        "supervisor": {
            key: data["summary"]["supervisor"][key]
            for key in ("verified", "escalated", "verified_rate", "llm_cost_usd")
        },
        "single_agent": {
            key: data["summary"]["single_agent"][key]
            for key in ("verified", "escalated", "verified_rate", "llm_cost_usd")
        },
        "reproduction_coverage": data["summary"]["reproduction_coverage"],
        "trace_coverage": data["summary"]["trace_coverage"],
        "false_verified": data["summary"]["false_verified"],
        "cases": [
            (
                case["id"],
                case["supervisor"]["status"],
                case["supervisor"]["attempts"],
                case["single_agent"]["status"],
            )
            for case in data["cases"]
        ],
    }


expected, actual = map(Path, sys.argv[1:3])
if signature(expected) != signature(actual):
    raise SystemExit("Benchmark outcome drifted from the committed snapshot")
print("Benchmark outcome matches the committed 30-case snapshot")
