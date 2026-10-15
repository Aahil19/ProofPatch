import pytest

from proofpatch.cli import main


@pytest.mark.parametrize(
    "args",
    [
        ["repo", "--provider", "demo"],
        ["repo", "--trusted-local"],
        ["repo", "--provider", "demo", "--trusted-local", "--tests", "../tests"],
        ["repo", "--provider", "demo", "--trusted-local", "--timeout", "0"],
    ],
)
def test_rejects_unsafe_or_incomplete_cli(args):
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
