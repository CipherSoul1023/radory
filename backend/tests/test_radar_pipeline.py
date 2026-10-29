import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.search import pipeline
from app.search.engine import create_search_job
from app.search.extraction_engine import ExtractionJobResult


def _terminal_job(search_db: Session, search_workspace: dict):
    result = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    )
    result.job.status = "completed"
    search_db.commit()
    return result.job


@pytest.mark.asyncio
async def test_pipeline_claims_once_and_persists_partial_progress(
    monkeypatch,
    search_db: Session,
    search_workspace: dict,
):
    job = _terminal_job(search_db, search_workspace)
    assert pipeline.ready_pipeline_job_ids(search_db) == [job.id]
    assert pipeline.claim_radar_pipeline(search_db, search_job_id=job.id) is True
    assert pipeline.claim_radar_pipeline(search_db, search_job_id=job.id) is False

    extraction = ExtractionJobResult(
        search_job_id=job.id,
        search_results=2,
        evidence_groups=2,
        skipped_results=0,
        model_calls=2,
        reused_extractions=0,
        succeeded_extractions=2,
        failed_extractions=0,
        observations=2,
    )

    async def fake_extract(*args, **kwargs):
        return extraction

    observation_ids = [uuid.uuid4(), uuid.uuid4()]

    async def fake_build(*args, observation_id, **kwargs):
        status = "completed" if observation_id == observation_ids[0] else "failed"
        return SimpleNamespace(status=status), True

    monkeypatch.setattr(pipeline, "extract_search_job", fake_extract)
    monkeypatch.setattr(
        pipeline,
        "_event_seed_observation_ids",
        lambda *args, **kwargs: observation_ids,
    )
    monkeypatch.setattr(pipeline, "build_radar_opportunity", fake_build)

    result = await pipeline.process_radar_pipeline(search_db, search_job_id=job.id)

    assert result.status == "partial_failed"
    assert result.completed_opportunities == 1
    assert result.failed_opportunities == 1
    search_db.refresh(job)
    assert job.pipeline_status == "partial_failed"
    assert job.pipeline_completed_at is not None


def test_pipeline_failure_is_recorded_without_provider_details(
    search_db: Session,
    search_workspace: dict,
):
    job = _terminal_job(search_db, search_workspace)
    assert pipeline.claim_radar_pipeline(search_db, search_job_id=job.id) is True

    pipeline.fail_radar_pipeline(
        search_db,
        search_job_id=job.id,
        error_code="provider_error",
        error_message="Radar post-processing failed",
    )

    search_db.refresh(job)
    assert job.pipeline_status == "failed"
    assert job.pipeline_error_code == "provider_error"
    assert job.pipeline_error_message == "Radar post-processing failed"
    assert job.pipeline_completed_at is not None
