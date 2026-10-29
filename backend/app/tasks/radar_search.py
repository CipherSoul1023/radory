from __future__ import annotations

import asyncio
import logging
import uuid

from app.database.session import get_session
from app.search.engine import (
    eligible_query_ids,
    execute_search_query,
    record_dispatch_attempt,
    recover_expired_leases,
)
from app.search.extraction_engine import extract_search_job
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="radory.radar.execute_search_query", ignore_result=True)
def execute_search_query_task(search_query_id: str) -> None:
    query_id = uuid.UUID(search_query_id)
    with get_session() as db:
        execute_search_query(db, search_query_id=query_id)


@celery_app.task(name="radory.radar.extract_search_job", ignore_result=True)
def extract_search_job_task(search_job_id: str) -> None:
    job_id = uuid.UUID(search_job_id)
    with get_session() as db:
        asyncio.run(extract_search_job(db, search_job_id=job_id))


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


@celery_app.task(name="radory.radar.reconcile_search_queries", ignore_result=True)
def reconcile_search_queries_task() -> None:
    with get_session() as db:
        recover_expired_leases(db)
    dispatch_search_queries()
