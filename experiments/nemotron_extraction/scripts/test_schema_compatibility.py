"""Offline checks for the response-format compatibility probe."""

from __future__ import annotations

from compare_schema_compatibility import anchor_match, free_text_values
from run_schema_compatibility import MODES, load_plan, prepare_case, response_format


def test_plan_is_bounded_and_messages_are_identical_across_modes():
    plan = load_plan()
    assert len(plan["cases"]) * len(MODES) == 12
    for row in plan["cases"]:
        _, messages = prepare_case(row)
        assert row["expected"] not in messages
        assert messages == prepare_case(row)[1]


def test_only_pattern_keywords_change_between_strict_modes():
    current = response_format("strict_current")["json_schema"]["schema"]
    changed = response_format("strict_without_patterns")["json_schema"]["schema"]

    def remove_patterns(value):
        if isinstance(value, dict):
            return {key: remove_patterns(child) for key, child in value.items() if key != "pattern"}
        if isinstance(value, list):
            return [remove_patterns(child) for child in value]
        return value

    assert current != changed
    assert remove_patterns(current) == changed
    assert "pattern" not in str(changed)


def test_json_object_mode_has_no_schema_payload():
    assert response_format("json_object") == {"type": "json_object"}


def test_collapsed_values_and_synthetic_anchors_are_detected():
    collapsed = {
        "outcome": "assessed",
        "events": [
            {
                "subject_company": {"value": "N", "evidence": []},
                "summary": {"value": "N", "evidence": []},
                "signals": [{"signal_key": "office_opening", "evidence": []}],
                "stage": {"value": "planned", "evidence": []},
                "locations": [],
                "timing": [],
            }
        ],
    }
    assert free_text_values(collapsed) == ["N", "N"]
    expected = load_plan()["cases"][0]["expected"]
    assert anchor_match(collapsed, expected)[0] is False


def test_negative_control_requires_assessed_zero_events():
    expected = load_plan()["cases"][3]["expected"]
    assert anchor_match({"outcome": "assessed", "events": []}, expected)[0] is True
    assert anchor_match({"outcome": "insufficient_evidence", "events": []}, expected)[0] is False
