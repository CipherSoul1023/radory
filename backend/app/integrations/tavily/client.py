from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings


class TavilyError(RuntimeError):
    error_code = "tavily_error"
    retryable = False


class TavilyNotConfigured(TavilyError):
    error_code = "not_configured"


class TavilyTransportError(TavilyError):
    error_code = "transport_error"
    retryable = True


class TavilyRequestError(TavilyError):
    def __init__(self, message: str, *, status_code: int):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = status_code == 429 or status_code >= 500
        self.error_code = {
            400: "invalid_request",
            401: "authentication_failed",
            403: "forbidden",
            422: "validation_failed",
            429: "rate_limited",
            432: "usage_limit_exceeded",
            433: "payg_limit_exceeded",
        }.get(status_code, "provider_unavailable" if status_code >= 500 else "http_error")


class TavilyResponseError(TavilyError):
    error_code = "invalid_response"


class TavilyResult(BaseModel):
    provider_result_id: str | None = None
    title: str
    url: str
    content: str = ""
    score: float | None = None
    published_date: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class TavilyResponse(BaseModel):
    results: list[TavilyResult]
    request_id: str | None = None
    response_time_seconds: float | None = None
    usage: dict[str, Any] | None = None


class TavilyClient:
    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        http_client: httpx.Client | None = None,
        timeout_seconds: float | None = None,
    ):
        self.api_key = api_key if api_key is not None else get_settings().tavily_api_key
        self.http_client = http_client
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else get_settings().tavily_timeout_seconds
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def search(
        self,
        query: str,
        *,
        include_domains: tuple[str, ...] = (),
        include_domains_mode: Literal["prefer", "restrict"] = "prefer",
        max_results: int = 10,
        search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = "basic",
        include_raw_content: bool = False,
    ) -> TavilyResponse:
        if not self.configured:
            raise TavilyNotConfigured("TAVILY_API_KEY is not configured")
        payload: dict[str, Any] = {
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "topic": "general",
            "include_answer": False,
            "include_raw_content": include_raw_content,
            "include_usage": True,
        }
        if include_domains:
            payload["include_domains"] = list(include_domains)
            payload["include_domains_mode"] = include_domains_mode

        try:
            if self.http_client is None:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(
                        self.endpoint,
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json=payload,
                    )
            else:
                response = self.http_client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=self.timeout_seconds,
                )
        except httpx.RequestError as exc:
            raise TavilyTransportError("Tavily request failed") from exc

        if response.is_error:
            raise TavilyRequestError(
                f"Tavily returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            raw_response = response.json()
            raw_results = raw_response.get("results", [])
            results = [
                TavilyResult(
                    provider_result_id=result.get("id"),
                    title=result["title"],
                    url=result["url"],
                    content=result.get("content", ""),
                    score=result.get("score"),
                    published_date=result.get("published_date"),
                    raw_payload=result,
                )
                for result in raw_results
            ]
            response_time = raw_response.get("response_time")
            return TavilyResponse(
                results=results,
                request_id=raw_response.get("request_id"),
                response_time_seconds=float(response_time) if response_time is not None else None,
                usage=raw_response.get("usage"),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise TavilyResponseError("Tavily returned an invalid response") from exc
