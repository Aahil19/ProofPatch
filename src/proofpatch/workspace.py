import difflib
import hashlib
import os
from pathlib import Path

from proofpatch.models import Proposal

IGNORED = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "artifacts",
    "dist",
    "build",
}


def inventory(root: Path) -> dict[str, bytes]:
    files = {}
    total = 0
    for parent, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED and not d.startswith("."))
        for name in dirs + names:
            path = Path(parent) / name
            if path.is_symlink():
                raise ValueError(f"Symlinks are unsupported: {path.relative_to(root)}")
        for name in sorted(names):
            if name.startswith(".env") or name.endswith((".pyc", ".pem", ".key")):
                continue
            path = Path(parent) / name
            if path.stat().st_size > 1_000_000:
                raise ValueError(f"File too large: {path.relative_to(root)}")
            content = path.read_bytes()
            total += len(content)
            if total > 10_000_000 or len(files) >= 1000:
                raise ValueError("Repositories are limited to 1,000 files / 10 MB")
            files[path.relative_to(root).as_posix()] = content
    return files


def hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}


def writable(path: str, test_targets: list[str]) -> bool:
    p = Path(path)
    if p.is_absolute() or ".." in p.parts or p.suffix != ".py":
        return False
    if any(part.startswith(".") or part.lower() in {"tests", "test"} for part in p.parts):
        return False
    if p.name.startswith("test_") or p.name.endswith("_test.py"):
        return False
    if p.name in {"conftest.py", "setup.py", "sitecustomize.py", "usercustomize.py"}:
        return False
    return not any(
        path == t.split("::")[0] or path.startswith(t.split("::")[0] + "/") for t in test_targets
    )


def apply_proposal(
    root: Path, original: dict[str, bytes], proposal: Proposal, allowed: set[str]
) -> str:
    updated = {}
    for edit in proposal.edits:
        if edit.path not in allowed or edit.path not in original:
            raise ValueError(f"Protected or unknown file: {edit.path}")
        current = updated.get(edit.path, original[edit.path].decode("utf-8"))
        if current.count(edit.old) != 1:
            raise ValueError(f"Edit must match exactly once: {edit.path}")
        updated[edit.path] = current.replace(edit.old, edit.new, 1)
    diff = ""
    for name, content in updated.items():
        compile(content, name, "exec")
        diff += "".join(
            difflib.unified_diff(
                original[name].decode().splitlines(True),
                content.splitlines(True),
                fromfile=f"a/{name}",
                tofile=f"b/{name}",
            )
        )
    if not diff or len(diff.encode()) > 30_000:
        raise ValueError("Patch is empty or exceeds 30 KB")
    for name, content in updated.items():
        (root / name).write_text(content, encoding="utf-8")
    return diff


def restore(root: Path, original: dict[str, bytes]) -> None:
    for name, content in original.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
