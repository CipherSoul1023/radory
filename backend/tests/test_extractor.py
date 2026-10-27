import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest

from app.core.config import Settings
from app.integrations.nebius.client import NebiusClient
from app.search.evidence import EvidenceBlock, PreparedDocument, PreparedEvidence, fingerprint
from app.search.extraction_contract import MAX_INPUT_CHARACTERS
from app.search.extractor import SemanticExtractor


@pytest.fixture
def prepared_evidence():
    document = PreparedDocument(
        content_basis="raw_content",
        provider_published_at=None,
        blocks=(EvidenceBlock("body", "raw_content", "Acme manufactures office chairs."),),
    )
    return PreparedEvidence(
        workspace_id=uuid4(),
        document=document,
        content_hash="example-hash",
        input_fingerprint=fingerprint(document.semantic_payload()),
        sources=(),
    )


def completion(content=None, finish_reason="stop"):
    return {
        "id": "completion-example",
        "model": "test-nemotron",
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"content": content or '{"outcome":"assessed","events":[]}'},
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response = response if response is not None else completion()
        self.error = error
        self.calls = []

    async def chat_completion(self, messages, model=None, max_tokens=None):
        self.calls.append((messages, model, max_tokens))
        if self.error:
            raise self.error
        return self.response


@pytest.mark.asyncio
async def test_uses_explicit_model_and_only_semantic_input(prepared_evidence):
    client = FakeClient()
    result = await SemanticExtractor(client, model="test-nemotron").extract(prepared_evidence)
    assert result.status == "succeeded"
    assert result.output.events == []
    assert result.usage == {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
    messages, model, limit = client.calls[0]
    assert model == "test-nemotron" and limit == 4096
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "completed_move" in messages[0]["content"]
    assert "untrusted data" in messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert set(payload) == {
        "schema_version",
        "content_basis",
        "coverage",
        "provider_published_at",
        "blocks",
    }
    assert str(prepared_evidence.workspace_id) not in messages[1]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("response", "code"),
    [
        (completion("not json"), "invalid_output_schema"),
        (completion(finish_reason="length"), "incomplete_model_response"),
        ({"choices": []}, "invalid_provider_response"),
        ({"choices": [None]}, "invalid_provider_response"),
        (
            {"choices": [{"finish_reason": "stop", "message": {"tool_calls": ["search"]}}]},
            "unexpected_model_action",
        ),
    ],
)
async def test_bad_responses_fail_without_retry_or_silent_empty_output(
    prepared_evidence, response, code
):
    client = FakeClient(response)
    result = await SemanticExtractor(client, model="test-nemotron").extract(prepared_evidence)
    assert result.status == "failed" and result.error_code == code
    assert result.output is None and len(client.calls) == 1


@pytest.mark.asyncio
async def test_transport_errors_are_safe_and_not_automatically_retried(prepared_evidence):
    client = FakeClient(error=httpx.ConnectError("sensitive provider exception"))
    result = await SemanticExtractor(client, model="test-nemotron").extract(prepared_evidence)
    assert result.error_code == "provider_transport_error"
    assert "sensitive" not in repr(result)
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_oversized_input_never_calls_provider(prepared_evidence):
    document = replace(
        prepared_evidence.document,
        blocks=(EvidenceBlock("body", "raw_content", "x" * (MAX_INPUT_CHARACTERS + 1)),),
    )
    client = FakeClient()
    result = await SemanticExtractor(client, model="test-nemotron").extract(
        replace(prepared_evidence, document=document)
    )
    assert result.error_code == "invalid_or_oversized_input"
    assert result.model_calls == 0 and not client.calls


@pytest.mark.asyncio
async def test_cache_identity_varies_with_workspace_model_and_generation_limit(prepared_evidence):
    client = FakeClient()
    first = await SemanticExtractor(client, model="model-a").extract(prepared_evidence)
    tenant = await SemanticExtractor(client, model="model-a").extract(
        replace(prepared_evidence, workspace_id=uuid4())
    )
    model = await SemanticExtractor(client, model="model-b").extract(prepared_evidence)
    limit = await SemanticExtractor(client, model="model-a", max_output_tokens=100).extract(
        prepared_evidence
    )
    assert len({result.cache_key for result in (first, tenant, model, limit)}) == 4


@pytest.mark.asyncio
async def test_existing_nebius_transport_is_wired_using_mock_http(monkeypatch, prepared_evidence):
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        assert request.url == "https://provider.example/v1/chat/completions"
        return httpx.Response(200, json=completion())

    client = NebiusClient()
    client.settings = Settings(
        _env_file=None,
        nebius_api_key="test-placeholder",
        nebius_base_url="https://provider.example/v1",
        nemotron_model="unused-fallback",
    )
    original_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.integrations.nebius.client.httpx.AsyncClient",
        lambda **kwargs: original_async_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await SemanticExtractor(client, model="explicit-model", max_output_tokens=512).extract(
        prepared_evidence
    )
    assert result.status == "succeeded"
    assert captured["model"] == "explicit-model"
    assert captured["max_tokens"] == 512
    assert "response_format" not in captured  # No unverified provider-specific feature required.
