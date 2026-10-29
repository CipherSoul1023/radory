"""Offline checks for A4-R2's frozen real-evidence request design."""

from run_experiment_a3 import A3NebiusClient
from run_experiment_a4r2 import (
    ThinkingDisabledNebiusClient,
    load_configuration,
)
from run_pilot_v1 import load_inputs


def test_a4r2_is_bounded_to_two_recoveries_and_three_controls():
    config = load_configuration()
    assert [row["case_id"] for row in config["cases"]] == [
        "pilot-v1-001",
        "pilot-v1-004",
        "pilot-v1-008",
        "pilot-v1-010",
        "pilot-v1-017",
    ]
    assert sum(row["role"] == "a3_reasoning_truncation" for row in config["cases"]) == 2
    assert sum(row["role"] == "successful_control" for row in config["cases"]) == 3
    assert config["max_live_calls"] == 5
    assert config["retries"] == 0


def test_treatment_adds_only_enable_thinking_false(tmp_path):
    config = load_configuration()
    messages = load_inputs()[0][2]
    kwargs = {
        "expected_messages": messages,
        "model": config["model"],
        "max_tokens": config["max_tokens"],
        "error_path": tmp_path / "error.json",
    }
    baseline = A3NebiusClient(**kwargs).payload(messages, config["model"], config["max_tokens"])
    treatment = ThinkingDisabledNebiusClient(**kwargs).payload(
        messages, config["model"], config["max_tokens"]
    )
    assert "chat_template_kwargs" not in baseline
    assert treatment["chat_template_kwargs"] == {"enable_thinking": False}
    assert baseline == {
        key: value for key, value in treatment.items() if key != "chat_template_kwargs"
    }


def test_acceptance_requires_all_five_without_reasoning_or_truncation():
    target = load_configuration()["acceptance"]
    assert target["parseable_json"] == 5
    assert target["typed_schema"] == 5
    assert target["backend_valid"] == 5
    assert target["truncations"] == 0
    assert target["cases_with_nonzero_reasoning_tokens"] == 0
    assert target["manual_control_semantic_regressions"] == 0
