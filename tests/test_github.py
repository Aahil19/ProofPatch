import io
import stat
import zipfile

import httpx
import pytest

from proofpatch.github import GitHub, RunURL, extract_archive, failed_test_ids


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/u/r/actions/runs/1",
        "https://evil.com/u/r/actions/runs/1",
        "https://github.com/u/r/actions/runs/1?url=evil",
        "https://github.com/u/r/actions/runs/1/jobs/2",
        "https://github.com/../r/actions/runs/1",
        "https://github.com/u/r/actions/runs/0",
    ],
)
def test_rejects_untrusted_run_urls(url):
    with pytest.raises(ValueError):
        RunURL.parse(url)


def test_pins_requested_attempt():
    run = RunURL.parse("https://github.com/u/r/actions/runs/123/attempts/2")
    assert (run.repository, run.run_id, run.attempt) == ("u/r", 123, 2)


def zip_bytes(name="root/app.py", mode=0):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        entry = zipfile.ZipInfo(name)
        entry.external_attr = mode << 16
        archive.writestr(entry, "x = 1\n")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "name,mode",
    [
        ("root/../../escape.py", 0),
        ("/root/app.py", 0),
        ("root/link.py", stat.S_IFLNK | 0o777),
        ("root\\escape.py", 0),
    ],
)
def test_archive_traversal_and_symlinks_rejected(tmp_path, name, mode):
    with pytest.raises(ValueError):
        extract_archive(zip_bytes(name, mode), tmp_path / "repo")
    assert not (tmp_path / "repo").exists()


def test_archive_regular_file(tmp_path):
    extract_archive(zip_bytes(), tmp_path / "repo")
    assert (tmp_path / "repo" / "app.py").read_text() == "x = 1\n"


def test_download_redirect_does_not_forward_credential():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.host == "api.github.com":
            return httpx.Response(
                302, headers={"location": "https://codeload.github.com/u/r/zip/sha"}
            )
        return httpx.Response(200, content=b"zip")

    api = GitHub("secret", httpx.Client(transport=httpx.MockTransport(handler)))
    assert api.download("/repos/u/r/zipball/sha") == b"zip"
    assert requests[0].headers["authorization"] == "Bearer secret"
    assert "authorization" not in requests[1].headers


def test_untrusted_redirect_rejected():
    api = GitHub(
        "secret",
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(302, headers={"location": "https://evil.com"})
            )
        ),
    )
    with pytest.raises(ValueError, match="redirect"):
        api.download("/test")


@pytest.mark.parametrize("status", [403, 404, 410, 429])
def test_api_failure_is_explicit(status):
    api = GitHub(
        client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status)))
    )
    with pytest.raises(ValueError, match=str(status)):
        api.download("/test")


def test_failed_job_pagination_attempt_and_exact_commit(tmp_path):
    seen = []
    sha = "a" * 40

    def handler(request):
        path = request.url.path
        seen.append(str(request.url))
        if path.endswith("/runs/123"):
            return httpx.Response(200, json={"run_attempt": 3})
        if path.endswith("/attempts/2"):
            return httpx.Response(
                200,
                json={
                    "status": "completed",
                    "conclusion": "failure",
                    "repository": {"full_name": "u/r"},
                    "head_repository": {"full_name": "u/r"},
                    "head_sha": sha,
                },
            )
        if path.endswith("/jobs"):
            page = request.url.params["page"]
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "jobs": [
                        {
                            "id": int(page),
                            "name": "pytest",
                            "conclusion": "failure" if page == "2" else "success",
                        }
                    ],
                },
            )
        if path.endswith("/jobs/2/logs"):
            return httpx.Response(200, text="FAILED tests/test_app.py::test_value - token-secret")
        if path.endswith("/zipball/" + sha):
            return httpx.Response(200, content=zip_bytes())
        raise AssertionError(path)

    api = GitHub("token-secret", httpx.Client(transport=httpx.MockTransport(handler)))
    context = api.incident(RunURL("u/r", 123, 2))
    assert context["run_attempt"] == 2
    assert context["head_sha"] == sha
    assert "token-secret" not in context["logs"][0]["text"]
    api.checkout(context, tmp_path / "repo")
    assert any("page=2" in url for url in seen)
    assert failed_test_ids(context, ".") == {"tests/test_app.py::test_value"}


def test_failure_ids_relative_to_subproject():
    context = {"logs": [{"text": "FAILED examples/x/tests/test_a.py::test_a - assert\n"}]}
    assert failed_test_ids(context, "examples/x") == {"tests/test_a.py::test_a"}
