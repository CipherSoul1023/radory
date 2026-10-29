from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ExtractionRun, SearchJob, SearchQuery, SearchResult
from app.search.extraction_contract import SemanticExtractionOutput
from app.search.extraction_engine import ExtractionJobNotReady, extract_search_job
from app.search.extractor import ExtractionResult, extraction_identity


class FakeExtractor:
    model = "fake-super"
    max_output_tokens = 4096

    def __init__(self):
        self.calls = []

    async def extract(self, evidence):
        self.calls.append(evidence)
        identity = extraction_identity(
            evidence,
            model=self.model,
            max_output_tokens=self.max_output_tokens,
        )
        return ExtractionResult(
            status="succeeded",
            output=SemanticExtractionOutput(outcome="assessed", events=[]),
            error_code=None,
            cache_key=identity.cache_key,
            model=self.model,
            specification_fingerprint=identity.specification_fingerprint,
            provider_request_id="fake-request",
            provider_model=self.model,
            usage={"total_tokens": 1},
            model_calls=1,
        )


def discovery_job(
    db: Session,
    context: dict,
    *,
    status: str = "completed",
    usable_results: int = 2,
    unusable_results: int = 0,
) -> SearchJob:
    profile = context["profile"]
    job = SearchJob(
        workspace_id=context["workspace"].id,
        initiated_by_user_id=context["user"].id,
        brokerage_profile_id=profile.id,
        status=status,
        country=profile.country,
        market=profile.primary_market,
        configured_submarkets=profile.submarkets,
        resolved_submarket=profile.submarkets[0],
        brokerage_profile_updated_at=profile.updated_at,
        search_context_version=1,
        completed_at=datetime.now(UTC) if status != "running" else None,
    )
    query = SearchQuery(
        job=job,
        signal_key="office_opening",
        query_rank=1,
        query_text="companies opening offices in Johannesburg",
        preferred_domains=[],
        include_domains_mode="prefer",
        search_depth="advanced",
        max_results=10,
        include_raw_content=True,
        status="succeeded" if status != "running" else "running",
        attempt_count=1,
        dispatch_attempt_count=1,
    )
    for rank in range(1, usable_results + 1):
        query.results.append(
            SearchResult(
                result_rank=rank,
                title="Acme plans a Johannesburg office",
                url=f"https://example.com/acme-{rank}",
                content="Acme plans to open a Johannesburg office next year.",
                raw_payload={"raw_content": "Acme plans to open a Johannesburg office next year."},
            )
        )
    for offset in range(1, unusable_results + 1):
        query.results.append(
            SearchResult(
                result_rank=usable_results + offset,
                title="Empty result",
                url=f"https://example.com/empty-{offset}",
                content=None,
                raw_payload={},
            )
        )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@pytest.mark.asyncio
async def test_deduplicates_evidence_before_calling_model(
    search_db: Session, search_workspace: dict
):
    job = discovery_job(search_db, search_workspace, usable_results=2)
    extractor = FakeExtractor()

    result = await extract_search_job(
        search_db,
        search_job_id=job.id,
        extractor=extractor,
    )

    assert result.search_results == 2
    assert result.evidence_groups == 1
    assert result.model_calls == 1
    assert result.succeeded_extractions == 1
    assert len(extractor.calls) == 1
    assert len(extractor.calls[0].sources) == 2


@pytest.mark.asyncio
async def test_rerun_reuses_success_without_calling_model(
    search_db: Session, search_workspace: dict
):
    job = discovery_job(search_db, search_workspace, usable_results=1)
    first_extractor = FakeExtractor()
    await extract_search_job(search_db, search_job_id=job.id, extractor=first_extractor)
    second_extractor = FakeExtractor()

    result = await extract_search_job(
        search_db,
        search_job_id=job.id,
        extractor=second_extractor,
    )

    assert result.model_calls == 0
    assert result.reused_extractions == 1
    assert not second_extractor.calls
    assert search_db.scalar(select(func.count()).select_from(ExtractionRun)) == 1


@pytest.mark.asyncio
async def test_skips_results_without_usable_evidence(search_db: Session, search_workspace: dict):
    job = discovery_job(
        search_db,
        search_workspace,
        usable_results=1,
        unusable_results=1,
    )

    result = await extract_search_job(
        search_db,
        search_job_id=job.id,
        extractor=FakeExtractor(),
    )

    assert result.search_results == 2
    assert result.skipped_results == 1
    assert result.evidence_groups == 1


@pytest.mark.asyncio
async def test_rejects_nonterminal_discovery_job(search_db: Session, search_workspace: dict):
    job = discovery_job(search_db, search_workspace, status="running", usable_results=0)

    with pytest.raises(ExtractionJobNotReady):
        await extract_search_job(
            search_db,
            search_job_id=job.id,
            extractor=FakeExtractor(),
        )
