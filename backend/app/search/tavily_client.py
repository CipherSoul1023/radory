from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.integrations.tavily.client import TavilyClient, TavilyResponse


class PlannedTavilyQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    query_text: str = Field(min_length=1)
    preferred_domains: tuple[str, ...] = ()
    include_domains_mode: Literal["prefer", "restrict"] = "prefer"
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "basic"
    max_results: int = Field(default=10, ge=1, le=20)
    include_raw_content: bool = False


class RadarTavilyClient:
    def __init__(self, transport: TavilyClient | None = None):
        self.transport = transport or TavilyClient()

    @property
    def configured(self) -> bool:
        return self.transport.configured

    def execute(self, query: PlannedTavilyQuery) -> TavilyResponse:
        return self.transport.search(
            query.query_text,
            include_domains=query.preferred_domains,
            include_domains_mode=query.include_domains_mode,
            search_depth=query.search_depth,
            max_results=query.max_results,
            include_raw_content=query.include_raw_content,
        )
