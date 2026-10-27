from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.integrations.tavily.client import TavilyError
from app.models import BrokerageProfile, SearchJob, SearchQuery, SearchResult
from app.search.planner import BrokerSearchContext, build_discovery_search_plans
from app.search.tavily_client import PlannedTavilyQuery, RadarTavilyClient
from app.search.transitions import derive_job_status, retry_at


class BrokerageProfileRequired(RuntimeError):
    pass


class ActiveSearchJobExists(RuntimeError):
    def __init__(self, job: SearchJob):
        super().__init__("An active radar search job already exists")
        self.job = job


class SearchJobNotFound(RuntimeError):
    pass


class SearchQueryNotRetryable(RuntimeError):
    pass


@dataclass(frozen=True)
class JobCreationResult:
    job: SearchJob
    created: bool


@dataclass(frozen=True)
class QueryExecutionResult:
    search_query_id: uuid.UUID
    executed: bool
    retry_scheduled: bool = False


def utc_now() -> datetime:
    return datetime.now(UTC)


def active_search_job(db: Session, workspace_id: uuid.UUID) -> SearchJob | None:
    return db.scalar(
        select(SearchJob)
        .where(
            SearchJob.workspace_id == workspace_id,
            SearchJob.status.in_(("pending", "running")),
        )
        .order_by(SearchJob.created_at)
    )


