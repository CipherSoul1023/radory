from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import current_workspace_admin, current_workspace_context
from app.database.session import get_db_session
from app.schemas import (
    InvestigationQueryResponse,
    InvestigationResultResponse,
    ObservationInvestigationResponse,
    RadarOpportunityCreateResponse,
    RadarOpportunityResponse,
    SearchJobCreateResponse,
    SearchJobResponse,
    SearchQuerySummary,
    SignalObservationResponse,
)
from app.search.engine import (
    ActiveSearchJobExists,
    BrokerageProfileRequired,
    SearchJobNotFound,
    SearchQueryNotRetryable,
    create_search_job,
    load_search_job,
    query_status_counts,
    retry_failed_query,
)
from app.search.extraction_engine import list_signal_observations
from app.search.investigation import (
    InvestigationDecisionFailed,
    InvestigationNotConfigured,
    InvestigationObservationNotFound,
    InvestigationSearchFailed,
    investigate_observation,
)
from app.search.opportunity_engine import (
    OpportunityAlreadyRunning,
    OpportunityBuildFailed,
    OpportunityNotConfigured,
    OpportunityNotFound,
    build_radar_opportunity,
    list_radar_opportunities,
)
from app.search.pipeline import opportunity_status_counts
from app.search.tavily_client import RadarTavilyClient
from app.services.workspace_context import ResolvedWorkspaceContext
from app.tasks.radar_search import dispatch_search_queries

router = APIRouter(prefix="/api/radar", tags=["radar search"])


@router.get("/opportunities", response_model=list[RadarOpportunityResponse])
def get_radar_opportunities(
    response: Response,
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_context)],
    db: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[RadarOpportunityResponse]:
    response.headers["Cache-Control"] = "no-store"
    return [
        RadarOpportunityResponse.model_validate(item)
        for item in list_radar_opportunities(
            db,
            workspace_id=context.workspace.id,
            limit=limit,
        )
    ]


@router.post(
    "/opportunities/from-observation/{observation_id}",
    response_model=RadarOpportunityCreateResponse,
)
async def create_radar_opportunity(
    observation_id: UUID,
    response: Response,
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_admin)],
    db: Annotated[Session, Depends(get_db_session)],
) -> RadarOpportunityCreateResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        opportunity, created = await build_radar_opportunity(
            db,
            workspace_id=context.workspace.id,
            observation_id=observation_id,
        )
    except OpportunityNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OpportunityAlreadyRunning as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OpportunityNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except OpportunityBuildFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    response.status_code = 201 if created else 200
    values = RadarOpportunityResponse.model_validate(opportunity).model_dump()
    return RadarOpportunityCreateResponse(**values, created=created)


@router.post(
    "/observations/{observation_id}/investigate",
    response_model=ObservationInvestigationResponse,
)
async def investigate_signal_observation(
    observation_id: UUID,
    response: Response,
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_admin)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ObservationInvestigationResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        execution = await investigate_observation(
            db,
            workspace_id=context.workspace.id,
            observation_id=observation_id,
        )
    except InvestigationObservationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvestigationNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InvestigationDecisionFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except InvestigationSearchFailed as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ObservationInvestigationResponse(
        observation_id=execution.observation_id,
        outcome=execution.decision.outcome,
        rationale=execution.decision.rationale,
        queries=[
            InvestigationQueryResponse(
                edge_id=query.plan.edge_id,
                target_signal=query.plan.target_signal,
                investigation_question=query.plan.investigation_question,
                query_text=query.plan.query_text,
                reason=query.plan.reason,
                preferred_domains=list(query.plan.preferred_domains),
                request_id=query.request_id,
                results=[
                    InvestigationResultResponse(
                        result_rank=rank,
                        title=result.title,
                        url=result.url,
                        content=result.content,
                        score=result.score,
                        published_date=result.published_date,
                    )
                    for rank, result in enumerate(query.results, start=1)
                ],
            )
            for query in execution.queries
        ],
    )


