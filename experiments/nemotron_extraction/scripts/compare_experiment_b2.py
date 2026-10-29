"""Compare B2 indexed compact detection with B1 and frozen case-008 gold."""

from __future__ import annotations

import json
import re

from compare_experiment_a5d import technical_metrics
from compare_pilot_v1 import gold_event, load_jsonl, norm
from run_experiment_b1 import ARM as B1_ARM
from run_experiment_b1 import OUT as B1_OUT
from run_experiment_b2 import ARM, OUT, load_configuration
from run_pilot_v1 import BASE, write_new


def compact_event(event: dict) -> dict:
    return {
        "subject_company": norm(event["subject_company"]["value"]),
        "signals": sorted(signal["signal_key"] for signal in event["signals"]),
        "timing": [],
        "quotes": [],
        "passage_ids": sorted(
            {
                *event["subject_company"]["evidence_passage_ids"],
                *(
                    passage_id
                    for signal in event["signals"]
                    for passage_id in signal["evidence_passage_ids"]
                ),
            }
        ),
    }


def companies_match(expected: str, predicted: str) -> bool:
    if expected == predicted or expected in predicted or predicted in expected:
        return True
    expected_tokens = set(re.findall(r"[a-z0-9]+", expected))
    predicted_tokens = set(re.findall(r"[a-z0-9]+", predicted))
    union = expected_tokens | predicted_tokens
    return bool(union) and len(expected_tokens & predicted_tokens) / len(union) >= 0.7


def match_indexed_events(expected: list[dict], predicted: list[dict]) -> list[tuple[int, int]]:
    candidates = []
    for gold_index, gold in enumerate(expected):
        for prediction_index, candidate in enumerate(predicted):
            if not companies_match(gold["subject_company"], candidate["subject_company"]):
                continue
            signal_overlap = len(set(gold["signals"]) & set(candidate["signals"]))
            candidates.append((signal_overlap, gold_index, prediction_index))
    pairs = []
    used_gold = set()
    used_predictions = set()
    for _, gold_index, prediction_index in sorted(candidates, reverse=True):
        if gold_index in used_gold or prediction_index in used_predictions:
            continue
        pairs.append((gold_index, prediction_index))
        used_gold.add(gold_index)
        used_predictions.add(prediction_index)
    return sorted(pairs)


def compare_compact(gold: dict, prediction: dict) -> dict:
    expected = [gold_event(event) for event in gold["expected"]["events"]]
    predicted = [compact_event(event) for event in prediction["events"]]
    pairs = match_indexed_events(expected, predicted)
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
                "predicted_passage_ids": predicted[prediction_index]["passage_ids"],
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
        raise ValueError("B2 requires both ordered chunk responses")
    aggregate = json.loads((OUT / "aggregate.json").read_text(encoding="utf-8"))
    gold = {
        row["case_id"]: row
        for row in load_jsonl(BASE / "data_local/pilot_v1/reference/pilot_v1_gold_answers.jsonl")
    }
    case_id = config["source_case_id"]
    comparison = compare_compact(gold[case_id], aggregate["prediction"])
    technical = technical_metrics(chunks)
    target = config["acceptance"]
    invalid_references = sum(
        len(row["validation_checks"]["invalid_passage_references"]) for row in chunks
    )
    signals = comparison["signal_presence"]
    technical_gate = (
        technical["chunk_calls"] == target["chunk_calls"]
        and technical["parseable_json"] == target["parseable_json"]
        and technical["typed_schema"] == target["typed_schema"]
        and technical["backend_valid_chunks"] == target["backend_valid_chunks"]
        and technical["truncations"] == target["truncations"]
        and aggregate["validation_status"]
        == ("succeeded" if target["aggregate_backend_valid"] else "failed")
        and invalid_references == target["invalid_passage_references"]
    )
    semantic_gate = (
        comparison["expected_events"] == target["expected_events"]
        and comparison["matched_events"] == target["matched_events"]
        and comparison["extra_events"] == target["extra_events"]
        and len(signals["true_positive"]) == target["signal_true_positives"]
        and len(signals["extra_vs_gold"]) == target["signal_extra"]
        and len(signals["missing_vs_gold"]) == target["signal_missing"]
    )
    b1_chunks = load_jsonl(B1_OUT / f"{B1_ARM}_chunk_predictions.jsonl")
    b1_metrics = json.loads((B1_OUT / "metrics.json").read_text(encoding="utf-8"))[
        "b1_compact_detection"
    ]
    metrics = {
        "source_case_id": case_id,
        "b1_exact_quote_baseline": {
            "technical": technical_metrics(b1_chunks),
            "unmatched_evidence_quotes": b1_metrics["unmatched_evidence_quotes"],
            "matched_events": b1_metrics["semantic"]["matched_events"],
            "extra_events": b1_metrics["semantic"]["extra_events"],
        },
        "b2_indexed_compact_detection": {
            "technical": technical,
            "invalid_passage_references": invalid_references,
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
