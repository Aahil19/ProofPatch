"""Read-only GitHub ingestion. Never execute repository install scripts or workflows."""

import io
import re
import stat
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx


@dataclass(frozen=True)
class RunURL:
    repository: str
    run_id: int
    attempt: int | None = None

    @classmethod
    def parse(cls, url: str):
        match = re.fullmatch(
            r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/actions/runs/([1-9][0-9]*)"
            r"(?:/attempts/([1-9][0-9]*))?/?",
            url,
        )
        if not match or any(x in {".", ".."} for x in match.groups()[:2]):
            raise ValueError("Expected https://github.com/OWNER/REPO/actions/runs/ID[/attempts/N]")
        owner, repo, run, attempt = match.groups()
        return cls(f"{owner}/{repo}", int(run), int(attempt) if attempt else None)


def extract_archive(data: bytes, destination: Path):
    """Extract bounded regular files only, stripping GitHub's archive root directory."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 5000 or sum(m.file_size for m in members) > 20_000_000:
            raise ValueError("Repository archive exceeds 5,000 entries / 20 MB")
        roots, seen, entries = set(), set(), []
        for member in members:
            path = PurePosixPath(member.filename)
            if path.is_absolute() or ".." in path.parts or "\\" in member.filename:
                raise ValueError("Unsafe archive path")
            roots.add(path.parts[0])
            mode = member.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise ValueError("Archive links and special files are unsupported")
            if member.is_dir():
                continue
            if len(path.parts) < 2 or member.file_size > 1_000_000:
                raise ValueError("Invalid archive layout or oversized file")
            relative = Path(*path.parts[1:])
            if relative in seen:
                raise ValueError("Duplicate archive path")
            seen.add(relative)
            entries.append((member, relative))
        if len(roots) != 1:
            raise ValueError("Expected one archive root")
        destination.mkdir(parents=True, exist_ok=False)
        for member, relative in entries:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))


class GitHub:
    def __init__(self, token: str | None = None, client=None, sleep=time.sleep):
        self.token = token
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.sleep = sleep

    def close(self):
        self.client.close()

    def download(self, path: str, limit: int = 5_000_000) -> bytes:
        url = "https://api.github.com" + path
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for _ in range(3):
            for retry in range(3):
                try:
                    with self.client.stream("GET", url, headers=headers) as response:
                        status = response.status_code
                        if status in (301, 302, 307, 308):
                            redirect = response.headers.get("location", "")
                            parsed = urlparse(redirect)
                            host = parsed.hostname or ""
                            if (
                                parsed.scheme != "https"
                                or parsed.username
                                or parsed.password
                                or parsed.port not in (None, 443)
                                or not (
                                    host in {"api.github.com", "codeload.github.com"}
                                    or host.endswith(
                                        (".blob.core.windows.net", ".actions.githubusercontent.com")
                                    )
                                )
                            ):
                                raise ValueError("GitHub returned an unsupported download redirect")
                            url = redirect
                            # Signed archive/log downloads never receive the API credential.
                            headers = {}
                            break
                        if status != 200:
                            if status in (429, 500, 502, 503, 504) and retry < 2:
                                self.sleep(2**retry)
                                continue
                            raise ValueError(
                                f"GitHub HTTP {status} for {path}; check read access, rate limits, and log retention"
                            )
                        chunks, size = [], 0
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > limit:
                                raise ValueError("GitHub response exceeds configured size limit")
                            chunks.append(chunk)
                        return b"".join(chunks)
                except httpx.TransportError:
                    if retry == 2:
                        raise ValueError("GitHub request failed after three attempts") from None
                    self.sleep(2**retry)
            else:
                raise ValueError("GitHub request failed after three attempts")
        raise ValueError("Too many GitHub redirects")

    def json(self, path):
        import json

        return json.loads(self.download(path))

    def incident(self, run: RunURL) -> dict:
        base = f"/repos/{run.repository}/actions/runs/{run.run_id}"
        current = self.json(base)
        attempt = run.attempt or current["run_attempt"]
        detail = self.json(f"{base}/attempts/{attempt}")
        if detail["status"] != "completed" or detail["conclusion"] != "failure":
            raise ValueError("Select a completed, failed workflow attempt")
        if detail["repository"]["full_name"].lower() != run.repository.lower():
            raise ValueError("Workflow repository mismatch")
        if detail["head_repository"]["full_name"].lower() != run.repository.lower():
            raise ValueError("Fork runs are not supported in Week 2")
        sha = detail["head_sha"]
        if not re.fullmatch(r"[a-fA-F0-9]{40}", sha):
            raise ValueError("Invalid GitHub commit SHA")
        jobs = []
        for page in range(1, 11):
            result = self.json(f"{base}/attempts/{attempt}/jobs?per_page=100&page={page}")
            jobs.extend(result["jobs"])
            if len(jobs) >= result["total_count"]:
                break
        else:
            raise ValueError("Too many workflow jobs")
        failed = [job for job in jobs if job["conclusion"] == "failure"]
        if not failed or len(failed) > 20:
            raise ValueError("Expected 1–20 failed jobs")
        logs = []
        for job in failed:
            text = self.download(
                f"/repos/{run.repository}/actions/jobs/{int(job['id'])}/logs"
            ).decode("utf-8", errors="replace")
            if self.token:
                text = text.replace(self.token, "[REDACTED]")
            logs.append({"job_id": job["id"], "name": job["name"], "text": text[-40_000:]})
        if sum(len(log["text"]) for log in logs) > 200_000:
            raise ValueError("Failed-job log context exceeds 200 KB")
        return {
            "repository": run.repository,
            "run_id": run.run_id,
            "run_attempt": attempt,
            "head_sha": sha,
            "run_url": f"https://github.com/{run.repository}/actions/runs/{run.run_id}/attempts/{attempt}",
            "workflow_path": detail.get("path"),
            "event": detail.get("event"),
            "logs": logs,
        }

    def checkout(self, incident: dict, destination: Path):
        data = self.download(
            f"/repos/{incident['repository']}/zipball/{incident['head_sha']}", 20_000_000
        )
        extract_archive(data, destination)


def failed_test_ids(incident: dict, subdir: str) -> set[str]:
    ids = set()
    prefix = subdir.strip("./") + "/" if subdir != "." else ""
    for log in incident["logs"]:
        for nodeid in re.findall(r"\bFAILED\s+([^\s]+\.py::[^\s]+)", log["text"]):
            if prefix and nodeid.startswith(prefix):
                nodeid = nodeid[len(prefix) :]
            ids.add(nodeid)
    return ids
