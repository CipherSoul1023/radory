"""Frozen-prompt output reliability experiment; no gold input or production changes."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx
from run_pilot_v1 import (
    BASE,
    ROOT,
    NebiusClient,
    RecordingClient,
    SemanticExtractionInput,
    SemanticExtractionOutput,
    SemanticExtractor,
    diagnostics,
    extraction_specification,
    fingerprint,
    get_settings,
    load_inputs,
    sha256,
    write_new,
)

PLAN_PATH = BASE / "cases" / "experiment_a_v1.json"
OUT = BASE / "results" / "experiment_a_v1"
LOCAL = BASE / "results" / "local" / "experiment_a_v1"
BASELINE = BASE / "results" / "pilot_v1_nemotron_predictions.jsonl"
FAILURES = (3, 4, 6, 7, 8, 9, 12, 15, 20, 22)
CONTROLS = (1, 2, 5, 10, 17, 24)
ARMS = {"a1_schema_4096": 4096, "a2_schema_8192": 8192}


def response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "radory_semantic_extraction_v1",
            "strict": True,
            "schema": SemanticExtractionOutput.model_json_schema(),
        },
    }


def build_plan() -> dict:
    baseline = {
        row["case_id"]: row
        for row in map(json.loads, BASELINE.read_text(encoding="utf-8").splitlines())
    }
    cases = []
    for number in sorted(FAILURES + CONTROLS):
        case_id = f"pilot-v1-{number:03d}"
        role = "previous_failure" if number in FAILURES else "successful_control"
        row = baseline[case_id]
        assert (row["validation_status"] == "failed") == (number in FAILURES)
        cases.append(
            {
                "case_id": case_id,
                "role": role,
                "variant": row["variant"],
                "input_fingerprint": row["input_fingerprint"],
                "baseline_validation_error": row["error"],
            }
        )
    return {
        "experiment_id": "experiment_a_v1",
        "purpose": "Output reliability only; no semantic prompt, evidence or validator changes.",
        "model": get_settings().nemotron_super_model,
        "baseline_sha256": sha256(BASELINE),
        "specification_fingerprint": fingerprint(extraction_specification()),
        "response_format_fingerprint": fingerprint(response_format()),
        "cases": cases,
        "arms": [{"name": name, "max_tokens": limit} for name, limit in ARMS.items()],
        "max_live_calls": 32,
        "max_completion_tokens_across_arms": 16 * (4096 + 8192),
        "retries": 0,
        "sampling_and_reasoning_settings": "Unspecified; preserve existing provider defaults.",
        "http_timeout_seconds": 60,
        "acceptance_per_arm": {
            "case_count": 16,
            "json_objects_min": 16,
            "typed_schema_min": 16,
            "backend_valid_min": 15,
            "truncations_max": 0,
            "valid_controls_min": 6,
        },
        "control_semantics": "Review against baseline and gold after both arms are saved; "
        "flag semantic regressions separately from backend validity.",
        "stop_conditions": [
            "Do not overwrite or retry an existing arm.",
            "Abort on provider HTTP/transport failure; no automatic fallback or weaker schema.",
            "Do not start semantic prompt experiments if output-reliability acceptance fails.",
        ],
        "limitations": [
            "Pilot v1 is a historical reference, not a contemporaneous repeated baseline.",
            "One output per case per arm is exploratory and cannot establish consistency.",
            "Provider schema cannot enforce exact evidence support or all Pydantic validators.",
            "Selected failures and controls are development cases, not an unseen holdout.",
        ],
        "sources": [
            "https://docs.tokenfactory.nebius.com/ai-models-inference/json",
            "https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/"
            "nemotron3-super-120B.md",
        ],
    }


class StructuredNebiusClient(NebiusClient):
    """Experiment-only transport: existing request plus documented response_format."""

    def __init__(self, *, expected_messages, model, max_tokens, error_path):
        super().__init__()
        self.expected_messages = copy.deepcopy(expected_messages)
        self.model = model
        self.max_tokens = max_tokens
        self.error_path = error_path
        self.format = response_format()
        self.used = False

    def payload(self, messages, model, max_tokens):
        if (
            messages != self.expected_messages
            or model != self.model
            or max_tokens != self.max_tokens
        ):
            raise AssertionError("Request differs from frozen experiment configuration")
        return {
            "model": model,
            "messages": copy.deepcopy(messages),
            "max_tokens": max_tokens,
            "response_format": copy.deepcopy(self.format),
        }

    async def chat_completion(self, messages, model=None, max_tokens=None):
        payload = self.payload(messages, model, max_tokens)
        if self.used:
            raise AssertionError("No repeated provider calls allowed")
        self.used = True
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.settings.nebius_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + self.settings.nebius_api_key},
                json=payload,
            )
            if response.is_error:
                # No headers or credential-bearing exception text is persisted.
                write_new(self.error_path, {"http_status": response.status_code})
            response.raise_for_status()
            return response.json()


async def run(arm: str | None, live: bool, freeze: bool) -> None:
    prepared = load_inputs()
    plan = build_plan()
    if freeze:
        write_new(PLAN_PATH, plan)
    if not PLAN_PATH.exists() or json.loads(PLAN_PATH.read_text(encoding="utf-8")) != plan:
        raise ValueError("Freeze and review a matching plan before any live call")
    selected_ids = {row["case_id"] for row in plan["cases"]}
    selected = [(r, e, m) for r, e, m in prepared if r["case_id"] in selected_ids]
    assert len(selected) == 16
    settings = get_settings()
    if not settings.nebius_api_key or not settings.nemotron_super_model:
        raise ValueError("Configured Nebius credentials and Super model required")
    print(
        json.dumps(
            {
                "preflight": "passed",
                "cases": 16,
                "controls": 6,
                "arm": arm,
                "live": live,
                "prompt_unchanged": True,
            }
        ),
        flush=True,
    )
    if not live:
        return
    if arm not in ARMS:
        raise ValueError("Choose an explicit arm")
    if arm == "a2_schema_8192":
        a1 = OUT / "a1_schema_4096_predictions.jsonl"
        if not a1.exists() or len(a1.read_text(encoding="utf-8").splitlines()) != 16:
            raise ValueError("Complete A1 before A2")
    output = OUT / f"{arm}_predictions.jsonl"
    local = LOCAL / arm
    if output.exists() or local.exists():
        raise FileExistsError("Existing arm found; no overwriting or paid retries")
    OUT.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True)
    model = plan["model"]
    limit = ARMS[arm]
    write_new(
        local / "run_metadata.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "arm": arm,
            "model": model,
            "max_tokens": limit,
            "plan_sha256": sha256(PLAN_PATH),
            "response_format": response_format(),
            "runner_sha256": sha256(Path(__file__)),
            "baseline_sha256": sha256(BASELINE),
            "specification_fingerprint": plan["specification_fingerprint"],
            "production_source_sha256": {
                str(path.relative_to(ROOT)): sha256(path)
                for path in (
                    ROOT / "backend/app/search/extractor.py",
                    ROOT / "backend/app/search/extraction_contract.py",
                    ROOT / "backend/app/integrations/nebius/client.py",
                )
            },
        },
    )
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        for row, evidence, messages in selected:
            case_id = row["case_id"]
            client = StructuredNebiusClient(
                expected_messages=messages,
                model=model,
                max_tokens=limit,
                error_path=local / f"{case_id}_http_error.json",
            )
            request_path = local / f"{case_id}_request.json"
            write_new(request_path, client.payload(messages, model, limit))
            recorder = RecordingClient(client, messages, local / f"{case_id}_response.json")
            started = time.monotonic()
            result = await SemanticExtractor(
                recorder, model=model, max_output_tokens=limit
            ).extract(evidence)
            raw = recorder.response
            parsed = None
            if raw:
                try:
                    parsed = json.loads(raw["choices"][0]["message"]["content"])
                except (KeyError, IndexError, TypeError, ValueError):
                    pass
            record = {
                "experiment_id": plan["experiment_id"],
                "arm": arm,
                "case_id": case_id,
                "variant": row["variant"],
                "input_fingerprint": row["input_fingerprint"],
                "model": model,
                "max_tokens": limit,
                "prediction": parsed,
                "raw_response": raw,
                "validation_status": result.status,
                "error": result.error_code,
                "validation_checks": diagnostics(
                    raw, SemanticExtractionInput.from_document(evidence.document)
                ),
                "adapter_result": asdict(result)
                | {
                    "output": result.output.model_dump(mode="json") if result.output else None,
                },
                "completed_at": datetime.now(UTC).isoformat(),
                "duration_seconds": round(time.monotonic() - started, 3),
                "request_sha256": sha256(request_path),
                "response_format_fingerprint": plan["response_format_fingerprint"],
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            print(
                json.dumps(
                    {
                        "arm": arm,
                        "case_id": case_id,
                        "status": result.status,
                        "error": result.error_code,
                    }
                ),
                flush=True,
            )
            if result.error_code and result.error_code.startswith("provider_"):
                raise RuntimeError("Provider failure recorded; experiment stopped without retry")
    print(json.dumps({"arm": arm, "saved_cases": 16}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-plan", action="store_true")
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.arm, args.live, args.freeze_plan))
