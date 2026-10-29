"""Compare A4-E grounding behavior with the frozen A4-R2 reference."""

from __future__ import annotations

import json
from collections import Counter

from compare_experiment_a import signature
from compare_experiment_a4r import summary
from compare_pilot_v1 import compare_case, load_jsonl, summarize
from run_experiment_a4e import ARM, OUT, load_configuration
from run_experiment_a4r2 import ARM as A4R2_ARM
from run_experiment_a4r2 import OUT as A4R2_OUT
from run_pilot_v1 import BASE, write_new


def main() -> None:
    config = load_configuration()
    ids = [row["case_id"] for row in config["cases"]]
    controls = {row["case_id"] for row in config["cases"] if row["role"] == "successful_control"}
    recovery = {
        row["case_id"] for row in config["cases"] if row["role"] == "a3_reasoning_truncation"
    }
    paths = {
        A4R2_ARM: A4R2_OUT / f"{A4R2_ARM}_predictions.jsonl",
        ARM: OUT / f"{ARM}_predictions.jsonl",
    }
    rows_by_arm = {}
    for arm, path in paths.items():
        indexed = {row["case_id"]: row for row in load_jsonl(path)}
        rows_by_arm[arm] = [indexed[case_id] for case_id in ids]
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
    current_rows = rows_by_arm[ARM]
    current = metrics[ARM]
    target = config["acceptance"]
    errors = Counter(row["error"] for row in current_rows if row["error"])
    current["cases_with_nonzero_reasoning_tokens"] = sum(
        details["reasoning_tokens"] != 0 for details in current["per_case"].values()
    )
    current["grounding_gate"] = (
        current["cases"] == target["case_count"]
        and current["parseable_json"] == target["parseable_json"]
        and current["typed_schema"] == target["typed_schema"]
        and current["backend_valid"] == target["backend_valid"]
        and current["truncations"] == target["truncations"]
        and current["character_collapse_cases"] == target["character_collapse_cases"]
        and current["cases_with_nonzero_reasoning_tokens"]
        == target["cases_with_nonzero_reasoning_tokens"]
        and errors["unsupported_literal_fact"] == target["unsupported_literal_fact_errors"]
        and errors["unmatched_evidence_quote"] == target["unmatched_evidence_quote_errors"]
    )
    diagnostics = current["gold_diagnostics"]
    signals = diagnostics["signal_presence"]
    current["semantic_readiness_gate_before_manual_review"] = (
        diagnostics["expected_events"] == target["expected_events"]
        and diagnostics["matched_events"] == target["matched_events"]
        and signals["tp"] == target["signal_true_positives"]
        and signals["extra_vs_gold"] == target["signal_extra"]
        and signals["missing_vs_gold"] == target["signal_missing"]
    )
    write_new(OUT / "metrics.json", metrics)
    with (OUT / "comparison.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in comparisons:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_new(OUT / "control_review.json", {"controls": control_review})
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
