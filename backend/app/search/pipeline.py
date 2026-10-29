from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ExtractionRun,
    ExtractionSource,
    RadarOpportunity,
    SearchJob,
    SearchQuery,
    SearchResult,
    SignalObservation,
)
from app.search.extraction_engine import ExtractionJobResult, extract_search_job
from app.search.opportunity_engine import OpportunityBuildFailed, build_radar_opportunity

TERMINAL_JOB_STATUSES = ("completed", "partial_failed", "failed")


@dataclass(frozen=True)
class RadarPipelineResult:
    search_job_id: uuid.UUID
    extraction: ExtractionJobResult
    opportunity_events: int
    completed_opportunities: int
    failed_opportunities: int
    status: str


def _utc_now() -> datetime:
    return datetime.now(UTC)


def ready_pipeline_job_ids(db: Session) -> list[uuid.UUID]:
    return list(
        db.scalars(
            select(SearchJob.id)
            .where(
                SearchJob.status.in_(TERMINAL_JOB_STATUSES),
                SearchJob.pipeline_status == "pending",
            )
            .order_by(SearchJob.created_at)
        )
    )


def claim_radar_pipeline(db: Session, *, search_job_id: uuid.UUID) -> bool:
    job = db.scalar(
        select(SearchJob).where(SearchJob.id == search_job_id).with_for_update(skip_locked=True)
    )
    if job is None or job.status not in TERMINAL_JOB_STATUSES or job.pipeline_status != "pending":
        db.rollback()
        return False
    job.pipeline_status = "running"
    job.pipeline_started_at = _utc_now()
    job.pipeline_completed_at = None
    job.pipeline_error_code = None
    job.pipeline_error_message = None
    db.commit()
    return True


def fail_radar_pipeline(
    db: Session,
    *,
    search_job_id: uuid.UUID,
    error_code: str,
    error_message: str,
) -> None:
    job = db.get(SearchJob, search_job_id)
    if job is None:
        return
    job.pipeline_status = "failed"
    job.pipeline_error_code = error_code[:64]
    job.pipeline_error_message = error_message[:1000]
    job.pipeline_completed_at = _utc_now()
    db.commit()


def _event_seed_observation_ids(
    db: Session,
    *,
    search_job_id: uuid.UUID,
) -> list[uuid.UUID]:
    observations = list(
        db.scalars(
            select(SignalObservation)
            .join(ExtractionRun, ExtractionRun.id == SignalObservation.extraction_run_id)
            .join(ExtractionSource, ExtractionSource.extraction_run_id == ExtractionRun.id)
            .join(SearchResult, SearchResult.id == ExtractionSource.search_result_id)
            .join(SearchQuery, SearchQuery.id == SearchResult.search_query_id)
            .where(SearchQuery.job_id == search_job_id)
            .order_by(SignalObservation.created_at, SignalObservation.id)
        )
    )
    seeds: dict[tuple[uuid.UUID, int], uuid.UUID] = {}
    for observation in observations:
        seeds.setdefault(
            (observation.extraction_run_id, observation.event_index),
            observation.id,
        )
    return list(seeds.values())


def opportunity_status_counts(db: Session, search_job_id: uuid.UUID) -> dict[str, int]:
    rows = db.execute(
        select(RadarOpportunity.status, func.count())
        .where(RadarOpportunity.search_job_id == search_job_id)
        .group_by(RadarOpportunity.status)
    )
    counts = {"running": 0, "completed": 0, "failed": 0}
    counts.update({status: count for status, count in rows})
    return counts


async def process_radar_pipeline(
    db: Session,
    *,
    search_job_id: uuid.UUID,
) -> RadarPipelineResult:
    job = db.get(SearchJob, search_job_id)
    if job is None or job.pipeline_status != "running":
        raise RuntimeError("Radar pipeline must be claimed before processing")

    extraction = await extract_search_job(db, search_job_id=search_job_id)
    seed_ids = _event_seed_observation_ids(db, search_job_id=search_job_id)
    completed = 0
    failed = 0
    for observation_id in seed_ids:
        try:
            opportunity, _ = await build_radar_opportunity(
                db,
                workspace_id=job.workspace_id,
                observation_id=observation_id,
            )
        except OpportunityBuildFailed:
            failed += 1
        except Exception:
            failed += 1
        else:
            if opportunity.status == "completed":
                completed += 1
            else:
                failed += 1

    if failed and completed:
        status = "partial_failed"
    elif failed:
        status = "failed"
    elif extraction.failed_extractions:
        status = "partial_failed"
    else:
        status = "completed"

    job = db.get(SearchJob, search_job_id)
    if job is None:
        raise RuntimeError("Radar search job disappeared during processing")
    job.pipeline_status = status
    job.pipeline_completed_at = _utc_now()
    job.pipeline_error_code = None
    job.pipeline_error_message = None
    db.commit()
    return RadarPipelineResult(
        search_job_id=search_job_id,
        extraction=extraction,
        opportunity_events=len(seed_ids),
        completed_opportunities=completed,
        failed_opportunities=failed,
        status=status,
    )
