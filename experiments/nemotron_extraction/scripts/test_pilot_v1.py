"""Offline checks for the disposable live-pilot harness."""

import asyncio
import json

import pytest
from compare_pilot_v1 import compare_case, match_events, summarize
from run_pilot_v1 import (
    RecordingClient,
    SemanticExtractionInput,
    SemanticExtractor,
    diagnostics,
    load_inputs,
)


def test_requests_match_frozen_inputs_without_discovery_context():
    prepared = load_inputs()
    assert len(prepared) == 24
    for _, _, messages in prepared:
        payload = json.loads(messages[1]["content"])
        assert set(payload) == {
            "schema_version",
            "content_basis",
            "coverage",
            "provider_published_at",
            "blocks",
        }


def test_recording_client_rejects_changed_requests_before_call(tmp_path):
    class NeverCalled:
        async def chat_completion(self, *args, **kwargs):
            raise AssertionError("Network boundary must not be reached")

    client = RecordingClient(NeverCalled(), [{"content": "frozen"}], tmp_path / "response.json")
    with pytest.raises(ValueError, match="audited"):
        asyncio.run(client.chat_completion([{"content": "changed"}]))
    assert client.calls == 0


def test_invalid_output_retained_and_no_retry(tmp_path):
    _, evidence, messages = load_inputs()[0]
    response = {"choices": [{"finish_reason": "stop", "message": {"content": "not JSON"}}]}

    class FakeClient:
        async def chat_completion(self, *args, **kwargs):
            return response

    raw_path = tmp_path / "raw.json"
    client = RecordingClient(FakeClient(), messages, raw_path)
    result = asyncio.run(SemanticExtractor(client, model="offline-test").extract(evidence))
    assert result.status == "failed"
    assert result.error_code == "invalid_output_schema"
    assert json.loads(raw_path.read_text(encoding="utf-8")) == response
    assert client.calls == 1
    with pytest.raises(ValueError, match="retries"):
        asyncio.run(client.chat_completion(messages))


def test_diagnostics_distinguish_empty_success_from_malformed_output():
    _, evidence, _ = load_inputs()[0]
    semantic = SemanticExtractionInput.from_document(evidence.document)
    response = {"choices": [{"message": {"content": '{"outcome":"assessed","events":[]}'}}]}
    checks = diagnostics(response, semantic)
    assert checks["typed_schema"]
    assert checks["quotes_match_input"]
    assert checks["quote_count"] == 0
    assert not diagnostics(None, semantic)["json_object"]


def test_event_alignment_ignores_order():
    events = [
        {
            "subject_company": name,
            "signals": ["office_opening"],
            "timing": [],
            "quotes": [name + " opens office"],
        }
        for name in ("alpha", "beta")
    ]
    assert match_events(events, list(reversed(events))) == [(0, 1), (1, 0)]


def test_failed_output_is_not_counted_as_correct_zero_event_rejection():
    gold = {"case_id": "pilot-v1-010", "expected": {"outcome": "assessed", "events": []}}
    saved = {
        "prediction": None,
        "input_fingerprint": "test",
        "validation_status": "failed",
        "error": "invalid_output_schema",
        "validation_checks": {"typed_schema": False},
    }
    row = compare_case(gold, saved)
    metrics = summarize([row])
    assert row["predicted_event_count"] is None
    assert metrics["zero_event_cases"] == 1
    assert metrics["zero_event_cases_correct"] == 0
    assert metrics["outcome_matches"] == 0
