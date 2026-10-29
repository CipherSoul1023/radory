"""Run A5-D's deterministic evidence-decomposition experiment."""

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

from run_experiment_a3 import response_format
from run_experiment_a4e import (
    OUT as A4E_OUT,
)
from run_experiment_a4e import (
    PLAN_PATH as A4E_PLAN_PATH,
)
from run_experiment_a4e import (
    load_configuration as load_a4e_configuration,
)
from run_experiment_a4e import (
    messages_with_addendum,
)
from run_experiment_a4r import DirectiveRecordingClient
from run_experiment_a4r2 import ThinkingDisabledNebiusClient
from run_pilot_v1 import (
    BASE,
    SemanticExtractor,
    diagnostics,
    fingerprint,
    get_settings,
    load_inputs,
    sha256,
    write_new,
)

from app.search.evidence import (
    PREPARATION_VERSION,
    EvidenceBlock,
    PreparedDocument,
    PreparedEvidence,
)
from app.search.extraction_contract import (
    ExtractionValidationError,
    SemanticExtractionInput,
    validate_semantic_output,
)
from app.search.extractor import extraction_messages, extraction_specification

PLAN_PATH = BASE / "cases" / "experiment_a5d_v1.json"
OUT = BASE / "results" / "experiment_a5d_v1"
LOCAL = BASE / "results" / "local" / "experiment_a5d_v1"
ARM = "paragraph_decomposition_thinking_off_4096"


def split_body(body: str, maximum_characters: int) -> list[str]:
    """Greedily group non-empty paragraphs without overlap or truncation."""
    paragraphs = [paragraph.strip() for paragraph in body.split("\n\n") if paragraph.strip()]
    if not paragraphs or any(len(paragraph) > maximum_characters for paragraph in paragraphs):
        raise ValueError("Evidence cannot be split without truncating a paragraph")
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0
    for paragraph in paragraphs:
        added_length = len(paragraph) + (2 if current else 0)
        if current and current_length + added_length > maximum_characters:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_length = len(paragraph)
        else:
            current.append(paragraph)
            current_length += added_length
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def load_configuration() -> tuple[dict, dict]:
    config = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    a4e = load_a4e_configuration()
    prerequisites = {
        A4E_PLAN_PATH: config["a4e_plan_sha256"],
        A4E_OUT / "grounding_addendum_thinking_off_4096_predictions.jsonl": config[
            "a4e_predictions_sha256"
        ],
    }
    for path, expected_hash in prerequisites.items():
        if sha256(path) != expected_hash:
            raise ValueError(f"Frozen prerequisite changed: {path.name}")
    if fingerprint(response_format()) != config["response_format_fingerprint"]:
        raise ValueError("Pattern-free strict provider schema changed")
    if config["max_live_calls"] != 2 or config["retries"] != 0:
        raise ValueError("A5-D call bounds changed")
    if config["chat_template_kwargs"] != {"enable_thinking": False}:
        raise ValueError("A5-D reasoning control changed")
    if config["prompt_variant"] != "grounding_addendum_v1":
        raise ValueError("A5-D prompt variant changed")
    return config, a4e


def build_chunks(config: dict) -> tuple[dict, PreparedEvidence, list[PreparedEvidence]]:
    inputs = {row[0]["case_id"]: row for row in load_inputs()}
    row, evidence, _ = inputs[config["source_case_id"]]
    if row["variant"] != config["source_variant"]:
        raise ValueError("A5-D evidence variant changed")
    if row["input_fingerprint"] != config["source_input_fingerprint"]:
        raise ValueError("A5-D source fingerprint changed")
    title = next((block for block in evidence.document.blocks if block.kind == "title"), None)
    body = next(
        (block.text for block in evidence.document.blocks if block.kind == "raw_content"), None
    )
    if title is None or body is None:
        raise ValueError("A5-D requires the frozen title and raw-content body")
    decomposition = config["decomposition"]
    bodies = split_body(body, decomposition["maximum_body_characters_per_chunk"])
    if len(bodies) != decomposition["expected_chunk_count"]:
        raise ValueError("A5-D chunk count changed")
    prepared = []
    for index, (body_text, expected) in enumerate(
        zip(bodies, decomposition["expected_chunks"], strict=True), start=1
    ):
        chunk_id = f"chunk-{index:03d}"
        if (
            chunk_id != expected["chunk_id"]
            or len(body_text) != expected["body_characters"]
            or hashlib.sha256(body_text.encode("utf-8")).hexdigest() != expected["body_sha256"]
        ):
            raise ValueError(f"A5-D {chunk_id} differs from the frozen split")
        document = PreparedDocument(
            content_basis="raw_content",
            provider_published_at=evidence.document.provider_published_at,
            blocks=(
                EvidenceBlock(block_id="title", kind="title", text=title.text),
                EvidenceBlock(
                    block_id=f"body_{chunk_id.replace('-', '_')}",
                    kind="raw_content",
                    text=body_text,
                ),
            ),
        )
        payload = document.semantic_payload()
        prepared.append(
            PreparedEvidence(
                workspace_id=evidence.workspace_id,
                document=document,
                content_hash=hashlib.sha256(body_text.encode("utf-8")).hexdigest(),
                input_fingerprint=fingerprint(
                    {"preparation_version": PREPARATION_VERSION, "input": payload}
                ),
                sources=(),
            )
        )
    return row, evidence, prepared


