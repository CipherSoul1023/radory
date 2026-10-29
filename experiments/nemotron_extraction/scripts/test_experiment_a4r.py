"""Offline checks for A4-R's frozen reasoning-isolation design."""

from __future__ import annotations

import asyncio

from run_experiment_a3 import response_format as a3_response_format
from run_experiment_a4r import (
    ARMS,
    DirectiveRecordingClient,
    load_configuration,
    messages_for_arm,
    response_format,
)
from run_pilot_v1 import load_inputs


def test_a4r_is_bounded_to_two_failures_and_three_controls():
    config, _ = load_configuration()
    assert [row["case_id"] for row in config["cases"]] == [
        "pilot-v1-001",
        "pilot-v1-004",
        "pilot-v1-008",
        "pilot-v1-010",
        "pilot-v1-017",
    ]
    assert sum(row["role"] == "a3_reasoning_truncation" for row in config["cases"]) == 2
    assert sum(row["role"] == "successful_control" for row in config["cases"]) == 3
    assert len(config["cases"]) * len(ARMS) == config["max_live_calls"] == 10
    assert config["retries"] == 0


def test_no_think_changes_only_first_line_of_system_message():
    messages = load_inputs()[0][2]
    default = messages_for_arm(messages, ARMS[0])
    no_think = messages_for_arm(messages, ARMS[1])
    assert default == messages
    assert no_think[0]["role"] == "system"
    assert no_think[0]["content"] == "/no_think\n" + default[0]["content"]
    assert no_think[1:] == default[1:]


def test_schema_model_budget_and_thresholds_remain_frozen():
    config, _ = load_configuration()
    assert response_format() == a3_response_format()
    assert config["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert config["max_tokens"] == 4096
    target = config["acceptance_for_no_think"]
    assert target["typed_schema"] == target["backend_valid"] == 5
    assert target["truncations"] == target["character_collapse_cases"] == 0
    assert target["minimum_reasoning_token_reduction_fraction"] == 0.75


def test_no_think_is_injected_at_provider_boundary(tmp_path):
    class FakeProvider:
        def __init__(self):
            self.messages = None

        async def chat_completion(self, messages, model=None, max_tokens=None):
            self.messages = messages
            return {"choices": [{"message": {"content": "{}"}}]}

    original = load_inputs()[0][2]
    modified = messages_for_arm(original, ARMS[1])
    provider = FakeProvider()
    recorder = DirectiveRecordingClient(
        provider,
        original,
        modified,
        tmp_path / "response.json",
    )

    asyncio.run(
        recorder.chat_completion(original, model="frozen-model", max_tokens=4096)
    )

    assert recorder.calls == 1
    assert provider.messages == modified
    assert provider.messages[0]["content"].startswith("/no_think\n")
