import pytest

from app.integrations.nebius.client import NebiusClient, NebiusNotConfigured
from app.integrations.r2.storage import R2NotConfigured, R2Storage
from app.integrations.tavily.client import TavilyClient, TavilyNotConfigured


@pytest.mark.asyncio
async def test_tavily_missing_key(monkeypatch):
    client = TavilyClient(api_key="")
    assert not client.configured
    with pytest.raises(TavilyNotConfigured):
        await client.search("unused")


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
