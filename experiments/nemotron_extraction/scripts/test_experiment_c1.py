"""Offline checks for C1's frozen B2 holdout."""

import json

from compare_experiment_c1 import summarize_clear
from run_experiment_b2 import IndexedCompactClient, IndexedCompactOutput, messages
from run_experiment_c1 import (
    EXPERIMENT_A_PLAN,
    aggregate_case,
    load_configuration,
)


def test_c1_selection_is_disjoint_from_experiment_a():
    config, cases = load_configuration()
    experiment_a = json.loads(EXPERIMENT_A_PLAN.read_text(encoding="utf-8"))
    tuning_ids = {case["case_id"] for case in experiment_a["cases"]}
    selected_ids = [case["row"]["case_id"] for case in cases]
    assert len(selected_ids) == len(set(selected_ids)) == 8
    assert not tuning_ids.intersection(selected_ids)
    assert selected_ids == [case["case_id"] for case in config["cases"]]


def test_c1_has_frozen_six_clear_two_review_and_sixteen_chunks():
    config, cases = load_configuration()
    assert sum(case["plan"]["scoring_set"] == "clear" for case in cases) == 6
    assert sum(case["plan"]["scoring_set"] == "manual_review" for case in cases) == 2
    assert sum(len(case["chunks"]) for case in cases) == config["max_live_calls"] == 16
    assert all(
        len(chunk["document"].blocks[-1].text) <= config["max_chunk_characters"]
        for case in cases
        for chunk in case["chunks"]
    )


def test_c1_uses_b2_contract_and_default_reasoning(tmp_path):
    config, cases = load_configuration()
    provider_messages = messages(cases[0]["chunks"][0]["indexed"])
    payload = IndexedCompactClient(
        expected_messages=provider_messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "error.json",
    ).payload(provider_messages, config["model"], config["max_tokens"])
    assert payload["response_format"]["json_schema"]["name"] == (
        "radory_indexed_compact_event_detection_v1"
    )
    assert "chat_template_kwargs" not in payload
    assert "reasoning_budget" not in payload
    assert "reasoning_effort" not in payload
    assert payload["max_tokens"] == 4096


def test_c1_aggregation_preserves_events_without_semantic_deduplication():
    config, cases = load_configuration()
    case = cases[0]
    passage = next(
        passage
        for passage in case["chunks"][0]["indexed"].passages
        if "Global Political Solutions, LLC" in passage.text
    )
    event = {
        "subject_company": {
            "value": "Global Political Solutions, LLC",
            "evidence_passage_ids": [passage.passage_id],
        },
        "signals": [
            {
                "signal_key": "office_opening",
                "evidence_passage_ids": [passage.passage_id],
            }
        ],
    }
    output = IndexedCompactOutput.model_validate({"outcome": "assessed", "events": [event]})
    aggregate = aggregate_case(config, case, [output])
    assert aggregate["validation_status"] == "succeeded"
    assert aggregate["prediction"]["events"] == [event]
    assert aggregate["aggregation"]["deduplication"] == "none"


def test_c1_empty_aggregation_prefers_assessed_if_any_chunk_was_assessable():
    config, cases = load_configuration()
    case = cases[1]
    assessed = IndexedCompactOutput(outcome="assessed", events=[])
    insufficient = IndexedCompactOutput(outcome="insufficient_evidence", events=[])
    aggregate = aggregate_case(config, case, [insufficient, assessed])
    assert aggregate["prediction"] == {"outcome": "assessed", "events": []}


def test_c1_aggregate_accepts_more_than_one_hundred_bounded_passages():
    config, cases = load_configuration()
    case = next(item for item in cases if item["row"]["case_id"] == "pilot-v1-014")
    assert sum(len(chunk["indexed"].passages) for chunk in case["chunks"]) > 100
    outputs = [IndexedCompactOutput(outcome="assessed", events=[]) for _ in case["chunks"]]
    aggregate = aggregate_case(config, case, outputs)
    assert aggregate["validation_status"] == "succeeded"
    assert aggregate["prediction"] == {"outcome": "assessed", "events": []}


def test_c1_acceptance_gate_was_frozen_before_predictions():
    config, _ = load_configuration()
    target = config["acceptance"]
    assert target["chunk_calls"] == target["parseable_json"] == 16
    assert target["backend_valid_chunks"] == 16
    assert target["truncations"] == target["invalid_passage_references"] == 0
    assert target["clear_event_precision_min"] == target["clear_event_recall_min"] == 0.8
    assert target["clear_signal_precision_min"] == target["clear_signal_recall_min"] == 0.8
    assert target["clear_gold_negative_false_positive_cases_max"] == 0


def test_c1_summary_uses_case_signal_presence_units():
    rows = [
        {
            "case_id": "positive",
            "scoring_set": "clear",
            "validation_status": "succeeded",
            "outcome_match": True,
            "event_count_match": True,
            "expected_event_count": 1,
            "predicted_event_count": 1,
            "matched_events": 1,
            "signal_presence": {
                "true_positive": ["office_opening"],
                "extra_vs_gold": [],
                "missing_vs_gold": [],
            },
        },
        {
            "case_id": "negative",
            "scoring_set": "clear",
            "validation_status": "succeeded",
            "outcome_match": True,
            "event_count_match": True,
            "expected_event_count": 0,
            "predicted_event_count": 0,
            "matched_events": 0,
            "signal_presence": {
                "true_positive": [],
                "extra_vs_gold": [],
                "missing_vs_gold": [],
            },
        },
    ]
    summary = summarize_clear(rows)
    assert summary["event_precision"] == summary["event_recall"] == 1.0
    assert summary["signal_precision"] == summary["signal_recall"] == 1.0
    assert summary["gold_negative_false_positive_cases"] == 0
