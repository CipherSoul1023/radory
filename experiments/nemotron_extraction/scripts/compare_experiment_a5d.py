"""Compare A5-D's aggregate with A4-E and the frozen case-008 gold answer."""

from __future__ import annotations

import json

from compare_pilot_v1 import compare_case, load_jsonl, summarize
from run_experiment_a4e import ARM as A4E_ARM
from run_experiment_a4e import OUT as A4E_OUT
from run_experiment_a5d import ARM, OUT, load_configuration
from run_pilot_v1 import BASE, write_new


def technical_metrics(rows: list[dict]) -> dict:
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    reasoning_tokens = 0
    truncations = 0
    for row in rows:
        raw = row.get("raw_response") or {}
        raw_usage = raw.get("usage") or {}
        for key in usage:
            usage[key] += raw_usage.get(key) or 0
        reasoning_tokens += (raw_usage.get("completion_tokens_details") or {}).get(
            "reasoning_tokens"
        ) or 0
        truncations += raw.get("choices", [{}])[0].get("finish_reason") != "stop"
    return {
        "chunk_calls": len(rows),
        "parseable_json": sum(isinstance(row.get("prediction"), dict) for row in rows),
        "typed_schema": sum(row["validation_checks"]["typed_schema"] for row in rows),
        "backend_valid_chunks": sum(row["validation_status"] == "succeeded" for row in rows),
        "truncations": truncations,
        "reasoning_tokens": reasoning_tokens,
        "usage": usage,
    }


def main() -> None:
    config, _ = load_configuration()
    chunk_path = OUT / f"{ARM}_chunk_predictions.jsonl"
    chunks = load_jsonl(chunk_path)
    if [row["chunk_id"] for row in chunks] != ["chunk-001", "chunk-002"]:
        raise ValueError("A5-D requires both ordered chunk responses")
    aggregate = json.loads((OUT / "aggregate.json").read_text(encoding="utf-8"))
    a4e_rows = {row["case_id"]: row for row in load_jsonl(A4E_OUT / f"{A4E_ARM}_predictions.jsonl")}
    gold = {
        row["case_id"]: row
        for row in load_jsonl(BASE / "data_local/pilot_v1/reference/pilot_v1_gold_answers.jsonl")
    }
    case_id = config["source_case_id"]
    baseline_comparison = compare_case(gold[case_id], a4e_rows[case_id])
    aggregate_comparison = compare_case(gold[case_id], aggregate)
    semantic = summarize([aggregate_comparison])
    technical = technical_metrics(chunks)
    target = config["acceptance"]
    signals = semantic["signal_presence"]
    technical_gate = (
        technical["chunk_calls"] == target["chunk_calls"]
        and technical["parseable_json"] == target["parseable_json"]
        and technical["typed_schema"] == target["typed_schema"]
        and technical["backend_valid_chunks"] == target["backend_valid_chunks"]
        and technical["truncations"] == target["truncations"]
        and technical["reasoning_tokens"] == target["cases_with_nonzero_reasoning_tokens"]
        and aggregate["validation_status"]
        == ("succeeded" if target["aggregate_backend_valid"] else "failed")
    )
    semantic_gate = (
        semantic["expected_events"] == target["expected_events"]
        and semantic["matched_events"] == target["matched_events"]
        and signals["tp"] == target["signal_true_positives"]
        and signals["extra_vs_gold"] == target["signal_extra"]
        and signals["missing_vs_gold"] == target["signal_missing"]
    )
    metrics = {
        "source_case_id": case_id,
        "a4e_baseline": {
            "validation_status": a4e_rows[case_id]["validation_status"],
            "predicted_event_count": baseline_comparison["predicted_event_count"],
            "matched_events": len(baseline_comparison["matched_events"]),
            "signal_presence": baseline_comparison["signal_presence"],
        },
        "a5d": {
            "technical": technical,
            "aggregate_validation_status": aggregate["validation_status"],
            "semantic": semantic,
            "technical_gate": technical_gate,
            "semantic_gate_before_manual_review": semantic_gate,
        },
    }
    write_new(OUT / "metrics.json", metrics)
    write_new(
        OUT / "comparison.json",
        {"a4e_baseline": baseline_comparison, "a5d_aggregate": aggregate_comparison},
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
