from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.tavily.client import (
    TavilyResponse,
    TavilyResult,
    TavilyTransportError,
)
from app.models import SearchJob, SearchQuery, SearchResult
from app.search.engine import (
    create_search_job,
    execute_search_query,
    recover_expired_leases,
    retry_failed_query,
)
from app.search.transitions import derive_job_status


class SuccessfulTavily:
    configured = True

    def execute(self, planned_query):
        assert planned_query.query_text
        assert planned_query.include_raw_content is True
        return TavilyResponse(
            results=[
                TavilyResult(
                    provider_result_id="result-1",
                    title="Example expansion",
                    url="https://example.com/expansion",
                    content="The company opened a larger office.",
                    score=0.91,
                    published_date="Tue, 11 Mar 2025 17:00:00 GMT",
                    raw_payload={
                        "id": "result-1",
                        "title": "Example expansion",
                        "url": "https://example.com/expansion",
                        "raw_content": "# Expansion\n\nThe company opened a larger office.",
                        "future_field": {"preserved": True},
                    },
                )
            ],
            request_id="request-1",
            response_time_seconds=1.25,
            usage={"credits": 1},
        )


class FailingTavily:
    configured = True

    def execute(self, planned_query):
        raise TavilyTransportError("Tavily request failed")


def test_job_creation_persists_all_26_queries_and_reuses_active_job(
    search_db: Session, search_workspace: dict
):
    first = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    )
    assert first.created
    assert first.job.configured_submarkets == ["Sandton", "Rosebank"]
    assert first.job.resolved_submarket == "Sandton"
    assert search_db.scalar(select(func.count()).select_from(SearchQuery)) == 26
    assert all(search_db.scalars(select(SearchQuery.include_raw_content)))

    second = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    )
    assert not second.created
    assert second.job.id == first.job.id
    assert search_db.scalar(select(func.count()).select_from(SearchJob)) == 1


def test_successful_query_stores_raw_evidence_and_updates_status(
    search_db: Session, search_workspace: dict
):
    creation = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    )
    query = search_db.scalar(
        select(SearchQuery).where(SearchQuery.job_id == creation.job.id).limit(1)
    )
    outcome = execute_search_query(
        search_db,
        search_query_id=query.id,
        tavily=SuccessfulTavily(),
    )
    assert outcome.executed
    search_db.refresh(query)
    assert query.status == "succeeded"
    assert query.attempt_count == 1
    assert query.provider_request_id == "request-1"
    assert query.provider_usage == {"credits": 1}
    result = search_db.scalar(select(SearchResult).where(SearchResult.search_query_id == query.id))
    assert result.provider_score == 0.91
    assert result.raw_payload["future_field"] == {"preserved": True}
    assert result.raw_payload["raw_content"] == (
        "# Expansion\n\nThe company opened a larger office."
    )
    search_db.refresh(creation.job)
    assert creation.job.status == "running"


def test_transient_failure_retries_only_that_query_and_stops_at_limit(
    search_db: Session, search_workspace: dict
):
    creation = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    )
    query = search_db.scalar(
        select(SearchQuery).where(SearchQuery.job_id == creation.job.id).limit(1)
    )
    settings = Settings(
        _env_file=None,
        radar_query_max_attempts=3,
        radar_retry_base_seconds=1,
    )
    for attempt in range(1, 4):
        outcome = execute_search_query(
            search_db,
            search_query_id=query.id,
            tavily=FailingTavily(),
            settings=settings,
        )
        search_db.refresh(query)
        assert outcome.executed
        assert query.attempt_count == attempt
        if attempt < 3:
            assert outcome.retry_scheduled
            assert query.status == "pending"
            query.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            search_db.commit()
        else:
            assert not outcome.retry_scheduled
            assert query.status == "failed"
    other_attempts = list(
        search_db.scalars(
            select(SearchQuery.attempt_count).where(
                SearchQuery.job_id == creation.job.id,
                SearchQuery.id != query.id,
            )
        )
    )
    assert set(other_attempts) == {0}

    retried = retry_failed_query(
        search_db,
        job_id=creation.job.id,
        search_query_id=query.id,
        workspace_id=search_workspace["workspace"].id,
    )
    assert retried.status == "pending"
    assert retried.attempt_count == 0
    search_db.refresh(creation.job)
    assert creation.job.status == "running"


def test_expired_execution_lease_returns_query_to_pending(
    search_db: Session, search_workspace: dict
):
    creation = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    )
    query = search_db.scalar(
        select(SearchQuery).where(SearchQuery.job_id == creation.job.id).limit(1)
    )
    query.status = "running"
    query.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    creation.job.status = "running"
    creation.job.started_at = datetime.now(UTC) - timedelta(minutes=1)
    search_db.commit()
    assert recover_expired_leases(search_db) == 1
    search_db.refresh(query)
    assert query.status == "pending"
    assert query.last_error_code == "lease_expired"
    assert query.lease_expires_at is None


def test_repeated_expired_leases_respect_the_attempt_limit(
    search_db: Session, search_workspace: dict
):
    creation = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    )
    query = search_db.scalar(
        select(SearchQuery).where(SearchQuery.job_id == creation.job.id).limit(1)
    )
    query.status = "running"
    query.attempt_count = 3
    query.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    creation.job.status = "running"
    creation.job.started_at = datetime.now(UTC) - timedelta(minutes=1)
    search_db.commit()
    settings = Settings(_env_file=None, radar_query_max_attempts=3)
    assert recover_expired_leases(search_db, settings=settings) == 1
    search_db.refresh(query)
    assert query.status == "failed"
    assert query.completed_at is not None


def test_job_status_is_derived_from_query_rows():
    assert derive_job_status(["pending"] * 26, started=False) == "pending"
    assert derive_job_status(["pending"] * 26, started=True) == "running"
    assert derive_job_status(["succeeded"] * 26, started=True) == "completed"
    assert derive_job_status(["failed"] * 26, started=True) == "failed"
    assert derive_job_status(["succeeded"] * 25 + ["failed"], started=True) == "partial_failed"