@router.get("/observations", response_model=list[SignalObservationResponse])
def get_signal_observations(
    response: Response,
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_context)],
    db: Annotated[Session, Depends(get_db_session)],
    job_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[SignalObservationResponse]:
    response.headers["Cache-Control"] = "no-store"
    observations = list_signal_observations(
        db,
        workspace_id=context.workspace.id,
        search_job_id=job_id,
        limit=limit,
    )
    return [SignalObservationResponse.model_validate(item) for item in observations]


def _job_response(db: Session, job, *, created: bool | None = None):
    counts = query_status_counts(db, job.id)
    opportunity_counts = opportunity_status_counts(db, job.id)
    values = {
        "id": job.id,
        "workspace_id": job.workspace_id,
        "initiated_by_user_id": job.initiated_by_user_id,
        "brokerage_profile_id": job.brokerage_profile_id,
        "status": job.status,
        "pipeline_status": job.pipeline_status,
        "pipeline_error_code": job.pipeline_error_code,
        "pipeline_error_message": job.pipeline_error_message,
        "country": job.country,
        "market": job.market,
        "configured_submarkets": job.configured_submarkets,
        "resolved_submarket": job.resolved_submarket,
        "brokerage_profile_updated_at": job.brokerage_profile_updated_at,
        "search_context_version": job.search_context_version,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "pipeline_started_at": job.pipeline_started_at,
        "pipeline_completed_at": job.pipeline_completed_at,
        "total_queries": sum(counts.values()),
        "pending_queries": counts["pending"],
        "running_queries": counts["running"],
        "succeeded_queries": counts["succeeded"],
        "failed_queries": counts["failed"],
        "completed_opportunities": opportunity_counts["completed"],
        "failed_opportunities": opportunity_counts["failed"],
        "queries": [SearchQuerySummary.model_validate(query) for query in job.queries],
    }
    if created is None:
        return SearchJobResponse(**values)
    return SearchJobCreateResponse(**values, created=created)


@router.post("/jobs", response_model=SearchJobCreateResponse)
def build_radar(
    response: Response,
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_admin)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SearchJobCreateResponse:
    response.headers["Cache-Control"] = "no-store"
    if not RadarTavilyClient().configured:
        raise HTTPException(status_code=503, detail="Tavily search is not configured")
    try:
        result = create_search_job(
            db,
            workspace_id=context.workspace.id,
            initiated_by_user_id=context.user.id,
        )
    except BrokerageProfileRequired as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    dispatch_search_queries(job_id=result.job.id)
    job = load_search_job(
        db,
        job_id=result.job.id,
        workspace_id=context.workspace.id,
    )
    response.status_code = 202 if result.created else 200
    return _job_response(db, job, created=result.created)


@router.get("/jobs/{job_id}", response_model=SearchJobResponse)
def get_radar_job(
    job_id: UUID,
    response: Response,
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_context)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SearchJobResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        job = load_search_job(db, job_id=job_id, workspace_id=context.workspace.id)
    except SearchJobNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _job_response(db, job)


@router.post(
    "/jobs/{job_id}/queries/{search_query_id}/retry",
    response_model=SearchJobResponse,
)
def retry_radar_query(
    job_id: UUID,
    search_query_id: UUID,
    response: Response,
    context: Annotated[ResolvedWorkspaceContext, Depends(current_workspace_admin)],
    db: Annotated[Session, Depends(get_db_session)],
) -> SearchJobResponse:
    response.headers["Cache-Control"] = "no-store"
    try:
        retry_failed_query(
            db,
            job_id=job_id,
            search_query_id=search_query_id,
            workspace_id=context.workspace.id,
        )
    except SearchJobNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SearchQueryNotRetryable as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ActiveSearchJobExists as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Another active radar job already exists: {exc.job.id}",
        ) from exc
    dispatch_search_queries(job_id=job_id)
    job = load_search_job(db, job_id=job_id, workspace_id=context.workspace.id)
    return _job_response(db, job)
