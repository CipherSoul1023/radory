import httpx
from pydantic import BaseModel

from app.core.config import get_settings


class TavilyNotConfigured(RuntimeError):
    pass


class TavilyResult(BaseModel):
    title: str
    url: str
    content: str = ""


class TavilyResponse(BaseModel):
    results: list[TavilyResult]


class TavilyClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else get_settings().tavily_api_key

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def search(self, query: str) -> TavilyResponse:
        if not self.configured:
            raise TavilyNotConfigured("TAVILY_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"query": query},
            )
            response.raise_for_status()
            return TavilyResponse.model_validate(response.json())
