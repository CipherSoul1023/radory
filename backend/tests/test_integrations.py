import json

import httpx
import pytest

from app.integrations.nebius.client import NebiusClient, NebiusNotConfigured
from app.integrations.r2.storage import R2NotConfigured, R2Storage
from app.integrations.tavily.client import (
    TavilyClient,
    TavilyNotConfigured,
    TavilyRequestError,
)


def test_tavily_missing_key(monkeypatch):
    client = TavilyClient(api_key="")
    assert not client.configured
    with pytest.raises(TavilyNotConfigured):
        client.search("unused")


def test_tavily_search_sends_supported_policy_and_preserves_raw_result():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "result-1",
                        "title": "Expansion",
                        "url": "https://example.com/expansion",
                        "content": "Expansion evidence",
                        "score": 0.9,
                        "provider_extension": "preserve me",
                    }
                ],
                "request_id": "request-1",
                "response_time": "1.2",
                "usage": {"credits": 1},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        response = TavilyClient(api_key="test-key", http_client=http_client).search(
            "Johannesburg expands operations",
            include_domains=("itweb.co.za",),
            include_domains_mode="prefer",
            search_depth="basic",
            max_results=10,
        )
    assert captured == {
        "query": "Johannesburg expands operations",
        "search_depth": "basic",
        "max_results": 10,
        "topic": "general",
        "include_answer": False,
        "include_raw_content": False,
        "include_usage": True,
        "include_domains": ["itweb.co.za"],
        "include_domains_mode": "prefer",
    }
    assert response.results[0].raw_payload["provider_extension"] == "preserve me"
    assert response.usage == {"credits": 1}


@pytest.mark.parametrize(("status_code", "retryable"), [(401, False), (429, True), (503, True)])
def test_tavily_http_errors_are_classified(status_code, retryable):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": {"error": "provider error"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        client = TavilyClient(api_key="test-key", http_client=http_client)
        with pytest.raises(TavilyRequestError) as captured:
            client.search("query")
    assert captured.value.retryable is retryable
    assert "test-key" not in str(captured.value)


@pytest.mark.asyncio
async def test_nebius_missing_key(monkeypatch):
    client = NebiusClient()
    monkeypatch.setattr(client.settings, "nebius_api_key", "")
    with pytest.raises(NebiusNotConfigured):
        await client.chat_completion([])


def test_r2_missing_key(monkeypatch):
    storage = R2Storage()
    monkeypatch.setattr(storage.settings, "r2_access_key_id", "")
    with pytest.raises(R2NotConfigured):
        storage.client()