def aggregate_chunks(
    row: dict, original: PreparedEvidence, chunks: list[PreparedEvidence], outputs: list
) -> dict:
    events = [
        event.model_dump(mode="json")
        for output in outputs
        if output is not None
        for event in output.events
    ]
    prediction = {"outcome": "assessed", "events": events}
    title = next(block for block in original.document.blocks if block.kind == "title")
    combined = PreparedDocument(
        content_basis="raw_content",
        provider_published_at=original.document.provider_published_at,
        blocks=(title,)
        + tuple(
            block
            for chunk in chunks
            for block in chunk.document.blocks
            if block.kind == "raw_content"
        ),
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
        "experiment_id": "experiment_a5d_v1",
        "arm": ARM,
        "case_id": row["case_id"],
        "variant": row["variant"],
        "input_fingerprint": row["input_fingerprint"],
        "prediction": prediction,
        "validation_status": status,
        "error": error,
        "validation_checks": diagnostics(synthetic_response, semantic),
        "aggregation": {
            "validated_chunk_outputs_included": sum(output is not None for output in outputs),
            "chunk_count": len(chunks),
            "deduplication": "none",
            "event_count": len(events),
        },
    }


async def run(live: bool) -> None:
    config, a4e = load_configuration()
    row, original, chunks = build_chunks(config)
    settings = get_settings()
    if settings.nemotron_super_model != config["model"] or not settings.nebius_api_key:
        raise ValueError("Configured Nebius credentials and frozen Super model required")
    print(
        json.dumps(
            {
                "preflight": "passed",
                "arm": ARM,
                "source_case": row["case_id"],
                "chunks": len(chunks),
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "chat_template_kwargs": config["chat_template_kwargs"],
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return
    output_path = OUT / f"{ARM}_chunk_predictions.jsonl"
    aggregate_path = OUT / "aggregate.json"
    if output_path.exists() or aggregate_path.exists() or LOCAL.exists():
        raise FileExistsError("Existing A5-D run found; no overwrite or retry")
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
            "chat_template_kwargs": config["chat_template_kwargs"],
            "grounding_addendum": a4e["grounding_addendum"],
            "decomposition": config["decomposition"],
            "plan_sha256": sha256(PLAN_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "automatic_retries": 0,
            "sampling": "provider defaults; no sampling fields sent",
            "http_timeout_seconds": config["timeout_seconds"],
        },
    )
    outputs = []
    with output_path.open("x", encoding="utf-8", newline="\n") as stream:
        for index, evidence in enumerate(chunks, start=1):
            chunk_id = f"chunk-{index:03d}"
            semantic = SemanticExtractionInput.from_document(evidence.document)
            extractor_messages = extraction_messages(semantic, extraction_specification())
            provider_messages = messages_with_addendum(extractor_messages, a4e)
            request_path = LOCAL / f"{chunk_id}_request.json"
            response_path = LOCAL / f"{chunk_id}_response.json"
            client = ThinkingDisabledNebiusClient(
                expected_messages=provider_messages,
                model=config["model"],
                max_tokens=config["max_tokens"],
                error_path=LOCAL / f"{chunk_id}_http_error.json",
            )
            write_new(
                request_path,
                client.payload(provider_messages, config["model"], config["max_tokens"]),
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
                "chunk_id": chunk_id,
                "chunk_input_fingerprint": evidence.input_fingerprint,
                "body_characters": len(evidence.document.blocks[-1].text),
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "chat_template_kwargs": config["chat_template_kwargs"],
                "prediction": prediction,
                "raw_response": raw,
                "validation_status": result.status,
                "error": result.error_code,
                "validation_checks": diagnostics(raw, semantic),
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
                        "chunk_id": chunk_id,
                        "status": result.status,
                        "error": result.error_code,
                        "events": len(result.output.events) if result.output else None,
                        "finish_reason": choice.get("finish_reason"),
                        "reasoning_tokens": usage.get("completion_tokens_details", {}).get(
                            "reasoning_tokens"
                        ),
                    }
                ),
                flush=True,
            )
            if result.error_code and result.error_code.startswith("provider_"):
                raise RuntimeError("Provider failure recorded; A5-D stopped without retry")
    aggregate = aggregate_chunks(row, original, chunks, outputs)
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
