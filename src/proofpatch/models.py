from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Diagnosis(StrictModel):
    summary: str
    suspect_files: list[str]
    evidence: list[str]


class Edit(StrictModel):
    path: str
    old: str = Field(min_length=1)
    new: str


class Proposal(StrictModel):
    rationale: str
    edits: list[Edit] = Field(min_length=1, max_length=8)


class TestRun(StrictModel):
    label: str
    command: list[str]
    exit_code: int
    duration_s: float
    outcomes: dict[str, Literal["passed", "failed", "skipped", "error"]]
    collected: list[str]
    errors: list[str]
    log: str
    evidence: str
    timed_out: bool = False

    @property
    def failures(self) -> list[str]:
        return sorted(k for k, v in self.outcomes.items() if v == "failed")

    @property
    def valid(self) -> bool:
        return (
            not self.timed_out
            and not self.errors
            and bool(self.collected)
            and len(self.collected) == len(set(self.collected))
            and set(self.collected) == set(self.outcomes)
            and "error" not in self.outcomes.values()
            and self.exit_code == (1 if self.failures else 0)
        )


class Incident(StrictModel):
    schema_version: int = 2
    status: Literal["running", "verified", "escalated"] = "running"
    reason: str = ""
    provider: str
    scope: list[str]
    attempts: int = 0
    diagnosis: Diagnosis | None = None
    runs: list[TestRun] = Field(default_factory=list)
    trace: list[dict] = Field(default_factory=list)
    usage: list[dict] = Field(default_factory=list)
    patch: str | None = None
    source_sha256: dict[str, str] = Field(default_factory=dict)
    provenance: dict = Field(default_factory=dict)
    execution: str = "trusted-local"
