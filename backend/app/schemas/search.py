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


class SignalObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    extraction_run_id: UUID
    event_index: int
    signal_key: str
    subject_company: str
    summary: str
    stage: Literal["planned", "underway", "completed", "cancelled", "unclear"]
    locations: list[dict]
    timing: list[dict]
    related_companies: list[dict]
    missing_facts: list[str]
    created_at: datetime


class InvestigationResultResponse(BaseModel):
    result_rank: int
    title: str
    url: str
    content: str
    score: float | None
    published_date: str | None


class InvestigationQueryResponse(BaseModel):
    edge_id: str
    target_signal: str
    investigation_question: str
    query_text: str
    reason: str
    preferred_domains: list[str]
    request_id: str | None
    results: list[InvestigationResultResponse]


class ObservationInvestigationResponse(BaseModel):
    observation_id: UUID
    outcome: Literal["investigate", "stop"]
    rationale: str
    queries: list[InvestigationQueryResponse]


class RadarOpportunityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    search_job_id: UUID
    subject_company: str
    status: Literal["running", "completed", "failed"]
    report: dict | None
    created_at: datetime
    updated_at: datetime


class RadarOpportunityCreateResponse(RadarOpportunityResponse):
    created: bool
