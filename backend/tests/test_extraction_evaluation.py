from pathlib import Path

import pytest

from app.search.evaluate_extraction import evaluate_prepared_evidence, run_fixture_evaluation
from app.search.evidence import EvidenceBlock, PreparedDocument, PreparedEvidence, fingerprint
from app.search.extractor import SemanticExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "extraction_cases.json"


@pytest.mark.asyncio
async def test_full_offline_pipeline_matches_reviewed_fixture_expectations(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline evaluation must not open a network or database connection")

    monkeypatch.setattr("httpx.AsyncClient", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("app.database.session.get_session", forbidden)
    report = await run_fixture_evaluation(FIXTURES)
    assert report["failed"] == 0
    assert report["passed"] == report["cases"] >= 10
    assert report["live_provider_calls"] == 0
    duplicate = next(row for row in report["results"] if row["case"] == "duplicate_discovery")
    assert duplicate["source_count"] == 2
    assert duplicate["unique_inputs"] == duplicate["model_calls"] == 1
    assert len(duplicate["evaluations"][0]["sources"]) == 2
    mismatch = next(row for row in report["results"] if row["case"] == "misleading_query_closure")
    assert mismatch["evaluations"][0]["sources"][0]["discovery_signal"] == "leadership_buildout"
    event = mismatch["evaluations"][0]["signature"]["events"][0]
    assert event["signals"] == ["business_rescue_closure"]
    empty = next(row for row in report["results"] if row["case"] == "empty_evidence")
    assert empty["model_calls"] == 0


@pytest.mark.asyncio
async def test_explicit_call_budget_is_checked_before_any_provider_call():
    from uuid import uuid4

    class ForbiddenClient:
        async def chat_completion(self, *args, **kwargs):
            raise AssertionError("Budget check must happen before provider calls")

    document = PreparedDocument(
        content_basis="snippet",
        provider_published_at=None,
        blocks=(EvidenceBlock("body", "snippet", "Example evidence"),),
    )
    item = PreparedEvidence(
        workspace_id=uuid4(),
        document=document,
        content_hash="example",
        input_fingerprint=fingerprint(document.semantic_payload()),
        sources=(),
    )
    with pytest.raises(ValueError, match="budget"):
        await evaluate_prepared_evidence(
            [item], SemanticExtractor(ForbiddenClient(), model="offline"), max_model_calls=0
        )
