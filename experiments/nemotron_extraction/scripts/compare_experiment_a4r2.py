"""Compare A4-R2 with its frozen A3 and A4-R references."""

from __future__ import annotations

import json

from compare_experiment_a import signature
from compare_experiment_a4r import summary
from compare_pilot_v1 import compare_case, load_jsonl, summarize
from run_experiment_a3 import ARM as A3_ARM
from run_experiment_a3 import OUT as A3_OUT
from run_experiment_a4r import ARMS as A4R_ARMS
from run_experiment_a4r import OUT as A4R_OUT
from run_experiment_a4r2 import ARM, OUT, load_configuration
from run_pilot_v1 import BASE, write_new


def main() -> None:
    config = load_configuration()
    ids = [row["case_id"] for row in config["cases"]]
    controls = {row["case_id"] for row in config["cases"] if row["role"] == "successful_control"}
    recovery = {
        row["case_id"] for row in config["cases"] if row["role"] == "a3_reasoning_truncation"
    }
    paths = {
        "a3_reference": A3_OUT / f"{A3_ARM}_predictions.jsonl",
        "a4r_default_4096": A4R_OUT / f"{A4R_ARMS[0]}_predictions.jsonl",
        "a4r_no_think_4096": A4R_OUT / f"{A4R_ARMS[1]}_predictions.jsonl",
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
    current = metrics[ARM]
    target = config["acceptance"]
    current["cases_with_nonzero_reasoning_tokens"] = sum(
        details["reasoning_tokens"] != 0 for details in current["per_case"].values()
    )
    current["automated_gate_before_manual_control_review"] = (
        current["cases"] == target["case_count"]
        and current["parseable_json"] == target["parseable_json"]
        and current["typed_schema"] == target["typed_schema"]
        and current["backend_valid"] == target["backend_valid"]
        and current["truncations"] == target["truncations"]
        and current["backend_valid_controls"] == target["backend_valid_controls"]
        and current["backend_valid_recovery_cases"] == target["backend_valid_recovery_cases"]
        and current["character_collapse_cases"] == target["character_collapse_cases"]
        and current["cases_with_nonzero_reasoning_tokens"]
        == target["cases_with_nonzero_reasoning_tokens"]
    )
    write_new(OUT / "metrics.json", metrics)
    with (OUT / "comparison.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in comparisons:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_new(OUT / "control_review.json", {"controls": control_review})
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
