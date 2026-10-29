from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ExtractionRun,
    ExtractionSource,
    SearchJob,
    SearchQuery,
    SearchResult,
    SignalObservation,
)
from app.search.evidence import fingerprint, group_identical_evidence, prepare_search_result
from app.search.extraction_contract import SemanticExtractionOutput
from app.search.extraction_persistence import (
    ExtractionPersistenceError,
    persist_extraction_result,
)
from app.search.extractor import ExtractionResult, extraction_specification

MODEL = "nvidia/nemotron-3-super-120b-a12b"
MAX_OUTPUT_TOKENS = 4096


def prepared_evidence(db: Session, context: dict, *, rank: int = 1):
    profile = context["profile"]
    job = SearchJob(
        workspace_id=context["workspace"].id,
        initiated_by_user_id=context["user"].id,
        brokerage_profile_id=profile.id,
        status="completed",
        pipeline_status="completed",
        country=profile.country,
        market=profile.primary_market,
        configured_submarkets=profile.submarkets,
        resolved_submarket=profile.submarkets[0],
        brokerage_profile_updated_at=profile.updated_at,
        search_context_version=1,
        completed_at=datetime.now(UTC),
    )
    query = SearchQuery(
        job=job,
        signal_key="office_opening",
        query_rank=1,
        query_text="companies opening offices in Johannesburg",
        preferred_domains=["example.com"],
        include_domains_mode="prefer",
        search_depth="advanced",
        max_results=10,
        include_raw_content=True,
        status="succeeded",
        attempt_count=1,
        dispatch_attempt_count=1,
    )
    result = SearchResult(
        search_query=query,
        result_rank=rank,
        title="Acme plans a Johannesburg office",
        url=f"https://example.com/acme-office-{rank}",
        content="Acme plans to open a Johannesburg office next year.",
        provider_score=0.9,
        raw_payload={"raw_content": "Acme plans to open a Johannesburg office next year."},
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return prepare_search_result(result, workspace_id=context["workspace"].id)


def extraction_result(evidence, *, output: SemanticExtractionOutput | None, error=None):
    specification_hash = fingerprint(extraction_specification())
    cache_key = fingerprint(
        {
            "workspace_id": str(evidence.workspace_id),
            "input_fingerprint": evidence.input_fingerprint,
            "specification": specification_hash,
            "model": MODEL,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
    )
    return ExtractionResult(
        status="succeeded" if output is not None else "failed",
        output=output,
        error_code=error,
        cache_key=cache_key,
        model=MODEL,
        specification_fingerprint=specification_hash,
        provider_request_id="provider-request-1",
        provider_model=MODEL,
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        model_calls=1,
    )


def supported_output() -> SemanticExtractionOutput:
    quote = {
        "block_id": "body",
        "quote": "Acme plans to open a Johannesburg office next year.",
    }
    return SemanticExtractionOutput.model_validate(
        {
            "outcome": "assessed",
            "events": [
                {
                    "subject_company": {"value": "Acme", "evidence": [quote]},
                    "related_companies": [],
                    "summary": {
                        "value": "Acme plans a Johannesburg office.",
                        "evidence": [quote],
                    },
                    "signals": [
                        {"signal_key": "office_opening", "evidence": [quote]},
                        {"signal_key": "business_expansion", "evidence": [quote]},
                    ],
                    "stage": {"value": "planned", "evidence": [quote]},
                    "locations": [
                        {
                            "country": None,
                            "market": {"value": "Johannesburg", "evidence": [quote]},
                            "submarket": None,
                            "role": "event_location",
                        }
                    ],
                    "timing": [
                        {
                            "expression": "next year",
                            "precision": "relative",
                            "evidence": [quote],
                        }
                    ],
                    "missing_facts": ["workplace_plans"],
                }
            ],
        }
    )


def test_persists_validated_observations_and_provenance(search_db: Session, search_workspace: dict):
    evidence = prepared_evidence(search_db, search_workspace)
    saved = persist_extraction_result(
        search_db,
        evidence=evidence,
        result=extraction_result(evidence, output=supported_output()),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    assert saved.created is True
    assert saved.run.workspace_id == search_workspace["workspace"].id
    assert saved.run.status == "succeeded"
    assert len(saved.run.sources) == 1
    assert {observation.signal_key for observation in saved.run.observations} == {
        "office_opening",
        "business_expansion",
    }
    assert all(observation.subject_company == "Acme" for observation in saved.run.observations)
    assert all(observation.stage == "planned" for observation in saved.run.observations)


def test_reuses_successful_extraction_without_duplicate_observations(
    search_db: Session, search_workspace: dict
):
    evidence = prepared_evidence(search_db, search_workspace)
    result = extraction_result(evidence, output=supported_output())
    first = persist_extraction_result(
        search_db,
        evidence=evidence,
        result=result,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )
    second = persist_extraction_result(
        search_db,
        evidence=evidence,
        result=result,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    assert first.created is True
    assert second.created is False
    assert second.run.id == first.run.id
    assert search_db.scalar(select(func.count()).select_from(ExtractionRun)) == 1
    assert search_db.scalar(select(func.count()).select_from(SignalObservation)) == 2


def test_identical_evidence_preserves_every_search_result_source(
    search_db: Session, search_workspace: dict
):
    first = prepared_evidence(search_db, search_workspace, rank=1)
    second = prepared_evidence(search_db, search_workspace, rank=2)
    grouped = group_identical_evidence([first, second])
    assert len(grouped) == 1
    assert len(grouped[0].sources) == 2

    saved = persist_extraction_result(
        search_db,
        evidence=grouped[0],
        result=extraction_result(grouped[0], output=supported_output()),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    assert saved.created is True
    assert len(saved.run.sources) == 2
    assert search_db.scalar(select(func.count()).select_from(ExtractionSource)) == 2


def test_assessed_zero_is_a_successful_run_with_no_observations(
    search_db: Session, search_workspace: dict
):
    evidence = prepared_evidence(search_db, search_workspace)
    output = SemanticExtractionOutput(outcome="assessed", events=[])
    saved = persist_extraction_result(
        search_db,
        evidence=evidence,
        result=extraction_result(evidence, output=output),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    assert saved.run.validated_output == {"outcome": "assessed", "events": []}
    assert saved.run.observations == []


def test_failed_extraction_is_recorded_without_observations(
    search_db: Session, search_workspace: dict
):
    evidence = prepared_evidence(search_db, search_workspace)
    saved = persist_extraction_result(
        search_db,
        evidence=evidence,
        result=extraction_result(
            evidence,
            output=None,
            error="invalid_output_schema",
        ),
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    assert saved.run.status == "failed"
    assert saved.run.error_code == "invalid_output_schema"
    assert saved.run.validated_output is None
    assert saved.run.observations == []


def test_rejects_result_that_does_not_match_evidence(search_db: Session, search_workspace: dict):
    evidence = prepared_evidence(search_db, search_workspace)
    result = extraction_result(evidence, output=supported_output())
    mismatched = ExtractionResult(
        **{**result.__dict__, "cache_key": "0" * 64},
    )

    with pytest.raises(ExtractionPersistenceError, match="does not match"):
        persist_extraction_result(
            search_db,
            evidence=evidence,
            result=mismatched,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
