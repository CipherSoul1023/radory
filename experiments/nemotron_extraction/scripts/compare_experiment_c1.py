"""Compare C1's fresh B2 holdout with the frozen independent gold answers."""

from __future__ import annotations

import json

from compare_experiment_a5d import technical_metrics
from compare_experiment_b2 import compact_event, match_indexed_events
from compare_pilot_v1 import gold_event, load_jsonl
from run_experiment_c1 import CASE_OUTPUT, CHUNK_OUTPUT, OUT, load_configuration
from run_pilot_v1 import BASE, sha256, write_new

GOLD = BASE / "data_local" / "pilot_v1" / "reference" / "pilot_v1_gold_answers.jsonl"


def compare_case(gold: dict, aggregate: dict) -> dict:
    expected = [gold_event(event) for event in gold["expected"]["events"]]
    predicted = [compact_event(event) for event in aggregate["prediction"]["events"]]
    pairs = match_indexed_events(expected, predicted)
    expected_signals = {signal for event in expected for signal in event["signals"]}
    predicted_signals = {signal for event in predicted for signal in event["signals"]}
    return {
        "case_id": aggregate["case_id"],
        "scoring_set": aggregate["scoring_set"],
        "validation_status": aggregate["validation_status"],
        "expected_outcome": gold["expected"]["outcome"],
        "predicted_outcome": aggregate["prediction"]["outcome"],
        "outcome_match": gold["expected"]["outcome"] == aggregate["prediction"]["outcome"],
        "expected_event_count": len(expected),
        "predicted_event_count": len(predicted),
        "event_count_match": len(expected) == len(predicted),
        "matched_events": len(pairs),
        "missing_events": len(expected) - len(pairs),
        "extra_events": len(predicted) - len(pairs),
        "pairs": [
            {
                "gold_event_index": gold_index,
                "prediction_event_index": prediction_index,
                "expected_company": expected[gold_index]["subject_company"],
                "predicted_company": predicted[prediction_index]["subject_company"],
                "expected_signals": expected[gold_index]["signals"],
                "predicted_signals": predicted[prediction_index]["signals"],
                "predicted_passage_ids": predicted[prediction_index]["passage_ids"],
            }
            for gold_index, prediction_index in pairs
        ],
        "unmatched_gold_event_indices": [
            index for index in range(len(expected)) if index not in {pair[0] for pair in pairs}
        ],
        "unmatched_prediction_event_indices": [
            index for index in range(len(predicted)) if index not in {pair[1] for pair in pairs}
        ],
        "signal_presence": {
            "true_positive": sorted(expected_signals & predicted_signals),
            "extra_vs_gold": sorted(predicted_signals - expected_signals),
            "missing_vs_gold": sorted(expected_signals - predicted_signals),
        },
        "prediction": aggregate["prediction"],
    }


def ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0


def summarize_clear(comparisons: list[dict]) -> dict:
    clear = [row for row in comparisons if row["scoring_set"] == "clear"]
    expected_events = sum(row["expected_event_count"] for row in clear)
    predicted_events = sum(row["predicted_event_count"] for row in clear)
    matched_events = sum(row["matched_events"] for row in clear)
    expected_signals = {
        (row["case_id"], signal)
        for row in clear
        for signal in (
            row["signal_presence"]["true_positive"] + row["signal_presence"]["missing_vs_gold"]
        )
    }
    predicted_signals = {
        (row["case_id"], signal)
        for row in clear
        for signal in (
            row["signal_presence"]["true_positive"] + row["signal_presence"]["extra_vs_gold"]
        )
    }
    signal_tp = len(expected_signals & predicted_signals)
    gold_negative = [row for row in clear if row["expected_event_count"] == 0]
    return {
        "case_count": len(clear),
        "backend_valid_cases": sum(row["validation_status"] == "succeeded" for row in clear),
        "outcome_matches": sum(row["outcome_match"] for row in clear),
        "exact_event_count_cases": sum(row["event_count_match"] for row in clear),
        "expected_events": expected_events,
        "predicted_events": predicted_events,
        "matched_events": matched_events,
        "missing_events": expected_events - matched_events,
        "extra_events": predicted_events - matched_events,
        "event_precision": ratio(matched_events, predicted_events),
        "event_recall": ratio(matched_events, expected_events),
        "signal_true_positives": signal_tp,
        "signal_extra": len(predicted_signals - expected_signals),
        "signal_missing": len(expected_signals - predicted_signals),
        "signal_precision": ratio(signal_tp, len(predicted_signals)),
        "signal_recall": ratio(signal_tp, len(expected_signals)),
        "gold_negative_cases": len(gold_negative),
        "gold_negative_false_positive_cases": sum(
            row["predicted_event_count"] > 0 for row in gold_negative
        ),
    }


