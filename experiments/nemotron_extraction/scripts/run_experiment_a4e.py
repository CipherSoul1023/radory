"""Run A4-E's reasoning-off evidence-grounding prompt experiment."""

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

from run_experiment_a3 import response_format
from run_experiment_a4r import DirectiveRecordingClient
from run_experiment_a4r2 import (
    ARM as A4R2_ARM,
)
from run_experiment_a4r2 import (
    OUT as A4R2_OUT,
)
from run_experiment_a4r2 import (
    PLAN_PATH as A4R2_PLAN_PATH,
)
from run_experiment_a4r2 import ThinkingDisabledNebiusClient
from run_pilot_v1 import (
    BASE,
    ROOT,
    SemanticExtractionInput,
    SemanticExtractor,
    diagnostics,
    fingerprint,
    get_settings,
    load_inputs,
    sha256,
    write_new,
)

PLAN_PATH = BASE / "cases" / "experiment_a4e_v1.json"
OUT = BASE / "results" / "experiment_a4e_v1"
LOCAL = BASE / "results" / "local" / "experiment_a4e_v1"
ARM = "grounding_addendum_thinking_off_4096"
CATALOGUE_MARKER = "\nSignal catalogue:\n"


def render_addendum(config: dict) -> str:
    addendum = config["grounding_addendum"]
    lines = ["Grounding addendum for this experiment:"]
    lines.extend(f"- {line}" for line in addendum["instructions"])
    lines.append("Synthetic examples:")
    lines.extend(f"- {line}" for line in addendum["examples"])
    return "\n".join(lines)


def messages_with_addendum(messages: list[dict[str, str]], config: dict) -> list[dict[str, str]]:
    changed = copy.deepcopy(messages)
    if changed[0].get("role") != "system" or CATALOGUE_MARKER not in changed[0]["content"]:
        raise ValueError("Unexpected frozen extraction-message structure")
    changed[0]["content"] = changed[0]["content"].replace(
        CATALOGUE_MARKER,
        "\n" + render_addendum(config) + CATALOGUE_MARKER,
        1,
    )
    return changed


def load_configuration() -> dict:
    config = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    paths_and_hashes = {
        A4R2_PLAN_PATH: config["a4r2_plan_sha256"],
        A4R2_OUT / f"{A4R2_ARM}_predictions.jsonl": config["a4r2_predictions_sha256"],
        ROOT / "backend/app/search/extractor.py": config["production_extractor_sha256"],
        ROOT / "backend/app/search/extraction_contract.py": config["production_contract_sha256"],
    }
    for path, expected_hash in paths_and_hashes.items():
        if sha256(path) != expected_hash:
            raise ValueError(f"Frozen prerequisite changed: {path.name}")
    if fingerprint(response_format()) != config["response_format_fingerprint"]:
        raise ValueError("Pattern-free strict provider schema changed")
    if config["max_live_calls"] != 5 or config["retries"] != 0:
        raise ValueError("A4-E call bounds changed")
    if config["chat_template_kwargs"] != {"enable_thinking": False}:
        raise ValueError("A4-E reasoning control changed")
    if len(config["grounding_addendum"]["instructions"]) != 5:
        raise ValueError("A4-E grounding instructions changed shape")
    return config


async def run(live: bool) -> None:
    config = load_configuration()
    selected_ids = [row["case_id"] for row in config["cases"]]
    inputs = {
        row["case_id"]: (row, evidence, messages) for row, evidence, messages in load_inputs()
    }
    prepared = [inputs[case_id] for case_id in selected_ids]
    for planned, (row, _, _) in zip(config["cases"], prepared, strict=True):
        if row["variant"] != planned["variant"]:
            raise ValueError("A4-E evidence variant changed")
    settings = get_settings()
    if settings.nemotron_super_model != config["model"] or not settings.nebius_api_key:
        raise ValueError("Configured Nebius credentials and frozen Super model required")
    print(
        json.dumps(
            {
                "preflight": "passed",
                "arm": ARM,
                "cases": selected_ids,
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "chat_template_kwargs": config["chat_template_kwargs"],
                "system_message_change": "grounding_addendum_only",
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return
    output = OUT / f"{ARM}_predictions.jsonl"
    if output.exists() or LOCAL.exists():
        raise FileExistsError("Existing A4-E run found; no overwrite or retry")
    OUT.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True)
    write_new(
        LOCAL / "run_metadata.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "experiment_id": config["experiment_id"],
            "arm": ARM,
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "response_format": response_format(),
            "chat_template_kwargs": config["chat_template_kwargs"],
            "grounding_addendum": config["grounding_addendum"],
            "plan_sha256": sha256(PLAN_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "automatic_retries": 0,
            "sampling": "provider defaults; no sampling fields sent",
            "http_timeout_seconds": config["timeout_seconds"],
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
        for row, evidence, original_messages in prepared:
            case_id = row["case_id"]
            provider_messages = messages_with_addendum(original_messages, config)
            request_path = LOCAL / f"{case_id}_request.json"
            response_path = LOCAL / f"{case_id}_response.json"
            client = ThinkingDisabledNebiusClient(
                expected_messages=provider_messages,
                model=config["model"],
                max_tokens=config["max_tokens"],
                error_path=LOCAL / f"{case_id}_http_error.json",
            )
            write_new(
                request_path,
                client.payload(provider_messages, config["model"], config["max_tokens"]),
            )
            recorder = DirectiveRecordingClient(
                client,
                original_messages,
                provider_messages,
                response_path,
            )
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
                "role": next(
                    item["role"] for item in config["cases"] if item["case_id"] == case_id
                ),
                "variant": row["variant"],
                "input_fingerprint": row["input_fingerprint"],
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "chat_template_kwargs": config["chat_template_kwargs"],
                "prompt_variant": "grounding_addendum_v1",
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
            choice = (raw or {}).get("choices", [{}])[0]
            usage = (raw or {}).get("usage", {})
            print(
                json.dumps(
                    {
                        "case_id": case_id,
                        "status": result.status,
                        "error": result.error_code,
                        "finish_reason": choice.get("finish_reason"),
                        "reasoning_tokens": usage.get("completion_tokens_details", {}).get(
                            "reasoning_tokens"
                        ),
                    }
                ),
                flush=True,
            )
            if result.error_code and result.error_code.startswith("provider_"):
                raise RuntimeError("Provider failure recorded; A4-E stopped without retry")
    print(json.dumps({"arm": ARM, "saved_cases": len(prepared)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.live))
