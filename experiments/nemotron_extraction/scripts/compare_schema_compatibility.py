"""Offline analysis for the disposable response-format compatibility probe."""

from __future__ import annotations

import json
from collections import Counter

from run_pilot_v1 import write_new
from run_schema_compatibility import MODES, OUT, load_plan


def free_text_values(prediction: dict | None) -> list[str]:
    values = []
    for event in (prediction or {}).get("events", []):
        values.extend([event["subject_company"]["value"], event["summary"]["value"]])
        for location in event["locations"]:
            values.extend(
                fact["value"]
                for key in ("country", "market", "submarket")
                if (fact := location.get(key)) is not None
            )
        values.extend(timing["expression"] for timing in event["timing"])

        def collect_quotes(value):
            if isinstance(value, dict):
                if isinstance(value.get("quote"), str):
                    values.append(value["quote"])
                for child in value.values():
                    collect_quotes(child)
            elif isinstance(value, list):
                for child in value:
                    collect_quotes(child)

        collect_quotes(event)
    return values


def anchor_match(prediction: dict | None, expected: dict) -> tuple[bool, dict]:
    if not isinstance(prediction, dict) or prediction.get("outcome") != expected["outcome"]:
        return False, {"outcome": False}
    events = prediction.get("events")
    if expected["company"] is None:
        matched = events == []
        return matched, {"outcome": True, "zero_events": matched}
    matching = [
        event
        for event in events or []
        if event.get("subject_company", {}).get("value") == expected["company"]
    ]
    if not matching:
        return False, {"outcome": True, "company": False}
    event = matching[0]
    signal_keys = {signal.get("signal_key") for signal in event.get("signals", [])}
    location_values = {
        fact.get("value")
        for location in event.get("locations", [])
        for key in ("country", "market", "submarket")
        if isinstance((fact := location.get(key)), dict)
    }
    timing_values = {timing.get("expression") for timing in event.get("timing", [])}
    checks = {
        "outcome": True,
        "company": True,
        "required_signals": set(expected["required_signals"]).issubset(signal_keys),
        "stage": event.get("stage", {}).get("value") == expected["stage"],
        "locations": set(expected["location_literals"]).issubset(location_values),
        "timing": expected["timing_literal"] in timing_values,
    }
    return all(checks.values()), checks


def main() -> None:
    plan = load_plan()
    predictions_path = OUT / "predictions.jsonl"
    rows = [json.loads(line) for line in predictions_path.read_text(encoding="utf-8").splitlines()]
    expected_pairs = [(mode, case["case_id"]) for mode in MODES for case in plan["cases"]]
    if [(row["mode"], row["case_id"]) for row in rows] != expected_pairs:
        raise ValueError("Expected exactly 12 ordered probe results")
    cases = {row["case_id"]: row for row in plan["cases"]}
    comparisons = []
    metrics = {}
    for mode in MODES:
        mode_rows = [row for row in rows if row["mode"] == mode]
        mode_comparisons = []
        for row in mode_rows:
            values = free_text_values(row["prediction"])
            collapsed = [value for value in values if len(value.strip()) <= 1]
            anchors, anchor_checks = anchor_match(
                row["prediction"], cases[row["case_id"]]["expected"]
            )
            comparison = {
                "mode": mode,
                "case_id": row["case_id"],
                "validation_status": row["validation_status"],
                "error": row["error"],
                "collapsed_free_text_values": collapsed,
                "free_text_value_count": len(values),
                "semantic_anchor_match": anchors,
                "semantic_anchor_checks": anchor_checks,
            }
            comparisons.append(comparison)
            mode_comparisons.append(comparison)
        parseable = sum(row["validation_checks"]["json_object"] for row in mode_rows)
        typed = sum(row["validation_checks"]["typed_schema"] for row in mode_rows)
        backend = sum(row["validation_status"] == "succeeded" for row in mode_rows)
        truncations = sum(
            any(
                choice.get("finish_reason") == "length"
                for choice in (row["raw_response"] or {}).get("choices", [])
            )
            for row in mode_rows
        )
        collapsed_count = sum(
            len(comparison["collapsed_free_text_values"]) for comparison in mode_comparisons
        )
        anchors = sum(comparison["semantic_anchor_match"] for comparison in mode_comparisons)
        usage = Counter()
        for row in mode_rows:
            provider_usage = (row["raw_response"] or {}).get("usage", {})
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage[key] += provider_usage.get(key, 0)
            usage["reasoning_tokens"] += (
                provider_usage.get("completion_tokens_details", {}).get("reasoning_tokens", 0) or 0
            )
        metrics[mode] = {
            "cases": len(mode_rows),
            "parseable_json": parseable,
            "typed_schema": typed,
            "backend_valid": backend,
            "truncations": truncations,
            "collapsed_free_text_values": collapsed_count,
            "semantic_anchor_matches": anchors,
            "errors": dict(Counter(row["error"] for row in mode_rows if row["error"])),
            "usage": dict(usage),
            "acceptance_passed": (
                len(mode_rows) == 4
                and parseable == 4
                and typed == 4
                and backend == 4
                and truncations == 0
                and collapsed_count == 0
                and anchors == 4
            ),
        }
    write_new(OUT / "metrics.json", metrics)
    with (OUT / "comparison.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in comparisons:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
