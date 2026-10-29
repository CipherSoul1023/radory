"""Offline A3 comparison against the unchanged historical, A1 and A2 results."""

from __future__ import annotations

import json

from compare_experiment_a import signature, structural_summary
from compare_pilot_v1 import compare_case, load_jsonl, summarize
from run_experiment_a import BASELINE, sha256, write_new
from run_experiment_a import OUT as A_OUT
from run_experiment_a3 import ARM, OUT, load_configuration
from run_pilot_v1 import BASE


def audited_free_text(prediction: dict | None) -> list[str]:
    """Values implicated by character collapse; enum keys and block IDs are excluded."""
    values = []

    def add(value) -> None:
        if isinstance(value, str):
            values.append(value)

    for event in (prediction or {}).get("events", []):
        add(event["subject_company"].get("value"))
        add(event["summary"].get("value"))
        for related in event.get("related_companies", []):
            add(related["company"].get("value"))
            add(related["role"].get("value"))
        for location in event.get("locations", []):
            for key in ("country", "market", "submarket"):
                if isinstance(location.get(key), dict):
                    add(location[key].get("value"))
        for timing in event.get("timing", []):
            add(timing.get("expression"))

        def collect_quotes(value):
            if isinstance(value, dict):
                if isinstance(value.get("quote"), str):
                    add(value["quote"])
                for child in value.values():
                    collect_quotes(child)
            elif isinstance(value, list):
                for child in value:
                    collect_quotes(child)

        collect_quotes(event)
    return values


def collapse_metrics(rows: list[dict]) -> dict:
    per_case = {
        row["case_id"]: [
            value for value in audited_free_text(row.get("prediction")) if len(value.strip()) <= 1
        ]
        for row in rows
    }
    return {
        "character_collapse_cases": sum(bool(values) for values in per_case.values()),
        "character_collapse_occurrences": sum(len(values) for values in per_case.values()),
        "character_collapse_case_ids": [case_id for case_id, values in per_case.items() if values],
    }


def main() -> None:
    config, parent = load_configuration()
    ids = [row["case_id"] for row in parent["cases"]]
    controls = {row["case_id"] for row in parent["cases"] if row["role"] == "successful_control"}
    paths = {
        "historical": BASELINE,
        "a1_schema_4096": A_OUT / "a1_schema_4096_predictions.jsonl",
        "a2_schema_8192": A_OUT / "a2_schema_8192_predictions.jsonl",
        ARM: OUT / f"{ARM}_predictions.jsonl",
    }
    rows_by_arm = {}
    for arm, path in paths.items():
        rows = load_jsonl(path)
        if arm == "historical":
            indexed = {row["case_id"]: row for row in rows}
            rows = [indexed[case_id] for case_id in ids]
        if [row["case_id"] for row in rows] != ids:
            raise ValueError(f"{arm} does not contain the exact ordered A3 cases")
        rows_by_arm[arm] = rows

    gold_path = BASE / "data_local/pilot_v1/reference/pilot_v1_gold_answers.jsonl"
    if sha256(gold_path) != "d2a5e0a39cdf64380602f44658647d7d28cb0eedd733af00ef8d665972da9852":
        raise ValueError("Frozen gold changed")
    gold = {row["case_id"]: row for row in load_jsonl(gold_path)}
    metrics = {}
    comparisons = []
    controls_review = []
    for arm, rows in rows_by_arm.items():
        structural = structural_summary(rows, controls)
        structural.update(collapse_metrics(rows))
        compared = []
        for row in rows:
            item = compare_case(gold[row["case_id"]], row)
            item["arm"] = arm
            item["is_control"] = row["case_id"] in controls
            item["prediction_signature"] = signature(row)
            item["collapsed_free_text_values"] = [
                value
                for value in audited_free_text(row.get("prediction"))
                if len(value.strip()) <= 1
            ]
            comparisons.append(item)
            compared.append(item)
            if row["case_id"] in controls:
                controls_review.append(
                    {
                        "arm": arm,
                        "case_id": row["case_id"],
                        "validation_status": row["validation_status"],
                        "error": row["error"],
                        "signature": signature(row),
                        "collapsed_free_text_values": item["collapsed_free_text_values"],
                    }
                )
        structural["gold_diagnostics"] = summarize(compared)
        metrics[arm] = structural

    a3 = metrics[ARM]
    a3["technical_gate_passed"] = (
        a3["cases"] == config["acceptance"]["case_count"]
        and a3["typed_schema"] == config["acceptance"]["typed_schema"]
        and a3["backend_valid"] >= config["acceptance"]["backend_valid_min"]
        and a3["truncations"] <= config["acceptance"]["truncations_max"]
        and a3["valid_controls"] == config["acceptance"]["backend_valid_controls"]
        and a3["character_collapse_cases"] <= config["acceptance"]["character_collapse_cases_max"]
        and a3["character_collapse_occurrences"]
        <= config["acceptance"]["character_collapse_occurrences_max"]
    )
    metrics["artifact_sha256"] = {arm: sha256(path) for arm, path in paths.items()}
    metrics["gold_sha256"] = sha256(gold_path)
    write_new(OUT / "metrics.json", metrics)
    with (OUT / "comparison.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
        for row in comparisons:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_new(OUT / "control_review.json", {"controls": controls_review})
    print(
        json.dumps(
            {
                arm: {key: value for key, value in arm_metrics.items() if key != "gold_diagnostics"}
                for arm, arm_metrics in metrics.items()
                if arm in rows_by_arm
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
