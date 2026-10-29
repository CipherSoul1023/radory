"""Offline checks for the bounded enable_thinking provider probe."""

from run_enable_thinking_compatibility import (
    ARMS,
    load_plan,
    payload_for_arm,
    response_summary,
)


def provider_response(*, reasoning_tokens=0, content='{"answer":1517}'):
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": content},
            }
        ],
        "usage": {
            "completion_tokens": 20,
            "completion_tokens_details": {"reasoning_tokens": reasoning_tokens},
        },
    }


def test_plan_is_bounded_to_two_calls_without_radory_evidence():
    plan = load_plan()
    assert plan["max_live_calls"] == 2
    assert plan["retries"] == 0
    assert "Radory" not in plan["synthetic_task"]


def test_treatment_changes_only_chat_template_kwargs():
    plan = load_plan()
    baseline = payload_for_arm(plan, ARMS[0])
    treatment = payload_for_arm(plan, ARMS[1])
    assert "chat_template_kwargs" not in baseline
    assert treatment["chat_template_kwargs"] == {"enable_thinking": False}
    assert baseline == {
        key: value for key, value in treatment.items() if key != "chat_template_kwargs"
    }


def test_accepted_zero_reasoning_and_correct_answer_is_effective():
    plan = load_plan()
    result = response_summary(ARMS[1], 200, provider_response(), plan)
    assert result["classification"] == "effective"


def test_rejection_reasoning_and_missing_usage_are_distinct():
    plan = load_plan()
    rejected = response_summary(ARMS[1], 400, {"error": {}}, plan)
    reasoning = response_summary(ARMS[1], 200, provider_response(reasoning_tokens=99), plan)
    inconclusive = response_summary(
        ARMS[1],
        200,
        {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]},
        plan,
    )
    assert rejected["classification"] == "rejected"
    assert reasoning["classification"] == "accepted_but_ineffective"
    assert inconclusive["classification"] == "inconclusive"
