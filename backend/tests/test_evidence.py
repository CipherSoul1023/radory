from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models import SearchQuery, SearchResult
from app.search.engine import create_search_job
from app.search.evidence import (
    EvidenceUnavailable,
    EvidenceWorkspaceMismatch,
    group_identical_evidence,
    prepare_search_result,
    source_url_parts,
)


@pytest.fixture
def evidence_results(search_db, search_workspace):
    job = create_search_job(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        initiated_by_user_id=search_workspace["user"].id,
    ).job
    queries = list(search_db.scalars(select(SearchQuery).where(SearchQuery.job_id == job.id)))
    results = []
    for query in queries[:2]:
        query.preferred_domains = ["example.com"]
        query.provider_request_id = "request-example"
        query.provider_usage = {"credits": 1}
        result = SearchResult(
            search_query_id=query.id,
            result_rank=1,
            title="Acme enters South Africa",
            url="https://news.example.com/story?edition=za#article",
            content="Acme plans to enter South Africa.",
            raw_payload={
                "raw_content": "Acme plans to enter South Africa.\r\nIts city is unknown.",
                "published_date": "2026-10-20",
            },
            published_at=datetime(2026, 10, 20, tzinfo=UTC),
            provider_score=0.9,
            provider_result_id="provider-result",
        )
        search_db.add(result)
        results.append(result)
    search_db.commit()
    return results


def test_preparation_maps_persisted_provenance_without_writes(
    search_db, search_workspace, evidence_results
):
    result = evidence_results[0]
    original = deepcopy(result.raw_payload)
    prepared = prepare_search_result(result, workspace_id=search_workspace["workspace"].id)
    source = prepared.sources[0]
    assert source.search_result_id == result.id
    assert source.search_query_id == result.search_query_id
    assert source.search_job_id == result.search_query.job_id
    assert source.workspace_id == result.search_query.job.workspace_id
    assert source.discovery_signal == result.search_query.signal_key
    assert source.query_text == result.search_query.query_text
    assert source.source_hostname == "news.example.com"
    assert source.matched_preferred_domains == ("example.com",)
    assert source.provider_usage == {"credits": 1}
    assert source.provider_score == 0.9
    assert source.provider_request_id == "request-example"
    assert source.result_rank == 1
    assert source.provider_result_id == "provider-result"
    assert prepared.document.content_basis == "raw_content"
    assert prepared.document.blocks[-1].text.endswith("\nIts city is unknown.")
    payload = prepared.document.semantic_payload()
    assert "workspace_id" not in payload
    assert "discovery_signal" not in payload
    assert "provider_score" not in payload
    assert not search_db.dirty and not search_db.new and not search_db.deleted
    source.raw_payload["raw_content"] = "snapshot changed independently"
    assert result.raw_payload == original


@pytest.mark.parametrize("raw_content", [None, "", " \n ", {"unexpected": "type"}])
def test_missing_raw_content_falls_back_to_snippet(evidence_results, raw_content):
    result = evidence_results[0]
    result.raw_payload = {"raw_content": raw_content}
    prepared = prepare_search_result(result, workspace_id=result.search_query.job.workspace_id)
    assert prepared.document.content_basis == "snippet"
    assert prepared.document.blocks[-1].text == result.content


def test_empty_evidence_and_wrong_workspace_are_rejected(evidence_results):
    result = evidence_results[0]
    with pytest.raises(EvidenceWorkspaceMismatch):
        prepare_search_result(result, workspace_id=uuid4())
    result.raw_payload = {}
    result.content = " "
    with pytest.raises(EvidenceUnavailable, match="No usable"):
        prepare_search_result(result, workspace_id=result.search_query.job.workspace_id)


def test_duplicate_inputs_preserve_query_origins_and_are_tenant_scoped(evidence_results):
    workspace_id = evidence_results[0].search_query.job.workspace_id
    items = [
        prepare_search_result(result, workspace_id=workspace_id) for result in evidence_results
    ]
    assert items[0].input_fingerprint == items[1].input_fingerprint
    grouped = group_identical_evidence([*items, items[0]])
    assert len(grouped) == 1
    assert len(grouped[0].sources) == 2
    assert len({source.search_query_id for source in grouped[0].sources}) == 2
    assert len(group_identical_evidence([items[0], replace(items[1], workspace_id=uuid4())])) == 2


@pytest.mark.parametrize("change", ["body", "title", "date", "basis"])
def test_changed_semantic_input_does_not_reuse_extraction(evidence_results, change):
    first, second = evidence_results
    workspace_id = first.search_query.job.workspace_id
    before = prepare_search_result(first, workspace_id=workspace_id)
    if change == "body":
        second.raw_payload = {"raw_content": "Acme cancelled its expansion."}
    elif change == "title":
        second.title = "Update: expansion cancelled"
    elif change == "date":
        second.published_at = datetime(2026, 10, 21, tzinfo=UTC)
    else:
        second.content = first.raw_payload["raw_content"]
        second.raw_payload = {}
    after = prepare_search_result(second, workspace_id=workspace_id)
    assert before.input_fingerprint != after.input_fingerprint
    assert len(group_identical_evidence([before, after])) == 2


def test_domain_boundaries_and_conservative_url_normalization(evidence_results):
    result = evidence_results[0]
    result.url = "https://fakeexample.com/story?edition=za#article"
    prepared = prepare_search_result(result, workspace_id=result.search_query.job.workspace_id)
    assert prepared.sources[0].matched_preferred_domains == ()
    assert prepared.sources[0].normalized_url == "https://fakeexample.com/story?edition=za"
    assert source_url_parts("https://NEWS.EXAMPLE.COM/a?x=1#part") == (
        "news.example.com",
        "https://news.example.com/a?x=1",
    )
    with pytest.raises(EvidenceUnavailable):
        source_url_parts("https://user:password@example.com")
