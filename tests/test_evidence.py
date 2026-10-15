import pytest

from proofpatch.models import Edit, Proposal
from proofpatch.models import TestRun as Evidence
from proofpatch.workflow import verification_errors
from proofpatch.workspace import apply_proposal, inventory, writable


def evidence(outcomes, code=0, collected=None):
    return Evidence(
        label="test",
        command=[],
        exit_code=code,
        duration_s=0,
        outcomes=outcomes,
        collected=collected or list(outcomes),
        errors=[],
        log="test.log",
        evidence="test.json",
    )


@pytest.mark.parametrize(
    "after",
    [
        {"broken": "passed"},
        {"broken": "skipped", "healthy": "passed"},
        {"broken": "passed", "healthy": "skipped"},
        {"broken": "passed", "healthy": "failed"},
        {"broken": "passed", "healthy": "error"},
        {"broken": "passed", "healthy": "passed", "extra": "passed"},
    ],
)
def test_no_false_verification(after):
    baseline = evidence({"broken": "failed", "healthy": "passed"}, 1)
    assert verification_errors(baseline, evidence({"broken": "passed"}), evidence(after))


def test_duplicate_ids_are_invalid():
    assert not evidence({"a": "passed"}, collected=["a", "a"]).valid


@pytest.mark.parametrize(
    "path",
    [
        "../outside.py",
        "/tmp/outside.py",
        "tests/test_app.py",
        "test_app.py",
        "app_test.py",
        "conftest.py",
        "setup.py",
        ".github/workflows/ci.py",
        "requirements.txt",
        "spec.py",
    ],
)
def test_protected_paths(path):
    assert not writable(path, ["spec.py"])


def test_source_path_allowed():
    assert writable("src/parser.py", ["tests"])


def test_patch_validation_is_atomic(tmp_path):
    original = {"app.py": b"x = 1\n", "other.py": b"y = 1\n"}
    for name, content in original.items():
        (tmp_path / name).write_bytes(content)
    proposal = Proposal(
        rationale="invalid",
        edits=[
            Edit(path="app.py", old="x = 1", new="x = 2"),
            Edit(path="other.py", old="y = 1", new="y = ("),
        ],
    )
    with pytest.raises(SyntaxError):
        apply_proposal(tmp_path, original, proposal, set(original))
    assert inventory(tmp_path) == original


def test_symlink_rejected(tmp_path):
    (tmp_path / "app.py").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="Symlinks"):
        inventory(tmp_path)