def create_search_job(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    initiated_by_user_id: uuid.UUID,
    settings: Settings | None = None,
) -> JobCreationResult:
    existing = active_search_job(db, workspace_id)
    if existing is not None:
        return JobCreationResult(job=existing, created=False)

    profile = db.scalar(
        select(BrokerageProfile).where(BrokerageProfile.workspace_id == workspace_id)
    )
    if profile is None:
        raise BrokerageProfileRequired("A brokerage profile is required to build a radar")

    config = settings or get_settings()
    job_id = uuid.uuid4()
    context = BrokerSearchContext(
        country=profile.country,
        market=profile.primary_market,
        submarkets=tuple(profile.submarkets),
    )
    plans = build_discovery_search_plans(
        job_id=job_id,
        workspace_id=workspace_id,
        profile=context,
    )
    if len(plans) != 26 or len({(plan.signal_key, plan.query_rank) for plan in plans}) != 26:
        raise RuntimeError("The discovery planner must produce exactly 26 unique plans")

    profile_version = profile.updated_at or profile.created_at
    if profile_version is None:
        raise RuntimeError("The brokerage profile has no persistence timestamp")
    job = SearchJob(
        id=job_id,
        workspace_id=workspace_id,
        initiated_by_user_id=initiated_by_user_id,
        brokerage_profile_id=profile.id,
        status="pending",
        country=context.country,
        market=context.market,
        configured_submarkets=list(context.submarkets),
        resolved_submarket=context.resolved_submarket,
        brokerage_profile_updated_at=profile_version,
        search_context_version=1,
    )
    db.add(job)
    for plan in plans:
        db.add(
            SearchQuery(
                job_id=job.id,
                signal_key=plan.signal_key,
                query_rank=plan.query_rank,
                query_text=plan.query_text,
                preferred_domains=list(plan.preferred_domains),
                include_domains_mode=plan.include_domains_mode,
                search_depth=config.tavily_search_depth,
                max_results=config.tavily_max_results,
                include_raw_content=False,
                status="pending",
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = active_search_job(db, workspace_id)
        if existing is None:
            raise
        return JobCreationResult(job=existing, created=False)
    db.refresh(job)
    return JobCreationResult(job=job, created=True)


def load_search_job(db: Session, *, job_id: uuid.UUID, workspace_id: uuid.UUID) -> SearchJob:
    job = db.scalar(
        select(SearchJob)
        .options(selectinload(SearchJob.queries))
        .execution_options(populate_existing=True)
        .where(SearchJob.id == job_id, SearchJob.workspace_id == workspace_id)
    )
    if job is None:
        raise SearchJobNotFound("Radar search job not found")
    return job


def eligible_query_ids(
    db: Session,
    *,
    job_id: uuid.UUID | None = None,
    now: datetime | None = None,
    stale_seconds: int | None = None,
) -> list[uuid.UUID]:
    current_time = now or utc_now()
    stale_after = stale_seconds or get_settings().radar_dispatch_stale_seconds
    statement = select(SearchQuery.id).where(
        SearchQuery.status == "pending",
        or_(SearchQuery.next_attempt_at.is_(None), SearchQuery.next_attempt_at <= current_time),
        or_(
            SearchQuery.last_dispatched_at.is_(None),
            SearchQuery.last_dispatched_at <= current_time - timedelta(seconds=stale_after),
        ),
    )
    if job_id is not None:
        statement = statement.where(SearchQuery.job_id == job_id)
    return list(db.scalars(statement.order_by(SearchQuery.created_at, SearchQuery.id)))


def record_dispatch_attempt(
    db: Session, *, search_query_id: uuid.UUID, dispatched: bool, now: datetime | None = None
) -> None:
    query = db.get(SearchQuery, search_query_id)
    if query is None or query.status != "pending":
        return
    query.dispatch_attempt_count += 1
    if dispatched:
        current_time = now or utc_now()
        query.last_dispatched_at = current_time
        job = db.get(SearchJob, query.job_id)
        if job is not None and job.status == "pending":
            job.status = "running"
            job.started_at = job.started_at or current_time
    db.commit()


def recover_expired_leases(
    db: Session, *, now: datetime | None = None, settings: Settings | None = None
) -> int:
    current_time = now or utc_now()
    config = settings or get_settings()
    queries = list(
        db.scalars(
            select(SearchQuery)
            .where(
                SearchQuery.status == "running",
                SearchQuery.lease_expires_at.is_not(None),
                SearchQuery.lease_expires_at <= current_time,
            )
            .with_for_update(skip_locked=True)
        )
    )
    job_ids: set[uuid.UUID] = set()
    for query in queries:
        query.lease_expires_at = None
        query.last_error_code = "lease_expired"
        query.last_error_message = "The previous execution lease expired"
        if query.attempt_count >= config.radar_query_max_attempts:
            query.status = "failed"
            query.next_attempt_at = None
            query.completed_at = current_time
        else:
            query.status = "pending"
            query.next_attempt_at = current_time
            query.last_dispatched_at = None
        job_ids.add(query.job_id)
    for job_id in job_ids:
        _refresh_job_status(db, job_id, now=current_time)
    db.commit()
    return len(queries)


def execute_search_query(
    db: Session,
    *,
    search_query_id: uuid.UUID,
    tavily: RadarTavilyClient | None = None,
    settings: Settings | None = None,
) -> QueryExecutionResult:
    config = settings or get_settings()
    claim = _claim_query(db, search_query_id, lease_seconds=config.radar_query_lease_seconds)
    if claim is None:
        return QueryExecutionResult(search_query_id=search_query_id, executed=False)
    attempt_number, planned_query = claim
    client = tavily or RadarTavilyClient()
    try:
        response = client.execute(planned_query)
    except TavilyError as exc:
        retry_scheduled = _record_failure(
            db,
            search_query_id=search_query_id,
            attempt_number=attempt_number,
            error_code=exc.error_code,
            error_message=str(exc),
            retryable=exc.retryable,
            settings=config,
        )
        return QueryExecutionResult(
            search_query_id=search_query_id,
            executed=True,
            retry_scheduled=retry_scheduled,
        )
    except Exception:
        _record_failure(
            db,
            search_query_id=search_query_id,
            attempt_number=attempt_number,
            error_code="execution_error",
            error_message="Unexpected search execution error",
            retryable=False,
            settings=config,
        )
        return QueryExecutionResult(search_query_id=search_query_id, executed=True)

    _record_success(
        db,
        search_query_id=search_query_id,
        attempt_number=attempt_number,
        response=response,
    )
    return QueryExecutionResult(search_query_id=search_query_id, executed=True)


def retry_failed_query(
    db: Session,
    *,
    job_id: uuid.UUID,
    search_query_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> SearchQuery:
    query = db.scalar(
        select(SearchQuery)
        .join(SearchJob)
        .where(
            SearchQuery.id == search_query_id,
            SearchQuery.job_id == job_id,
            SearchJob.workspace_id == workspace_id,
        )
        .with_for_update()
    )
    if query is None:
        raise SearchJobNotFound("Radar search query not found")
    if query.status != "failed":
        raise SearchQueryNotRetryable("Only failed search queries can be retried")
    active = active_search_job(db, workspace_id)
    if active is not None and active.id != job_id:
        raise ActiveSearchJobExists(active)

    current_time = utc_now()
    query.status = "pending"
    query.attempt_count = 0
    query.next_attempt_at = current_time
    query.last_dispatched_at = None
    query.lease_expires_at = None
    query.completed_at = None
    query.last_error_code = None
    query.last_error_message = None
    job = query.job
    job.status = "running"
    job.started_at = job.started_at or current_time
    job.completed_at = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        active = active_search_job(db, workspace_id)
        if active is not None:
            raise ActiveSearchJobExists(active) from None
        raise
    db.refresh(query)
    return query


def _claim_query(
    db: Session, search_query_id: uuid.UUID, *, lease_seconds: int
) -> tuple[int, PlannedTavilyQuery] | None:
    current_time = utc_now()
    query = db.scalar(
        select(SearchQuery)
        .where(
            SearchQuery.id == search_query_id,
            SearchQuery.status == "pending",
            or_(SearchQuery.next_attempt_at.is_(None), SearchQuery.next_attempt_at <= current_time),
        )
        .with_for_update(skip_locked=True)
    )
    if query is None:
        db.rollback()
        return None
    query.status = "running"
    query.attempt_count += 1
    query.started_at = query.started_at or current_time
    query.next_attempt_at = None
    query.lease_expires_at = current_time + timedelta(seconds=lease_seconds)
    job = db.get(SearchJob, query.job_id)
    if job is not None:
        job.status = "running"
        job.started_at = job.started_at or current_time
        job.completed_at = None
    planned_query = PlannedTavilyQuery(
        query_text=query.query_text,
        preferred_domains=tuple(query.preferred_domains),
        include_domains_mode=query.include_domains_mode,
        search_depth=query.search_depth,
        max_results=query.max_results,
        include_raw_content=query.include_raw_content,
    )
    attempt_number = query.attempt_count
    db.commit()
    return attempt_number, planned_query


def _record_success(
    db: Session,
    *,
    search_query_id: uuid.UUID,
    attempt_number: int,
    response,
) -> None:
    query = db.scalar(
        select(SearchQuery).where(SearchQuery.id == search_query_id).with_for_update()
    )
    if query is None or query.status != "running" or query.attempt_count != attempt_number:
        db.rollback()
        return
    db.execute(delete(SearchResult).where(SearchResult.search_query_id == query.id))
    for rank, result in enumerate(response.results, start=1):
        db.add(
            SearchResult(
                search_query_id=query.id,
                result_rank=rank,
                provider_result_id=result.provider_result_id,
                title=result.title,
                url=result.url,
                content=result.content,
                provider_score=result.score,
                published_at=_parse_published_at(result.published_date),
                raw_payload=result.raw_payload,
            )
        )
    current_time = utc_now()
    query.status = "succeeded"
    query.completed_at = current_time
    query.lease_expires_at = None
    query.next_attempt_at = None
    query.last_error_code = None
    query.last_error_message = None
    query.provider_request_id = response.request_id
    query.provider_response_time_seconds = response.response_time_seconds
    query.provider_usage = response.usage
    _refresh_job_status(db, query.job_id, now=current_time)
    db.commit()


def _record_failure(
    db: Session,
    *,
    search_query_id: uuid.UUID,
    attempt_number: int,
    error_code: str,
    error_message: str,
    retryable: bool,
    settings: Settings,
) -> bool:
    query = db.scalar(
        select(SearchQuery).where(SearchQuery.id == search_query_id).with_for_update()
    )
    if query is None or query.status != "running" or query.attempt_count != attempt_number:
        db.rollback()
        return False
    current_time = utc_now()
    query.lease_expires_at = None
    query.last_error_code = error_code[:64]
    query.last_error_message = error_message[:1000]
    should_retry = retryable and query.attempt_count < settings.radar_query_max_attempts
    if should_retry:
        query.status = "pending"
        query.next_attempt_at = retry_at(
            attempt_count=query.attempt_count,
            base_seconds=settings.radar_retry_base_seconds,
            now=current_time,
        )
        query.last_dispatched_at = None
        query.completed_at = None
    else:
        query.status = "failed"
        query.next_attempt_at = None
        query.completed_at = current_time
    _refresh_job_status(db, query.job_id, now=current_time)
    db.commit()
    return should_retry


def _refresh_job_status(db: Session, job_id: uuid.UUID, *, now: datetime) -> None:
    job = db.scalar(select(SearchJob).where(SearchJob.id == job_id).with_for_update())
    if job is None:
        return
    statuses = list(db.scalars(select(SearchQuery.status).where(SearchQuery.job_id == job_id)))
    status = derive_job_status(statuses, started=job.started_at is not None)
    job.status = status
    if status in {"completed", "partial_failed", "failed"}:
        job.completed_at = now
    else:
        job.completed_at = None


def query_status_counts(db: Session, job_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(SearchQuery.status, func.count())
        .where(SearchQuery.job_id == job_id)
        .group_by(SearchQuery.status)
    )
    counts = {"pending": 0, "running": 0, "succeeded": 0, "failed": 0}
    counts.update({status: count for status, count in rows})
    return counts


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
