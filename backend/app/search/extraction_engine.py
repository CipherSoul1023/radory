from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.integrations.nebius.client import NebiusClient
from app.models import SearchJob, SearchQuery
from app.search.evidence import (
    EvidenceUnavailable,
    PreparedEvidence,
    group_identical_evidence,
    prepare_search_result,
)
from app.search.extraction_persistence import (
    persist_extraction_result,
    reuse_successful_extraction,
)
from app.search.extractor import (
    ExtractionResult,
    SemanticExtractor,
    extraction_identity,
)


class ExtractionJobNotFound(RuntimeError):
    pass


class ExtractionJobNotReady(RuntimeError):
    pass


class ExtractionModelNotConfigured(RuntimeError):
    pass


class Extractor(Protocol):
    model: str
    max_output_tokens: int

    async def extract(self, evidence: PreparedEvidence) -> ExtractionResult: ...


@dataclass(frozen=True)
class ExtractionJobResult:
    search_job_id: uuid.UUID
    search_results: int
    evidence_groups: int
    skipped_results: int
    model_calls: int
    reused_extractions: int
    succeeded_extractions: int
    failed_extractions: int
    observations: int


def _load_job(db: Session, search_job_id: uuid.UUID) -> SearchJob:
    job = db.scalar(
        select(SearchJob)
        .options(selectinload(SearchJob.queries).selectinload(SearchQuery.results))
        .where(SearchJob.id == search_job_id)
    )
    if job is None:
        raise ExtractionJobNotFound("Radar search job not found")
    if job.status not in {"completed", "partial_failed", "failed"}:
        raise ExtractionJobNotReady("Discovery must reach a terminal state before extraction")
    return job


def _prepare_job_evidence(job: SearchJob) -> tuple[list[PreparedEvidence], int, int]:
    results = [result for query in job.queries for result in query.results]
    prepared = []
    skipped = 0
    for result in results:
        try:
            prepared.append(prepare_search_result(result, workspace_id=job.workspace_id))
        except EvidenceUnavailable:
            skipped += 1
    return group_identical_evidence(prepared), len(results), skipped


async def extract_search_job(
    db: Session,
    *,
    search_job_id: uuid.UUID,
    extractor: Extractor | None = None,
    settings: Settings | None = None,
) -> ExtractionJobResult:
    """Extract one terminal discovery job; never dispatch investigation work."""
    job = _load_job(db, search_job_id)
    evidence_groups, result_count, skipped = _prepare_job_evidence(job)
    config = settings or get_settings()
    selected = extractor
    if selected is None:
        if not config.nemotron_super_model:
            raise ExtractionModelNotConfigured("NEMOTRON_SUPER_MODEL is required")
        selected = SemanticExtractor(
            NebiusClient(),
            model=config.nemotron_super_model,
            max_output_tokens=config.nemotron_extraction_max_tokens,
        )

    model_calls = 0
    reused = 0
    succeeded = 0
    failed = 0
    observations = 0
    for evidence in evidence_groups:
        identity = extraction_identity(
            evidence,
            model=selected.model,
            max_output_tokens=selected.max_output_tokens,
        )
        cached = reuse_successful_extraction(
            db,
            evidence=evidence,
            cache_key=identity.cache_key,
        )
        if cached is not None:
            reused += 1
            observations += len(cached.run.observations)
            continue

        extraction = await selected.extract(evidence)
        persisted = persist_extraction_result(
            db,
            evidence=evidence,
            result=extraction,
            max_output_tokens=selected.max_output_tokens,
        )
        model_calls += extraction.model_calls
        if extraction.status == "succeeded":
            succeeded += 1
            observations += len(persisted.run.observations)
        else:
            failed += 1

    return ExtractionJobResult(
        search_job_id=job.id,
        search_results=result_count,
        evidence_groups=len(evidence_groups),
        skipped_results=skipped,
        model_calls=model_calls,
        reused_extractions=reused,
        succeeded_extractions=succeeded,
        failed_extractions=failed,
        observations=observations,
    )
