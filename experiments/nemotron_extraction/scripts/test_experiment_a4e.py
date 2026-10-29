"""Offline checks for A4-E's frozen grounding-prompt experiment."""

from run_experiment_a4e import (
    load_configuration,
    messages_with_addendum,
)
from run_experiment_a4r2 import ThinkingDisabledNebiusClient
from run_pilot_v1 import load_inputs


def test_a4e_is_bounded_to_the_same_five_cases():
    config = load_configuration()
    assert [row["case_id"] for row in config["cases"]] == [
        "pilot-v1-001",
        "pilot-v1-004",
        "pilot-v1-008",
        "pilot-v1-010",
        "pilot-v1-017",
    ]
    assert config["max_live_calls"] == 5
    assert config["retries"] == 0
    assert config["chat_template_kwargs"] == {"enable_thinking": False}


def test_addendum_changes_only_the_system_message():
    config = load_configuration()
    original = load_inputs()[0][2]
    changed = messages_with_addendum(original, config)
    assert changed[1:] == original[1:]
    assert changed[0]["role"] == original[0]["role"] == "system"
    assert changed[0]["content"] != original[0]["content"]
    assert "Never emit the strings null, unknown, unspecified, or N/A" in changed[0]["content"]
    assert "Orbit raised funding to expand" in changed[0]["content"]


def test_provider_payload_changes_only_messages(tmp_path):
    config = load_configuration()
    original = load_inputs()[0][2]
    changed = messages_with_addendum(original, config)
    baseline_client = ThinkingDisabledNebiusClient(
        expected_messages=original,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "baseline-error.json",
    )
    treatment_client = ThinkingDisabledNebiusClient(
        expected_messages=changed,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "treatment-error.json",
    )
    baseline = baseline_client.payload(original, config["model"], config["max_tokens"])
    treatment = treatment_client.payload(changed, config["model"], config["max_tokens"])
    assert baseline["messages"] != treatment["messages"]
    assert {**baseline, "messages": treatment["messages"]} == treatment


def test_acceptance_keeps_grounding_and_semantics_separate():
    target = load_configuration()["acceptance"]
    assert target["backend_valid"] == 5
    assert target["unsupported_literal_fact_errors"] == 0
    assert target["unmatched_evidence_quote_errors"] == 0
    assert target["expected_events"] == target["matched_events"] == 6
    assert target["signal_true_positives"] == 6
    assert target["signal_extra"] == target["signal_missing"] == 0
