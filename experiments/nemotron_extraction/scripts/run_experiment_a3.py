"""Run A3 on Experiment A's frozen real-evidence cases without schema patterns."""

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

from run_experiment_a import (
    BASELINE,
    StructuredNebiusClient,
)
from run_experiment_a import PLAN_PATH as A_PLAN_PATH
from run_pilot_v1 import (
    BASE,
    ROOT,
    RecordingClient,
    SemanticExtractionInput,
    SemanticExtractionOutput,
    SemanticExtractor,
    diagnostics,
    fingerprint,
    get_settings,
    load_inputs,
    sha256,
    write_new,
)

A3_PLAN_PATH = BASE / "cases" / "experiment_a3_v1.json"
OUT = BASE / "results" / "experiment_a3_v1"
LOCAL = BASE / "results" / "local" / "experiment_a3_v1"
ARM = "a3_schema_without_patterns_4096"


def without_patterns(value):
    """Copy a JSON Schema while removing only regex pattern keywords."""
    if isinstance(value, dict):
        return {key: without_patterns(child) for key, child in value.items() if key != "pattern"}
    if isinstance(value, list):
        return [without_patterns(child) for child in value]
    return copy.deepcopy(value)


def response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "radory_semantic_extraction_v1",
            "strict": True,
            "schema": without_patterns(SemanticExtractionOutput.model_json_schema()),
        },
    }


def load_configuration() -> tuple[dict, dict]:
    config = json.loads(A3_PLAN_PATH.read_text(encoding="utf-8"))
    parent = json.loads(A_PLAN_PATH.read_text(encoding="utf-8"))
    if sha256(A_PLAN_PATH) != config["parent_plan_sha256"]:
        raise ValueError("Frozen Experiment A plan changed")
    if (
        sha256(BASELINE) != config["baseline_sha256"]
        or parent["baseline_sha256"] != config["baseline_sha256"]
    ):
        raise ValueError("Historical selected-case baseline changed")
    if parent["model"] != config["model"]:
        raise ValueError("A3 model differs from Experiment A")
    if config["arm"] != ARM or config["max_tokens"] != 4096:
        raise ValueError("A3 arm or frozen output budget changed")
    if config["max_live_calls"] != 16 or config["retries"] != 0:
        raise ValueError("A3 call bounds changed")
    if fingerprint(response_format()) != config["response_format_fingerprint"]:
        raise ValueError("A3 provider schema changed")
    return config, parent


class A3NebiusClient(StructuredNebiusClient):
    """Experiment A transport with only its provider schema representation changed."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.format = response_format()


async def run(live: bool) -> None:
    config, parent = load_configuration()
    selected_ids = [row["case_id"] for row in parent["cases"]]
    prepared = [item for item in load_inputs() if item[0]["case_id"] in set(selected_ids)]
    if [row["case_id"] for row, _, _ in prepared] != selected_ids:
        raise ValueError("A3 cases differ from Experiment A's frozen ordered cases")
    settings = get_settings()
    if settings.nemotron_super_model != config["model"] or not settings.nebius_api_key:
        raise ValueError("Configured Nebius credentials and frozen Super model required")
    print(
        json.dumps(
            {
                "preflight": "passed",
                "arm": ARM,
                "cases": len(prepared),
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "regex_patterns_in_provider_schema": 0,
                "prompt_evidence_gold_validators_unchanged": True,
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return

    output = OUT / f"{ARM}_predictions.jsonl"
    arm_local = LOCAL / ARM
    if output.exists() or LOCAL.exists():
        raise FileExistsError("Existing A3 run found; no overwriting or paid retries")
    OUT.mkdir(parents=True, exist_ok=True)
    arm_local.mkdir(parents=True)
    write_new(
        LOCAL / "run_metadata.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "arm": ARM,
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "response_format": response_format(),
            "a3_plan_sha256": sha256(A3_PLAN_PATH),
            "parent_plan_sha256": sha256(A_PLAN_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "baseline_sha256": sha256(BASELINE),
            "automatic_retries": 0,
            "sampling_and_reasoning": "provider defaults; not sent",
            "http_timeout_seconds": 60,
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
        for row, evidence, messages in prepared:
            case_id = row["case_id"]
            client = A3NebiusClient(
                expected_messages=messages,
                model=config["model"],
                max_tokens=config["max_tokens"],
                error_path=arm_local / f"{case_id}_http_error.json",
            )
            request_path = arm_local / f"{case_id}_request.json"
            write_new(
                request_path,
                client.payload(messages, config["model"], config["max_tokens"]),
            )
            recorder = RecordingClient(client, messages, arm_local / f"{case_id}_response.json")
            started = time.monotonic()
            result = await SemanticExtractor(
                recorder,
                model=config["model"],
                max_output_tokens=config["max_tokens"],
            ).extract(evidence)
            raw = recorder.response
            prediction = None
            if raw:
                try:
                    prediction = json.loads(raw["choices"][0]["message"]["content"])
                except (KeyError, IndexError, TypeError, ValueError):
                    pass
            record = {
                "experiment_id": config["experiment_id"],
                "arm": ARM,
                "case_id": case_id,
                "variant": row["variant"],
                "input_fingerprint": row["input_fingerprint"],
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "prediction": prediction,
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
                "response_format_fingerprint": config["response_format_fingerprint"],
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            print(
                json.dumps(
                    {
                        "arm": ARM,
                        "case_id": case_id,
                        "status": result.status,
                        "error": result.error_code,
                    }
                ),
                flush=True,
            )
            if result.error_code and result.error_code.startswith("provider_"):
                raise RuntimeError("Provider failure recorded; A3 stopped without retry")
    print(json.dumps({"arm": ARM, "saved_cases": 16, "path": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly send at most 16 calls")
    args = parser.parse_args()
    asyncio.run(run(args.live))
