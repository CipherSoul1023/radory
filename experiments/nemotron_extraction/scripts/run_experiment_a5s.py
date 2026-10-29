"""Run A5-S with finer default-reasoning parts for A5-R's failed chunk."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.search.evidence import (
    PREPARATION_VERSION,
    EvidenceBlock,
    PreparedDocument,
    PreparedEvidence,
)
from app.search.extraction_contract import (
    ExtractionValidationError,
    SemanticExtractionInput,
    SemanticExtractionOutput,
    validate_semantic_output,
)
from app.search.extractor import extraction_messages, extraction_specification
from compare_pilot_v1 import load_jsonl
from run_experiment_a3 import A3NebiusClient, response_format
from run_experiment_a4e import messages_with_addendum
from run_experiment_a4r import DirectiveRecordingClient
from run_experiment_a5d import build_chunks, split_body
from run_experiment_a5r import (
    OUT as A5R_OUT,
)
from run_experiment_a5r import (
    PLAN_PATH as A5R_PLAN_PATH,
)
from run_experiment_a5r import (
    load_configuration as load_a5r_configuration,
)
from run_pilot_v1 import (
    BASE,
    SemanticExtractor,
    diagnostics,
    fingerprint,
    get_settings,
    sha256,
    write_new,
)

PLAN_PATH = BASE / "cases" / "experiment_a5s_v1.json"
OUT = BASE / "results" / "experiment_a5s_v1"
LOCAL = BASE / "results" / "local" / "experiment_a5s_v1"
ARM = "fine_paragraph_decomposition_default_reasoning_4096"


def load_configuration() -> tuple[dict, dict, dict, dict]:
    config = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    a5r, a5d, a4e = load_a5r_configuration()
    prerequisites = {
        A5R_PLAN_PATH: config["a5r_plan_sha256"],
        A5R_OUT
        / "paragraph_decomposition_default_reasoning_4096_chunk_predictions.jsonl": config[
            "a5r_chunk_predictions_sha256"
        ],
        A5R_OUT / "aggregate.json": config["a5r_aggregate_sha256"],
    }
    for path, expected_hash in prerequisites.items():
        if sha256(path) != expected_hash:
            raise ValueError(f"Frozen prerequisite changed: {path.name}")
    if fingerprint(response_format()) != config["response_format_fingerprint"]:
        raise ValueError("Pattern-free strict provider schema changed")
    if config["max_live_calls"] != 3 or config["retries"] != 0:
        raise ValueError("A5-S call bounds changed")
    if config["reasoning_mode"] != a5r["reasoning_mode"] != "provider_default":
        raise ValueError("A5-S reasoning mode changed")
    if config["model"] != a5r["model"] or config["max_tokens"] != a5r["max_tokens"]:
        raise ValueError("A5-S model or token limit differs from A5-R")
    return config, a5r, a5d, a4e


def build_parts(config: dict, a5d: dict) -> tuple[dict, PreparedEvidence, list, list]:
    row, original, parent_chunks = build_chunks(a5d)
    parent = parent_chunks[0]
    parent_body = parent.document.blocks[-1].text
    decomposition = config["decomposition"]
    bodies = split_body(parent_body, decomposition["maximum_body_characters_per_part"])
    if len(bodies) != decomposition["expected_part_count"]:
        raise ValueError("A5-S part count changed")
    title = next(block for block in original.document.blocks if block.kind == "title")
    parts = []
    for index, (body, expected) in enumerate(
        zip(bodies, decomposition["expected_parts"], strict=True), start=1
    ):
        part_id = f"chunk-001-part-{index:03d}"
        if (
            part_id != expected["part_id"]
            or len(body) != expected["body_characters"]
            or hashlib.sha256(body.encode("utf-8")).hexdigest()
            != expected["body_sha256"]
        ):
            raise ValueError(f"A5-S {part_id} differs from the frozen split")
        document = PreparedDocument(
            content_basis="raw_content",
            provider_published_at=original.document.provider_published_at,
            blocks=(
                title,
                EvidenceBlock(
                    block_id=part_id.replace("-", "_"), kind="raw_content", text=body
                ),
            ),
        )
        parts.append(
            PreparedEvidence(
                workspace_id=original.workspace_id,
                document=document,
                content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
                input_fingerprint=fingerprint(
                    {
                        "preparation_version": PREPARATION_VERSION,
                        "input": document.semantic_payload(),
                    }
                ),
                sources=(),
            )
        )
    return row, original, parent_chunks, parts


def preserved_output(config: dict) -> SemanticExtractionOutput:
    rows = load_jsonl(
        A5R_OUT
        / "paragraph_decomposition_default_reasoning_4096_chunk_predictions.jsonl"
    )
    frozen = next(
        row for row in rows if row["chunk_id"] == config["preserved_result"]["chunk_id"]
    )
    if (
        frozen["validation_status"]
        != config["preserved_result"]["required_validation_status"]
    ):
        raise ValueError("A5-S preserved result is no longer backend-valid")
    output = SemanticExtractionOutput.model_validate(frozen["adapter_result"]["output"])
    if len(output.events) != config["preserved_result"]["expected_event_count"]:
        raise ValueError("A5-S preserved result event count changed")
    return output


def aggregate_parts(row, original, parent_chunks, parts, outputs, preserved) -> dict:
    events = [
        event.model_dump(mode="json")
        for output in outputs
        if output is not None
        for event in output.events
    ] + [event.model_dump(mode="json") for event in preserved.events]
    prediction = {"outcome": "assessed", "events": events}
    title = next(block for block in original.document.blocks if block.kind == "title")
    combined = PreparedDocument(
        content_basis="raw_content",
        provider_published_at=original.document.provider_published_at,
        blocks=(title,)
        + tuple(part.document.blocks[-1] for part in parts)
        + (parent_chunks[1].document.blocks[-1],),
    )
    semantic = SemanticExtractionInput.from_document(combined)
    response_text = json.dumps(prediction, ensure_ascii=False)
    status, error = "succeeded", None
    try:
        validate_semantic_output(response_text, semantic)
    except ExtractionValidationError as exc:
        status, error = "failed", exc.code
    synthetic_response = {
        "choices": [{"finish_reason": "stop", "message": {"content": response_text}}]
    }
    return {
        "experiment_id": "experiment_a5s_v1",
        "arm": ARM,
        "case_id": row["case_id"],
        "variant": row["variant"],
        "input_fingerprint": row["input_fingerprint"],
        "prediction": prediction,
        "validation_status": status,
        "error": error,
        "validation_checks": diagnostics(synthetic_response, semantic),
        "aggregation": {
            "validated_new_part_outputs_included": sum(
                output is not None for output in outputs
            ),
            "new_part_count": len(parts),
            "preserved_event_count": len(preserved.events),
            "deduplication": "none",
            "event_count": len(events),
        },
    }


async def run(live: bool) -> None:
    config, _, a5d, a4e = load_configuration()
    row, original, parent_chunks, parts = build_parts(config, a5d)
    preserved = preserved_output(config)
    settings = get_settings()
    if settings.nemotron_super_model != config["model"] or not settings.nebius_api_key:
        raise ValueError(
            "Configured Nebius credentials and frozen Super model required"
        )
    print(
        json.dumps(
            {
                "preflight": "passed",
                "arm": ARM,
                "source_case": row["case_id"],
                "new_parts": len(parts),
                "preserved_events": len(preserved.events),
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "reasoning_mode": config["reasoning_mode"],
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return
    output_path = OUT / f"{ARM}_part_predictions.jsonl"
    aggregate_path = OUT / "aggregate.json"
    if output_path.exists() or aggregate_path.exists() or LOCAL.exists():
        raise FileExistsError("Existing A5-S run found; no overwrite or retry")
    OUT.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True)
    write_new(
        LOCAL / "run_metadata.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "experiment_id": config["experiment_id"],
            "arm": ARM,
            "source_case_id": row["case_id"],
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "response_format": response_format(),
            "reasoning_mode": config["reasoning_mode"],
            "chat_template_kwargs": "not sent",
            "grounding_addendum": a4e["grounding_addendum"],
            "decomposition": config["decomposition"],
            "preserved_result": config["preserved_result"],
            "plan_sha256": sha256(PLAN_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "automatic_retries": 0,
            "sampling": "provider defaults; no sampling fields sent",
            "http_timeout_seconds": config["timeout_seconds"],
        },
    )
    outputs = []
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        for index, evidence in enumerate(parts, start=1):
            part_id = f"chunk-001-part-{index:03d}"
            semantic = SemanticExtractionInput.from_document(evidence.document)
            extractor_messages = extraction_messages(
                semantic, extraction_specification()
            )
            provider_messages = messages_with_addendum(extractor_messages, a4e)
            request_path = LOCAL / f"{part_id}_request.json"
            response_path = LOCAL / f"{part_id}_response.json"
            client = A3NebiusClient(
                expected_messages=provider_messages,
                model=config["model"],
                max_tokens=config["max_tokens"],
                error_path=LOCAL / f"{part_id}_http_error.json",
            )
            write_new(
                request_path,
                client.payload(
                    provider_messages, config["model"], config["max_tokens"]
                ),
            )
            recorder = DirectiveRecordingClient(
                client, extractor_messages, provider_messages, response_path
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
            outputs.append(result.output)
            record = {
                "experiment_id": config["experiment_id"],
                "arm": ARM,
                "case_id": row["case_id"],
                "part_id": part_id,
                "part_input_fingerprint": evidence.input_fingerprint,
                "body_characters": len(evidence.document.blocks[-1].text),
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "reasoning_mode": config["reasoning_mode"],
                "prediction": prediction,
                "raw_response": raw,
                "validation_status": result.status,
                "error": result.error_code,
                "validation_checks": diagnostics(raw, semantic),
                "adapter_result": asdict(result)
                | {
                    "output": result.output.model_dump(mode="json")
                    if result.output
                    else None,
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
                        "part_id": part_id,
                        "status": result.status,
                        "error": result.error_code,
                        "events": len(result.output.events) if result.output else None,
                        "finish_reason": choice.get("finish_reason"),
                        "reasoning_tokens": usage.get(
                            "completion_tokens_details", {}
                        ).get("reasoning_tokens"),
                    }
                ),
                flush=True,
            )
            if result.error_code and result.error_code.startswith("provider_"):
                raise RuntimeError(
                    "Provider failure recorded; A5-S stopped without retry"
                )
    aggregate = aggregate_parts(row, original, parent_chunks, parts, outputs, preserved)
    write_new(aggregate_path, aggregate)
    print(
        json.dumps(
            {
                "aggregate_status": aggregate["validation_status"],
                "aggregate_error": aggregate["error"],
                "aggregate_events": aggregate["aggregation"]["event_count"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.live))
