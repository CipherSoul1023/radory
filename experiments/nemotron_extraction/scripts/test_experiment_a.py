"""Offline checks; never send a live request."""

import asyncio
import copy
from types import SimpleNamespace

import httpx
import pytest
import run_experiment_a as experiment
from compare_experiment_a import structural_summary


def test_plan_includes_all_failures_and_six_successful_controls():
    plan = experiment.build_plan()
    assert len(plan["cases"]) == 16
    assert sum(c["role"] == "previous_failure" for c in plan["cases"]) == 10
    assert sum(c["role"] == "successful_control" for c in plan["cases"]) == 6
    assert plan["max_live_calls"] == 32
    assert plan["acceptance_per_arm"]["typed_schema_min"] == 16


def test_payload_changes_only_format_and_budget(tmp_path):
    _, _, messages = experiment.load_inputs()[0]
    client = experiment.StructuredNebiusClient(
        expected_messages=messages,
        model="offline",
        max_tokens=4096,
        error_path=tmp_path / "error.json",
    )
    a1 = client.payload(messages, "offline", 4096)
    assert set(a1) == {"model", "messages", "max_tokens", "response_format"}
    assert a1["messages"] == messages
    assert a1["response_format"]["json_schema"]["schema"] == (
        experiment.SemanticExtractionOutput.model_json_schema()
    )
    a1["response_format"]["json_schema"]["schema"].clear()
    assert client.payload(messages, "offline", 4096)["response_format"]["json_schema"]["schema"]
    bad_messages = copy.deepcopy(messages)
    bad_messages[0]["content"] += "changed prompt"
    with pytest.raises(AssertionError):
        client.payload(bad_messages, "offline", 4096)
    with pytest.raises(AssertionError):
        client.payload(messages, "offline", 8192)


def test_transport_uses_exact_payload_and_forbids_retries(monkeypatch, tmp_path):
    messages = [{"role": "user", "content": "offline evidence"}]
    client = experiment.StructuredNebiusClient(
        expected_messages=messages,
        model="offline",
        max_tokens=8192,
        error_path=tmp_path / "error.json",
    )
    client.settings = SimpleNamespace(
        nebius_base_url="https://provider.example/v1", nebius_api_key="offline-placeholder"
    )
    captured = []

    class FakeHTTP:
        def __init__(self, *, timeout):
            assert timeout == 60

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, *, headers, json):
            captured.append((url, json))
            return httpx.Response(200, json={"choices": []}, request=httpx.Request("POST", url))

    monkeypatch.setattr(experiment.httpx, "AsyncClient", FakeHTTP)
    asyncio.run(client.chat_completion(messages, model="offline", max_tokens=8192))
    assert captured[0][0] == "https://provider.example/v1/chat/completions"
    assert captured[0][1] == client.payload(messages, "offline", 8192)
    with pytest.raises(AssertionError, match="repeated"):
        asyncio.run(client.chat_completion(messages, model="offline", max_tokens=8192))
    assert len(captured) == 1


def metric_rows():
    return [
        {
            "case_id": f"case-{i}",
            "validation_status": "succeeded",
            "error": None,
            "validation_checks": {
                "json_object": True,
                "typed_schema": True,
                "quotes_match_input": True,
            },
            "raw_response": {"choices": [{"finish_reason": "stop"}]},
            "duration_seconds": 0,
        }
        for i in range(16)
    ]


def test_acceptance_requires_all_controls_to_remain_valid():
    rows = metric_rows()
    controls = {f"case-{i}" for i in range(6)}
    assert structural_summary(rows, controls)["technical_gate_passed"]
    rows[0]["validation_status"] = "failed"
    rows[0]["error"] = "unmatched_evidence_quote"
    summary = structural_summary(rows, controls)
    assert summary["backend_valid"] == 15
    assert not summary["technical_gate_passed"]


def test_one_backend_failure_allowed_but_no_schema_failure():
    rows = metric_rows()
    controls = {f"case-{i}" for i in range(6)}
    rows[10]["validation_status"] = "failed"
    rows[10]["error"] = "unmatched_evidence_quote"
    assert structural_summary(rows, controls)["technical_gate_passed"]
    rows[10]["validation_checks"]["typed_schema"] = False
    assert not structural_summary(rows, controls)["technical_gate_passed"]
