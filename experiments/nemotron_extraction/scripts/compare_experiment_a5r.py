"""Compare A5-R with A5-D and the frozen case-008 gold answer."""

from __future__ import annotations

import json

from compare_experiment_a5d import technical_metrics
from compare_pilot_v1 import compare_case, load_jsonl, summarize
from run_experiment_a5d import ARM as A5D_ARM
from run_experiment_a5d import OUT as A5D_OUT
from run_experiment_a5r import ARM, OUT, load_configuration
from run_pilot_v1 import BASE, write_new


def main() -> None:
    config, _, _ = load_configuration()
    chunk_path = OUT / f"{ARM}_chunk_predictions.jsonl"
    chunks = load_jsonl(chunk_path)
    if [row["chunk_id"] for row in chunks] != ["chunk-001", "chunk-002"]:
        raise ValueError("A5-R requires both ordered chunk responses")
    current_aggregate = json.loads((OUT / "aggregate.json").read_text(encoding="utf-8"))
    baseline_chunks = load_jsonl(A5D_OUT / f"{A5D_ARM}_chunk_predictions.jsonl")
    baseline_aggregate = json.loads(
        (A5D_OUT / "aggregate.json").read_text(encoding="utf-8")
    )
    gold = {
        row["case_id"]: row
        for row in load_jsonl(
            BASE / "data_local/pilot_v1/reference/pilot_v1_gold_answers.jsonl"
        )
    }
    case_id = config["source_case_id"]
    baseline_comparison = compare_case(gold[case_id], baseline_aggregate)
    current_comparison = compare_case(gold[case_id], current_aggregate)
    semantic = summarize([current_comparison])
    technical = technical_metrics(chunks)
    baseline_technical = technical_metrics(baseline_chunks)
    target = config["acceptance"]
    signals = semantic["signal_presence"]
    technical_gate = (
        technical["chunk_calls"] == target["chunk_calls"]
        and technical["parseable_json"] == target["parseable_json"]
        and technical["typed_schema"] == target["typed_schema"]
        and technical["backend_valid_chunks"] == target["backend_valid_chunks"]
        and technical["truncations"] == target["truncations"]
        and current_aggregate["validation_status"]
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
        "a5d_thinking_off": {
            "technical": baseline_technical,
            "predicted_event_count": baseline_comparison["predicted_event_count"],
            "matched_events": len(baseline_comparison["matched_events"]),
            "signal_presence": baseline_comparison["signal_presence"],
        },
        "a5r_default_reasoning": {
            "technical": technical,
            "aggregate_validation_status": current_aggregate["validation_status"],
            "semantic": semantic,
            "technical_gate": technical_gate,
            "semantic_gate_before_manual_review": semantic_gate,
        },
    }
    write_new(OUT / "metrics.json", metrics)
    write_new(
        OUT / "comparison.json",
        {
            "a5d_thinking_off": baseline_comparison,
            "a5r_default_reasoning": current_comparison,
        },
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
