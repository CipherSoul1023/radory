"""Offline comparison of A4-R default and no-think arms."""

from __future__ import annotations

import json
from collections import Counter

from compare_experiment_a import signature
from compare_experiment_a3 import collapse_metrics
from compare_pilot_v1 import compare_case, load_jsonl, summarize
from run_experiment_a3 import ARM as A3_ARM
from run_experiment_a3 import OUT as A3_OUT
from run_experiment_a4r import ARMS, OUT, load_configuration
from run_pilot_v1 import BASE, write_new


def summary(rows: list[dict], controls: set[str], recovery: set[str]) -> dict:
    parseable = sum(row["validation_checks"]["json_object"] for row in rows)
    typed = sum(row["validation_checks"]["typed_schema"] for row in rows)
    backend = sum(row["validation_status"] == "succeeded" for row in rows)
    truncations = sum(
        any(
            choice.get("finish_reason") == "length"
            for choice in (row["raw_response"] or {}).get("choices", [])
        )
        for row in rows
    )
    usage = Counter()
    per_case = {}
    for row in rows:
        provider_usage = (row["raw_response"] or {}).get("usage", {})
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            usage[key] += provider_usage.get(key, 0)
        reasoning = (
            provider_usage.get("completion_tokens_details", {}).get(
                "reasoning_tokens", 0
            )
            or 0
        )
        usage["reasoning_tokens"] += reasoning
        choice = (row["raw_response"] or {}).get("choices", [{}])[0]
        per_case[row["case_id"]] = {
            "finish_reason": choice.get("finish_reason"),
            "reasoning_tokens": reasoning,
            "completion_tokens": provider_usage.get("completion_tokens", 0),
            "validation_status": row["validation_status"],
            "error": row["error"],
        }
    result = {
        "cases": len(rows),
        "parseable_json": parseable,
        "typed_schema": typed,
        "backend_valid": backend,
        "truncations": truncations,
        "backend_valid_controls": sum(
            row["validation_status"] == "succeeded"
            for row in rows
            if row["case_id"] in controls
        ),
        "backend_valid_recovery_cases": sum(
            row["validation_status"] == "succeeded"
            for row in rows
            if row["case_id"] in recovery
        ),
        "errors": dict(Counter(row["error"] for row in rows if row["error"])),
        "usage": dict(usage),
        "per_case": per_case,
    }
    result.update(collapse_metrics(rows))
    return result


def main() -> None:
    config, _ = load_configuration()
    ids = [row["case_id"] for row in config["cases"]]
    controls = {
        row["case_id"] for row in config["cases"] if row["role"] == "successful_control"
    }
    recovery = {
        row["case_id"]
        for row in config["cases"]
        if row["role"] == "a3_reasoning_truncation"
    }
    paths = {
        "a3_reference": A3_OUT / f"{A3_ARM}_predictions.jsonl",
        ARMS[0]: OUT / f"{ARMS[0]}_predictions.jsonl",
        ARMS[1]: OUT / f"{ARMS[1]}_predictions.jsonl",
    }
    rows_by_arm = {}
    for arm, path in paths.items():
        rows = load_jsonl(path)
        indexed = {row["case_id"]: row for row in rows}
        rows = [indexed[case_id] for case_id in ids]
        rows_by_arm[arm] = rows
    gold_path = BASE / "data_local/pilot_v1/reference/pilot_v1_gold_answers.jsonl"
    gold = {row["case_id"]: row for row in load_jsonl(gold_path)}
    metrics = {}
    comparisons = []
    control_review = []
    for arm, rows in rows_by_arm.items():
        metrics[arm] = summary(rows, controls, recovery)
        compared = []
        for row in rows:
            comparison = compare_case(gold[row["case_id"]], row)
            comparison["arm"] = arm
            comparison["role"] = next(
                planned["role"]
                for planned in config["cases"]
                if planned["case_id"] == row["case_id"]
            )
            comparison["signature"] = signature(row)
            comparisons.append(comparison)
            compared.append(comparison)
            if row["case_id"] in controls:
                control_review.append(
                    {
                        "arm": arm,
                        "case_id": row["case_id"],
                        "validation_status": row["validation_status"],
                        "error": row["error"],
                        "signature": signature(row),
                    }
                )
        metrics[arm]["gold_diagnostics"] = summarize(compared)
    default_reasoning = metrics[ARMS[0]]["usage"]["reasoning_tokens"]
    no_think_reasoning = metrics[ARMS[1]]["usage"]["reasoning_tokens"]
    reduction = (
        0.0
        if default_reasoning == 0
        else (default_reasoning - no_think_reasoning) / default_reasoning
    )
    target = config["acceptance_for_no_think"]
    no_think = metrics[ARMS[1]]
    no_think["reasoning_token_reduction_fraction_vs_default"] = reduction
    no_think["automated_gate_before_manual_control_review"] = (
        no_think["cases"] == target["case_count"]
        and no_think["parseable_json"] == target["parseable_json"]
        and no_think["typed_schema"] == target["typed_schema"]
        and no_think["backend_valid"] == target["backend_valid"]
        and no_think["truncations"] == target["truncations"]
        and no_think["backend_valid_controls"] == target["backend_valid_controls"]
        and no_think["backend_valid_recovery_cases"]
        == target["backend_valid_recovery_cases"]
        and no_think["character_collapse_cases"] == target["character_collapse_cases"]
        and reduction >= target["minimum_reasoning_token_reduction_fraction"]
    )
    write_new(OUT / "metrics.json", metrics)
    with (OUT / "comparison.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in comparisons:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_new(OUT / "control_review.json", {"controls": control_review})
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
