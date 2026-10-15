from types import SimpleNamespace

import pytest

from proofpatch.models import Diagnosis
from proofpatch.providers import OpenAIProvider


class FakeResponses:
    def parse(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            status="completed",
            usage=None,
            output_parsed=Diagnosis(summary="cause", suspect_files=[], evidence=[]),
        )


def test_live_provider_contract_and_call_limit():
    responses = FakeResponses()
    provider = OpenAIProvider(
        "configured-model", max_calls=1, client=SimpleNamespace(responses=responses)
    )
    assert provider.investigate({}).summary == "cause"
    assert responses.kwargs["store"] is False
    assert responses.kwargs["text_format"] is Diagnosis
    assert provider.usage[0]["model"] == "configured-model"
    with pytest.raises(ValueError, match="call limit"):
        provider.investigate({})


def test_refusal_escalates_to_caller():
    responses = SimpleNamespace(
        parse=lambda **kwargs: SimpleNamespace(status="completed", usage=None, output_parsed=None)
    )
    provider = OpenAIProvider("configured-model", client=SimpleNamespace(responses=responses))
    with pytest.raises(ValueError, match="unstructured"):
        provider.investigate({})
