"""Offline comparison only. Requires all 24 predictions to have been saved first."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
MANUAL_CASES = {f"pilot-v1-{i:03d}" for i in (7, 9, 12, 14, 15, 18, 20)}
FIELDS = ("subject_company", "signals", "stage", "geography", "timing")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()]


def norm(value: str) -> str:
    return " ".join(value.casefold().split())


def gold_event(event: dict) -> dict:
    return {
        "subject_company": norm(event["subject_company"]),
        "signals": sorted(event["signals"]),
        "stage": event["stage"],
        "geography": {
            field: [norm(value)] if (value := event["geography"].get(field)) else []
            for field in ("country", "market", "submarket")
        },
        "timing": sorted((norm(t["expression"]), t["precision"]) for t in event["timing"]),
        "summary": event["summary"],
        "quotes": event["supporting_evidence"],
    }


def predicted_event(event: dict) -> dict:
    return {
        "subject_company": norm(event["subject_company"]["value"]),
        "signals": sorted(s["signal_key"] for s in event["signals"]),
        "stage": event["stage"]["value"],
        "geography": {
            field: sorted(
                {norm(loc[field]["value"]) for loc in event["locations"] if loc[field] is not None}
            )
            for field in ("country", "market", "submarket")
        },
        "timing": sorted((norm(t["expression"]), t["precision"]) for t in event["timing"]),
        "summary": event["summary"]["value"],
        "quotes": [q["quote"] for q in event["summary"]["evidence"]],
    }


def match_events(expected: list[dict], predicted: list[dict]) -> list[tuple[int, int]]:
    """Maximum-weight one-to-one alignment; event order does not affect scoring."""

    def weight(g, p):
        same_company = g["subject_company"] == p["subject_company"]
        g_tokens = set(re.findall(r"\w+", g["subject_company"]))
        p_tokens = set(re.findall(r"\w+", p["subject_company"]))
        company_overlap = len(g_tokens & p_tokens) / max(1, len(g_tokens | p_tokens))
        signal_overlap = len(set(g["signals"]) & set(p["signals"]))
        timing_overlap = len(set(g["timing"]) & set(p["timing"]))
        quote_overlap = any(a in b or b in a for a in g["quotes"] for b in p["quotes"])
        if not (same_company or company_overlap or quote_overlap):
            return 0
        return (
            100 * same_company
            + 30 * company_overlap
            + 15 * quote_overlap
            + (10 * signal_overlap + 5 * timing_overlap)
        )

    @lru_cache(None)
    def assign(index, used):
        if index == len(expected):
            return 0, ()
        best_score, best_pairs = assign(index + 1, used)
        for pi, p in enumerate(predicted):
            if used & (1 << pi):
                continue
            score = weight(expected[index], p)
            if not score:
                continue
            rest_score, rest_pairs = assign(index + 1, used | (1 << pi))
            if score + rest_score > best_score:
                best_score = score + rest_score
                best_pairs = ((index, pi),) + rest_pairs
        return best_score, best_pairs

    return list(assign(0, 0)[1])


def compare_case(gold: dict, saved: dict) -> dict:
    expected = gold["expected"]
    # Failed grounding can still have interpretable fields. Report that separately from usability.
    parsed = saved["prediction"] if saved["validation_checks"]["typed_schema"] else None
    expected_events = [gold_event(event) for event in expected["events"]]
    predicted_events = [predicted_event(event) for event in parsed["events"]] if parsed else []
    pairs = match_events(expected_events, predicted_events)
    matched = []
    for gi, pi in pairs:
        g, p = expected_events[gi], predicted_events[pi]
        matched.append(
            {
                "gold_event_index": gi,
                "prediction_event_index": pi,
                "expected": {k: g[k] for k in FIELDS},
                "predicted": {k: p[k] for k in FIELDS},
                "field_matches": {k: g[k] == p[k] for k in FIELDS},
                "differences": [k for k in FIELDS if g[k] != p[k]],
            }
        )
    missing = [i for i in range(len(expected_events)) if i not in {g for g, _ in pairs}]
    extra = [i for i in range(len(predicted_events)) if i not in {p for _, p in pairs}]
    g_signals = {s for e in expected_events for s in e["signals"]}
    p_signals = {s for e in predicted_events for s in e["signals"]}
    manual = gold["case_id"] in MANUAL_CASES
    return {
        "case_id": gold["case_id"],
        "scoring_set": "manual_review" if manual else "clear",
        "input_fingerprint": saved["input_fingerprint"],
        "validation_status": saved["validation_status"],
        "validation_error": saved["error"],
        "unvalidated_raw_outcome": saved["prediction"].get("outcome")
        if isinstance(saved["prediction"], dict)
        else None,
        "unvalidated_raw_events": saved["prediction"].get("events")
        if isinstance(saved["prediction"], dict)
        else None,
        "semantic_comparison_available": parsed is not None,
        "expected_outcome": expected["outcome"],
        "predicted_outcome": parsed["outcome"] if parsed else None,
        "outcome_match": parsed is not None and expected["outcome"] == parsed["outcome"],
        "expected_event_count": len(expected_events),
        "predicted_event_count": len(predicted_events) if parsed else None,
        "event_count_match": parsed is not None and len(expected_events) == len(predicted_events),
        "expected_events": expected_events,
        "predicted_events": predicted_events,
        "matched_events": matched,
        "unmatched_gold_event_indices": missing,
        "unmatched_prediction_event_indices": extra,
        "signal_presence": {
            "true_positive": sorted(g_signals & p_signals),
            "extra_vs_gold": sorted(p_signals - g_signals),
            "missing_vs_gold": sorted(g_signals - p_signals),
        },
        "validation_checks": saved["validation_checks"],
        "difference_status": (
            "manual_adjudication_required"
            if manual
            else "literal_difference_requires_semantic_review"
        ),
    }


def summarize(rows: list[dict]) -> dict:
    fields = {field: 0 for field in FIELDS}
    expected_events = sum(row["expected_event_count"] for row in rows)
    signal_counts = Counter()
    per_signal = {}
    accepted_signal_counts = Counter()
    for row in rows:
        for match in row["matched_events"]:
            for field in FIELDS:
                fields[field] += int(match["field_matches"][field])
        for category, keys in row["signal_presence"].items():
            signal_counts[category] += len(keys)
            for key in keys:
                per_signal.setdefault(key, Counter())[category] += 1
        expected_keys = {key for event in row["expected_events"] for key in event["signals"]}
        accepted_keys = (
            {key for event in row["predicted_events"] for key in event["signals"]}
            if row["validation_status"] == "succeeded"
            else set()
        )
        accepted_signal_counts["tp"] += len(expected_keys & accepted_keys)
        accepted_signal_counts["extra"] += len(accepted_keys - expected_keys)
        accepted_signal_counts["missing"] += len(expected_keys - accepted_keys)
    tp, fp, fn = (signal_counts[k] for k in ("true_positive", "extra_vs_gold", "missing_vs_gold"))
    positives = [r for r in rows if r["expected_event_count"] > 0]
    negatives = [
        r for r in rows if r["expected_outcome"] == "assessed" and not r["expected_event_count"]
    ]
    insufficient = [r for r in rows if r["expected_outcome"] == "insufficient_evidence"]
    return {
        "cases": len(rows),
        "accepted_by_backend": sum(r["validation_status"] == "succeeded" for r in rows),
        "interpretable_typed_outputs": sum(r["semantic_comparison_available"] for r in rows),
        "outcome_matches": sum(r["outcome_match"] for r in rows),
        "event_count_matches": sum(r["event_count_match"] for r in rows),
        "expected_events": expected_events,
        "matched_events": sum(len(r["matched_events"]) for r in rows),
        "missing_events": sum(len(r["unmatched_gold_event_indices"]) for r in rows),
        "extra_events": sum(len(r["unmatched_prediction_event_indices"]) for r in rows),
        "literal_field_matches_over_expected_events": fields,
        "signal_presence": {
            "unit": "(case_id, signal_key), independent of duplicate/grouped events",
            "tp": tp,
            "extra_vs_gold": fp,
            "missing_vs_gold": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "per_signal": per_signal,
        "positive_cases": len(positives),
        "positive_cases_detected_in_typed_output": sum(
            (r["predicted_event_count"] or 0) > 0 for r in positives
        ),
        "positive_cases_detected_in_parseable_raw_output": sum(
            bool(r["unvalidated_raw_events"]) for r in positives
        ),
        "positive_cases_usable_after_validation": sum(
            r["validation_status"] == "succeeded" and (r["predicted_event_count"] or 0) > 0
            for r in positives
        ),
        "zero_event_cases": len(negatives),
        "zero_event_cases_returning_no_positive_events": sum(
            r["unvalidated_raw_events"] == [] for r in negatives
        ),
        "zero_event_cases_correct": sum(
            r["predicted_outcome"] == "assessed" and r["predicted_event_count"] == 0
            for r in negatives
        ),
        "insufficient_cases": len(insufficient),
        "insufficient_cases_correct": sum(r["outcome_match"] for r in insufficient),
        "backend_accepted_signal_counts": dict(accepted_signal_counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--replace-derived", action="store_true")
    args = parser.parse_args()
    predictions_path = BASE / "results/pilot_v1_nemotron_predictions.jsonl"
    predictions = load_jsonl(predictions_path)
    ids = [f"pilot-v1-{i:03d}" for i in range(1, 25)]
    if [r["case_id"] for r in predictions] != ids:
        raise ValueError("Save all 24 predictions before loading the answer key")
    gold = load_jsonl(args.gold)
    if [r["case_id"] for r in gold] != ids:
        raise ValueError("Gold case IDs do not match predictions")
    review = args.review.read_text(encoding="utf-8")
    gold_hash = hashlib.sha256(args.gold.read_bytes()).hexdigest()
    if gold_hash not in review:
        raise ValueError("Gold hash not attested by supplied review memo")
    rows = [compare_case(g, p) for g, p in zip(gold, predictions, strict=True)]
    annotations_path = BASE / "results/local/pilot_v1/semantic_review.json"
    if annotations_path.exists():
        annotations = json.loads(annotations_path.read_text(encoding="utf-8"))
        for row in rows:
            row["semantic_review"] = annotations[row["case_id"]]
    mode = "w" if args.replace_derived else "x"
    comparison = BASE / "results/pilot_v1_comparison.jsonl"
    with comparison.open(mode, encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "all": summarize(rows),
        "clear": summarize([r for r in rows if r["scoring_set"] == "clear"]),
        "manual_review_working_reference_only": summarize(
            [r for r in rows if r["scoring_set"] == "manual_review"]
        ),
        "gold_sha256": gold_hash,
        "review_sha256": hashlib.sha256(args.review.read_bytes()).hexdigest(),
        "predictions_sha256": hashlib.sha256(predictions_path.read_bytes()).hexdigest(),
        "limitations": [
            "Literal comparisons casefold and collapse whitespace only; aliases can differ.",
            "One-to-one event alignment can expose splitting/grouping differences as misses.",
            "Gold has one geography object; prediction supports multiple locations and roles.",
            "Null gold geography does not prove a predicted location is unsupported.",
            "Strict quote matching proves textual attachment, not semantic entailment.",
            "Backend-rejected but typed predictions remain visible in semantic diagnostics.",
            "Invalid or missing predictions count as unavailable, not as zero-event rejections.",
            "No gold labels were modified, and no model call is made by this script.",
        ],
    }
    path = BASE / "results/local/pilot_v1/comparison_metrics.json"
    with path.open(mode, encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
