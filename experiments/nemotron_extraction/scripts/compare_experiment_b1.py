"""Compare B1 compact detection with A5-R and frozen case-008 gold."""

from __future__ import annotations

import json

from compare_experiment_a5d import technical_metrics
from compare_pilot_v1 import gold_event, load_jsonl, norm
from run_experiment_a5r import OUT as A5R_OUT
from run_experiment_b1 import ARM, OUT, load_configuration
from run_pilot_v1 import BASE, write_new


def compact_event(event: dict) -> dict:
    return {
        "subject_company": norm(event["subject_company"]["value"]),
        "signals": sorted(signal["signal_key"] for signal in event["signals"]),
        "timing": [],
        "quotes": [
            quote["quote"]
            for quote in event["subject_company"]["evidence"]
            + [quote for signal in event["signals"] for quote in signal["evidence"]]
        ],
    }


def companies_match(expected: str, predicted: str) -> bool:
    return expected == predicted or expected in predicted or predicted in expected


def match_compact_events(expected: list[dict], predicted: list[dict]) -> list[tuple[int, int]]:
    candidates = []
    for gold_index, gold in enumerate(expected):
        for prediction_index, candidate in enumerate(predicted):
            if not companies_match(gold["subject_company"], candidate["subject_company"]):
                continue
            signal_overlap = len(set(gold["signals"]) & set(candidate["signals"]))
            quote_overlap = len(set(gold["quotes"]) & set(candidate["quotes"]))
            candidates.append((signal_overlap, quote_overlap, gold_index, prediction_index))
    pairs = []
    used_gold = set()
    used_predictions = set()
    for _, _, gold_index, prediction_index in sorted(candidates, reverse=True):
        if gold_index in used_gold or prediction_index in used_predictions:
            continue
        pairs.append((gold_index, prediction_index))
        used_gold.add(gold_index)
        used_predictions.add(prediction_index)
    return sorted(pairs)


def compare_compact(gold: dict, prediction: dict) -> dict:
    expected = [gold_event(event) for event in gold["expected"]["events"]]
    predicted = [compact_event(event) for event in prediction["events"]]
    pairs = match_compact_events(expected, predicted)
    expected_signals = {signal for event in expected for signal in event["signals"]}
    predicted_signals = {signal for event in predicted for signal in event["signals"]}
    return {
        "expected_events": len(expected),
        "predicted_events": len(predicted),
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
            }
            for gold_index, prediction_index in pairs
        ],
        "signal_presence": {
            "true_positive": sorted(expected_signals & predicted_signals),
            "extra_vs_gold": sorted(predicted_signals - expected_signals),
            "missing_vs_gold": sorted(expected_signals - predicted_signals),
        },
    }


def main() -> None:
    config, _ = load_configuration()
    chunks = load_jsonl(OUT / f"{ARM}_chunk_predictions.jsonl")
    if [row["chunk_id"] for row in chunks] != ["chunk-001", "chunk-002"]:
        raise ValueError("B1 requires both ordered chunk responses")
    aggregate = json.loads((OUT / "aggregate.json").read_text(encoding="utf-8"))
    gold = {
        row["case_id"]: row
        for row in load_jsonl(BASE / "data_local/pilot_v1/reference/pilot_v1_gold_answers.jsonl")
    }
    case_id = config["source_case_id"]
    comparison = compare_compact(gold[case_id], aggregate["prediction"])
    technical = technical_metrics(chunks)
    target = config["acceptance"]
    unmatched_quotes = sum(len(row["validation_checks"]["unmatched_quotes"]) for row in chunks)
    signals = comparison["signal_presence"]
    technical_gate = (
        technical["chunk_calls"] == target["chunk_calls"]
        and technical["parseable_json"] == target["parseable_json"]
        and technical["typed_schema"] == target["typed_schema"]
        and technical["backend_valid_chunks"] == target["backend_valid_chunks"]
        and technical["truncations"] == target["truncations"]
        and aggregate["validation_status"]
        == ("succeeded" if target["aggregate_backend_valid"] else "failed")
        and unmatched_quotes == target["unmatched_evidence_quotes"]
    )
    semantic_gate = (
        comparison["expected_events"] == target["expected_events"]
        and comparison["matched_events"] == target["matched_events"]
        and comparison["extra_events"] == target["extra_events"]
        and len(signals["true_positive"]) == target["signal_true_positives"]
        and len(signals["extra_vs_gold"]) == target["signal_extra"]
        and len(signals["missing_vs_gold"]) == target["signal_missing"]
    )
    a5r = json.loads((A5R_OUT / "aggregate.json").read_text(encoding="utf-8"))
    metrics = {
        "source_case_id": case_id,
        "a5r_verbose_baseline": {
            "accepted_events": len(a5r["prediction"]["events"]),
            "validation_status": a5r["validation_status"],
        },
        "b1_compact_detection": {
            "technical": technical,
            "unmatched_evidence_quotes": unmatched_quotes,
            "aggregate_validation_status": aggregate["validation_status"],
            "semantic": comparison,
            "technical_gate": technical_gate,
            "semantic_gate_before_manual_review": semantic_gate,
        },
    }
    write_new(OUT / "metrics.json", metrics)
    write_new(OUT / "comparison.json", comparison)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