def main() -> None:
    config, _ = load_configuration()
    chunks = load_jsonl(CHUNK_OUTPUT)
    aggregates = load_jsonl(CASE_OUTPUT)
    expected_ids = [case["case_id"] for case in config["cases"]]
    if [row["case_id"] for row in aggregates] != expected_ids:
        raise ValueError("C1 case aggregates are missing or out of order")
    if len(chunks) != config["max_live_calls"]:
        raise ValueError("C1 chunk responses are incomplete")
    if sha256(GOLD) != config["gold_sha256"]:
        raise ValueError("Frozen gold answers changed")
    gold = {row["case_id"]: row for row in load_jsonl(GOLD)}
    comparisons = [compare_case(gold[row["case_id"]], row) for row in aggregates]
    clear = summarize_clear(comparisons)
    technical = technical_metrics(chunks)
    invalid_references = sum(
        len(row["validation_checks"]["invalid_passage_references"]) for row in chunks
    )
    target = config["acceptance"]
    technical_gate = (
        len(aggregates) == target["case_count"]
        and technical["chunk_calls"] == target["chunk_calls"]
        and technical["parseable_json"] == target["parseable_json"]
        and technical["typed_schema"] == target["typed_schema"]
        and technical["backend_valid_chunks"] == target["backend_valid_chunks"]
        and technical["truncations"] == target["truncations"]
        and invalid_references == target["invalid_passage_references"]
        and sum(row["validation_status"] == "succeeded" for row in aggregates)
        == target["backend_valid_case_aggregates"]
    )
    semantic_gate = (
        clear["case_count"] == target["clear_case_count"]
        and clear["exact_event_count_cases"] >= target["clear_exact_event_count_cases_min"]
        and clear["outcome_matches"] >= target["clear_outcome_matches_min"]
        and clear["event_precision"] >= target["clear_event_precision_min"]
        and clear["event_recall"] >= target["clear_event_recall_min"]
        and clear["signal_precision"] >= target["clear_signal_precision_min"]
        and clear["signal_recall"] >= target["clear_signal_recall_min"]
        and clear["gold_negative_false_positive_cases"]
        <= target["clear_gold_negative_false_positive_cases_max"]
    )
    metrics = {
        "experiment_id": config["experiment_id"],
        "technical": technical,
        "invalid_passage_references": invalid_references,
        "backend_valid_case_aggregates": sum(
            row["validation_status"] == "succeeded" for row in aggregates
        ),
        "clear_semantics": clear,
        "manual_review_case_count": sum(
            row["scoring_set"] == "manual_review" for row in comparisons
        ),
        "technical_gate": technical_gate,
        "semantic_gate_before_manual_review": semantic_gate,
        "overall_gate_before_manual_review": technical_gate and semantic_gate,
    }
    with (OUT / "comparison.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for comparison in comparisons:
            stream.write(json.dumps(comparison, ensure_ascii=False) + "\n")
    write_new(OUT / "metrics.json", metrics)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
