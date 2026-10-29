"""Offline Experiment A comparison after both prediction files are complete."""

from __future__ import annotations

import json
from collections import Counter

from compare_pilot_v1 import compare_case, load_jsonl, summarize
from run_experiment_a import ARMS, BASE, BASELINE, LOCAL, OUT, PLAN_PATH, sha256, write_new


def structural_summary(rows: list[dict], controls: set[str]) -> dict:
    count = len(rows)
    parsed = sum(row["validation_checks"]["json_object"] for row in rows)
    typed = sum(row["validation_checks"]["typed_schema"] for row in rows)
    accepted = sum(row["validation_status"] == "succeeded" for row in rows)
    control_passes = sum(
        row["validation_status"] == "succeeded" for row in rows if row["case_id"] in controls
    )
    truncated = sum(
        any(
            c.get("finish_reason") == "length"
            for c in (row["raw_response"] or {}).get("choices", [])
        )
        for row in rows
    )
    usage = Counter()
    for row in rows:
        values = (row["raw_response"] or {}).get("usage", {})
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[key] += values.get(key, 0)
        usage["reasoning_tokens"] += (
            values.get("completion_tokens_details", {}).get("reasoning_tokens", 0) or 0
        )
    return {
        "cases": count,
        "parseable_json": parsed,
        "typed_schema": typed,
        "backend_valid": accepted,
        "truncations": truncated,
        "valid_controls": control_passes,
        "technical_gate_passed": (
            count == 16
            and parsed == 16
            and typed == 16
            and accepted >= 15
            and truncated == 0
            and control_passes == 6
        ),
        "failed_case_ids": [r["case_id"] for r in rows if r["validation_status"] != "succeeded"],
        "failed_control_ids": [
            r["case_id"]
            for r in rows
            if r["case_id"] in controls and r["validation_status"] != "succeeded"
        ],
        "primary_errors": dict(Counter(r["error"] for r in rows if r["error"])),
        "quotes_all_match": sum(r["validation_checks"]["quotes_match_input"] is True for r in rows),
        "usage": dict(usage),
        "summed_duration_seconds": round(sum(r["duration_seconds"] for r in rows), 3),
    }


def signature(row: dict) -> dict | None:
    if not row["validation_checks"]["typed_schema"]:
        return None
    parsed = row["prediction"]
    return {
        "outcome": parsed["outcome"],
        "events": [
            {
                "company": e["subject_company"]["value"],
                "signals": sorted(s["signal_key"] for s in e["signals"]),
                "stage": e["stage"]["value"],
                "locations": [
                    {k: v.get("value") if isinstance(v, dict) else v for k, v in loc.items()}
                    for loc in e["locations"]
                ],
                "timing": [{k: v for k, v in t.items() if k != "evidence"} for t in e["timing"]],
            }
            for e in parsed["events"]
        ],
    }


def main() -> None:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    ids = [row["case_id"] for row in plan["cases"]]
    controls = {row["case_id"] for row in plan["cases"] if row["role"] == "successful_control"}
    arms = {}
    for arm in ARMS:
        rows = load_jsonl(OUT / f"{arm}_predictions.jsonl")
        if [r["case_id"] for r in rows] != ids:
            raise ValueError("Both complete 16-case arms must be saved before comparison")
        arms[arm] = rows
    if sha256(BASELINE) != plan["baseline_sha256"]:
        raise ValueError("Historical baseline changed")
    baseline = {row["case_id"]: row for row in load_jsonl(BASELINE)}
    # Answer key is loaded here only; neither live runner imports this comparison module.
    gold_path = BASE / "data_local/pilot_v1/reference/pilot_v1_gold_answers.jsonl"
    if sha256(gold_path) != "d2a5e0a39cdf64380602f44658647d7d28cb0eedd733af00ef8d665972da9852":
        raise ValueError("Frozen gold changed")
    gold = {r["case_id"]: r for r in load_jsonl(gold_path)}
    metrics = {"historical_baseline": structural_summary([baseline[i] for i in ids], controls)}
    comparisons = []
    control_reviews = []
    for arm, predictions in arms.items():
        comparison = []
        for row in predictions:
            case_id = row["case_id"]
            compared = compare_case(gold[case_id], row)
            compared["arm"] = arm
            compared["is_control"] = case_id in controls
            compared["baseline_validation_status"] = baseline[case_id]["validation_status"]
            compared["baseline_signature"] = signature(baseline[case_id])
            compared["current_signature"] = signature(row)
            compared["signature_changed"] = compared["baseline_signature"] != signature(row)
            comparison.append(compared)
            if case_id in controls:
                control_reviews.append(
                    {
                        "arm": arm,
                        "case_id": case_id,
                        "backend_regression": row["validation_status"] != "succeeded",
                        "signature_changed_requires_review": compared["signature_changed"],
                        "baseline": compared["baseline_signature"],
                        "current": signature(row),
                    }
                )
        comparisons.extend(comparison)
        metrics[arm] = structural_summary(predictions, controls)
        metrics[arm]["gold_diagnostics_not_a_semantic_experiment"] = summarize(comparison)
    metrics["prediction_sha256"] = {arm: sha256(OUT / f"{arm}_predictions.jsonl") for arm in ARMS}
    metrics["gold_sha256"] = sha256(gold_path)
    metrics["max_calls"] = 32
    metrics["actual_saved_calls"] = sum(len(rows) for rows in arms.values())
    write_new(OUT / "metrics.json", metrics)
    with (OUT / "comparison.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in comparisons:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_new(LOCAL / "control_review.json", {"controls": control_reviews})
    print(
        json.dumps(
            {
                arm: {
                    k: v
                    for k, v in values.items()
                    if k != "gold_diagnostics_not_a_semantic_experiment"
                }
                for arm, values in metrics.items()
                if arm in ARMS or arm == "historical_baseline"
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
