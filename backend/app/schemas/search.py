from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SearchQuerySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    signal_key: str
    query_rank: int
    query_text: str
    status: Literal["pending", "running", "succeeded", "failed"]
    attempt_count: int
    last_error_code: str | None
    last_error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class SearchJobResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    initiated_by_user_id: UUID | None
    brokerage_profile_id: UUID | None
    status: Literal["pending", "running", "completed", "partial_failed", "failed"]
    country: str
    market: str
    configured_submarkets: list[str]
    resolved_submarket: str | None
    brokerage_profile_updated_at: datetime
    search_context_version: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    total_queries: int
    pending_queries: int
    running_queries: int
    succeeded_queries: int
    failed_queries: int
    queries: list[SearchQuerySummary]


class SearchJobCreateResponse(SearchJobResponse):
    created: bool
