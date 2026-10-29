from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy import select

from app.database.session import get_session
from app.models import SearchQuery
from app.search.engine import (
    eligible_query_ids,
    execute_search_query,
    record_dispatch_attempt,
    recover_expired_leases,
)
from app.search.extraction_engine import extract_search_job
from app.search.pipeline import (
    claim_radar_pipeline,
    fail_radar_pipeline,
    process_radar_pipeline,
    ready_pipeline_job_ids,
)
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="radory.radar.execute_search_query", ignore_result=True)
def execute_search_query_task(search_query_id: str) -> None:
    query_id = uuid.UUID(search_query_id)
    with get_session() as db:
        job_id = db.scalar(select(SearchQuery.job_id).where(SearchQuery.id == query_id))
        execute_search_query(db, search_query_id=query_id)
    if job_id is not None:
        dispatch_radar_pipelines(job_id=job_id)


@celery_app.task(name="radory.radar.extract_search_job", ignore_result=True)
def extract_search_job_task(search_job_id: str) -> None:
    job_id = uuid.UUID(search_job_id)
    with get_session() as db:
        asyncio.run(extract_search_job(db, search_job_id=job_id))


@celery_app.task(name="radory.radar.process_pipeline", ignore_result=True)
def process_radar_pipeline_task(search_job_id: str) -> None:
    job_id = uuid.UUID(search_job_id)
    with get_session() as db:
        if not claim_radar_pipeline(db, search_job_id=job_id):
            return
        try:
            asyncio.run(process_radar_pipeline(db, search_job_id=job_id))
        except Exception as exc:
            logger.exception("Radar post-processing failed for job %s", job_id)
            fail_radar_pipeline(
                db,
                search_job_id=job_id,
                error_code=type(exc).__name__.lower(),
                error_message="Radar post-processing failed",
            )


def dispatch_search_queries(*, job_id: uuid.UUID | None = None) -> int:
    with get_session() as db:
        query_ids = eligible_query_ids(db, job_id=job_id)
    dispatched = 0
    for query_id in query_ids:
        try:
            execute_search_query_task.apply_async(args=[str(query_id)])
        except Exception:
            logger.warning("Unable to dispatch radar search query %s", query_id)
            with get_session() as db:
                record_dispatch_attempt(
                    db,
                    search_query_id=query_id,
                    dispatched=False,
                )
        else:
            dispatched += 1
            with get_session() as db:
                record_dispatch_attempt(
                    db,
                    search_query_id=query_id,
                    dispatched=True,
                )
    return dispatched


def dispatch_radar_pipelines(*, job_id: uuid.UUID | None = None) -> int:
    with get_session() as db:
        job_ids = ready_pipeline_job_ids(db)
    if job_id is not None:
        job_ids = [candidate for candidate in job_ids if candidate == job_id]
    dispatched = 0
    for candidate in job_ids:
        try:
            process_radar_pipeline_task.apply_async(args=[str(candidate)])
        except Exception:
            logger.warning("Unable to dispatch radar post-processing for job %s", candidate)
        else:
            dispatched += 1
    return dispatched


@celery_app.task(name="radory.radar.reconcile_search_queries", ignore_result=True)
def reconcile_search_queries_task() -> None:
    with get_session() as db:
        recover_expired_leases(db)
    dispatch_search_queries()
    dispatch_radar_pipelines()
