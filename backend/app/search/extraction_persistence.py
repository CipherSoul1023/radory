from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import ExtractionRun, ExtractionSource, SignalObservation
from app.search.evidence import PREPARATION_VERSION, PreparedEvidence, fingerprint
from app.search.extractor import EXTRACTION_VERSION, ExtractionResult


class ExtractionPersistenceError(ValueError):
    pass


@dataclass(frozen=True)
class PersistedExtraction:
    run: ExtractionRun
    created: bool


def _expected_cache_key(
    evidence: PreparedEvidence,
    result: ExtractionResult,
    *,
    max_output_tokens: int,
) -> str:
    return fingerprint(
        {
            "workspace_id": str(evidence.workspace_id),
            "input_fingerprint": evidence.input_fingerprint,
            "specification": result.specification_fingerprint,
            "model": result.model,
            "max_output_tokens": max_output_tokens,
        }
    )


def _validate_result(
    evidence: PreparedEvidence,
    result: ExtractionResult,
    *,
    max_output_tokens: int,
) -> None:
    if not evidence.sources:
        raise ExtractionPersistenceError("Extraction evidence must retain at least one source")
    if any(source.workspace_id != evidence.workspace_id for source in evidence.sources):
        raise ExtractionPersistenceError("Extraction sources cross workspace boundaries")
    if result.cache_key != _expected_cache_key(
        evidence, result, max_output_tokens=max_output_tokens
    ):
        raise ExtractionPersistenceError("Extraction result does not match prepared evidence")
    if result.status == "succeeded":
        if result.output is None or result.error_code is not None:
            raise ExtractionPersistenceError("Successful extraction result is inconsistent")
    elif result.status == "failed":
        if result.output is not None or result.error_code is None:
            raise ExtractionPersistenceError("Failed extraction result is inconsistent")
    else:
        raise ExtractionPersistenceError("Unknown extraction status")


def _successful_run(
    db: Session, evidence: PreparedEvidence, cache_key: str
) -> ExtractionRun | None:
    return db.scalar(
        select(ExtractionRun)
        .options(
            selectinload(ExtractionRun.sources),
            selectinload(ExtractionRun.observations),
        )
        .where(
            ExtractionRun.workspace_id == evidence.workspace_id,
            ExtractionRun.cache_key == cache_key,
            ExtractionRun.status == "succeeded",
        )
    )


def _attach_sources(run: ExtractionRun, evidence: PreparedEvidence) -> None:
    existing = {source.search_result_id for source in run.sources}
    for source in evidence.sources:
        if source.search_result_id not in existing:
            run.sources.append(ExtractionSource(search_result_id=source.search_result_id))
            existing.add(source.search_result_id)


def _observation(
    run: ExtractionRun,
    *,
    event_index: int,
    signal,
    event,
) -> SignalObservation:
    return SignalObservation(
        workspace_id=run.workspace_id,
        event_index=event_index,
        signal_key=signal.signal_key,
        subject_company=event.subject_company.value,
        summary=event.summary.value,
        stage=event.stage.value,
        subject_company_evidence=[
            quote.model_dump(mode="json") for quote in event.subject_company.evidence
        ],
        summary_evidence=[quote.model_dump(mode="json") for quote in event.summary.evidence],
        signal_evidence=[quote.model_dump(mode="json") for quote in signal.evidence],
        stage_evidence=[quote.model_dump(mode="json") for quote in event.stage.evidence],
        locations=[location.model_dump(mode="json") for location in event.locations],
        timing=[timing.model_dump(mode="json") for timing in event.timing],
        related_companies=[company.model_dump(mode="json") for company in event.related_companies],
        missing_facts=list(event.missing_facts),
    )


def persist_extraction_result(
    db: Session,
    *,
    evidence: PreparedEvidence,
    result: ExtractionResult,
    max_output_tokens: int,
) -> PersistedExtraction:
    """Persist validated extraction output and provenance without triggering investigation."""
    _validate_result(evidence, result, max_output_tokens=max_output_tokens)

    if result.status == "succeeded":
        existing = _successful_run(db, evidence, result.cache_key)
        if existing is not None:
            _attach_sources(existing, evidence)
            db.commit()
            db.refresh(existing)
            return PersistedExtraction(run=existing, created=False)

    run = ExtractionRun(
        workspace_id=evidence.workspace_id,
        cache_key=result.cache_key,
        input_fingerprint=evidence.input_fingerprint,
        content_hash=evidence.content_hash,
        preparation_version=PREPARATION_VERSION,
        extraction_version=EXTRACTION_VERSION,
        specification_fingerprint=result.specification_fingerprint,
        model=result.model,
        max_output_tokens=max_output_tokens,
        content_basis=evidence.document.content_basis,
        provider_published_at=evidence.document.provider_published_at,
        status=result.status,
        error_code=result.error_code,
        provider_request_id=result.provider_request_id,
        provider_model=result.provider_model,
        provider_usage=result.usage,
        model_calls=result.model_calls,
        validated_output=(result.output.model_dump(mode="json") if result.output else None),
    )
    _attach_sources(run, evidence)
    if result.output is not None:
        for event_index, event in enumerate(result.output.events):
            for signal in event.signals:
                run.observations.append(
                    _observation(
                        run,
                        event_index=event_index,
                        signal=signal,
                        event=event,
                    )
                )
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if result.status != "succeeded":
            raise
        existing = _successful_run(db, evidence, result.cache_key)
        if existing is None:
            raise
        _attach_sources(existing, evidence)
        db.commit()
        db.refresh(existing)
        return PersistedExtraction(run=existing, created=False)
    db.refresh(run)
    return PersistedExtraction(run=run, created=True)
