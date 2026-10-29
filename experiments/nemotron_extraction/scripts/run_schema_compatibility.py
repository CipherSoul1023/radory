"""Disposable live probe for Nemotron response-format compatibility."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx
from app.search.evidence import EvidenceBlock, PreparedDocument, PreparedEvidence
from run_pilot_v1 import (
    BASE,
    ROOT,
    RecordingClient,
    SemanticExtractionInput,
    SemanticExtractionOutput,
    SemanticExtractor,
    diagnostics,
    extraction_messages,
    extraction_specification,
    fingerprint,
    get_settings,
    sha256,
    write_new,
)

PLAN_PATH = BASE / "cases" / "schema_compatibility_v1.json"
OUT = BASE / "results" / "schema_compatibility_v1"
LOCAL = BASE / "results" / "local" / "schema_compatibility_v1"
MODES = ("strict_current", "strict_without_patterns", "json_object")


def without_patterns(value):
    """Return the same JSON Schema with only regex pattern keywords removed."""
    if isinstance(value, dict):
        return {key: without_patterns(child) for key, child in value.items() if key != "pattern"}
    if isinstance(value, list):
        return [without_patterns(child) for child in value]
    return copy.deepcopy(value)


def response_format(mode: str) -> dict:
    if mode == "json_object":
        return {"type": "json_object"}
    schema = SemanticExtractionOutput.model_json_schema()
    if mode == "strict_without_patterns":
        schema = without_patterns(schema)
    elif mode != "strict_current":
        raise ValueError("Unknown response-format mode")
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "radory_semantic_extraction_v1",
            "strict": True,
            "schema": schema,
        },
    }


def load_plan() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if plan["modes"] != list(MODES) or plan["max_live_calls"] != 12 or plan["retries"] != 0:
        raise ValueError("Probe plan does not match its fixed execution bounds")
    if [row["case_id"] for row in plan["cases"]] != [
        f"schema-v1-{number:03d}" for number in range(1, 5)
    ]:
        raise ValueError("Probe requires exactly four ordered synthetic cases")
    return plan


def prepare_case(row: dict) -> tuple[PreparedEvidence, list[dict[str, str]]]:
    document = PreparedDocument(
        content_basis=row["content_basis"],
        provider_published_at=None,
        blocks=(
            EvidenceBlock(block_id="title", kind="title", text=row["title"]),
            EvidenceBlock(block_id="body", kind=row["content_basis"], text=row["body"]),
        ),
    )
    semantic = SemanticExtractionInput.from_document(document)
    messages = extraction_messages(semantic, extraction_specification())
    expected_text = json.dumps(row["expected"], ensure_ascii=False, sort_keys=True)
    if expected_text in json.dumps(messages, ensure_ascii=False, sort_keys=True):
        raise AssertionError("Expected-answer object leaked into model messages")
    input_payload = document.semantic_payload()
    evidence = PreparedEvidence(
        workspace_id=uuid5(NAMESPACE_URL, "radory-disposable-schema-compatibility-v1"),
        document=document,
        content_hash=hashlib.sha256(row["body"].encode("utf-8")).hexdigest(),
        input_fingerprint=fingerprint({"preparation_version": "1", "input": input_payload}),
        sources=(),
    )
    return evidence, messages


class ProbeClient:
    """One-call transport that adds only the selected response_format."""

    def __init__(self, *, expected_messages, model, max_tokens, mode, error_path):
        self.settings = get_settings()
        self.expected_messages = copy.deepcopy(expected_messages)
        self.model = model
        self.max_tokens = max_tokens
        self.mode = mode
        self.error_path = error_path
        self.used = False

    def payload(self, messages, model, max_tokens) -> dict:
        if (
            messages != self.expected_messages
            or model != self.model
            or max_tokens != self.max_tokens
        ):
            raise AssertionError("Request differs from frozen probe configuration")
        return {
            "model": model,
            "messages": copy.deepcopy(messages),
            "max_tokens": max_tokens,
            "response_format": response_format(self.mode),
        }

    async def chat_completion(self, messages, model=None, max_tokens=None):
        payload = self.payload(messages, model, max_tokens)
        if self.used:
            raise AssertionError("Probe calls cannot be retried")
        self.used = True
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.settings.nebius_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + self.settings.nebius_api_key},
                json=payload,
            )
            if response.is_error:
                write_new(self.error_path, {"http_status": response.status_code})
            response.raise_for_status()
            return response.json()


async def run(live: bool) -> None:
    plan = load_plan()
    settings = get_settings()
    model = settings.nemotron_super_model
    if not model or not settings.nebius_api_key:
        raise ValueError("Configured Nebius credentials and Super model required")
    prepared = [(row, *prepare_case(row)) for row in plan["cases"]]
    print(
        json.dumps(
            {
                "preflight": "passed",
                "cases": len(prepared),
                "modes": list(MODES),
                "max_calls": len(prepared) * len(MODES),
                "model": model,
                "live": live,
                "semantic_messages_identical_across_modes": True,
            }
        ),
        flush=True,
    )
    if not live:
        return

    output = OUT / "predictions.jsonl"
    if output.exists() or LOCAL.exists():
        raise FileExistsError("Existing probe found; live calls cannot be overwritten or retried")
    OUT.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True)
    write_new(
        LOCAL / "run_metadata.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "model": model,
            "max_tokens": plan["max_tokens"],
            "modes": {mode: response_format(mode) for mode in MODES},
            "plan_sha256": sha256(PLAN_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "production_source_sha256": {
                str(path.relative_to(ROOT)): sha256(path)
                for path in (
                    ROOT / "backend/app/search/extractor.py",
                    ROOT / "backend/app/search/extraction_contract.py",
                    ROOT / "backend/app/integrations/nebius/client.py",
                )
            },
            "automatic_retries": 0,
            "sampling_and_reasoning": "provider defaults; not sent",
        },
    )
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        for mode in MODES:
            mode_dir = LOCAL / mode
            mode_dir.mkdir()
            for row, evidence, messages in prepared:
                case_id = row["case_id"]
                client = ProbeClient(
                    expected_messages=messages,
                    model=model,
                    max_tokens=plan["max_tokens"],
                    mode=mode,
                    error_path=mode_dir / f"{case_id}_http_error.json",
                )
                request_path = mode_dir / f"{case_id}_request.json"
                write_new(request_path, client.payload(messages, model, plan["max_tokens"]))
                recorder = RecordingClient(client, messages, mode_dir / f"{case_id}_response.json")
                started = time.monotonic()
                result = await SemanticExtractor(
                    recorder, model=model, max_output_tokens=plan["max_tokens"]
                ).extract(evidence)
                raw = recorder.response
                prediction = None
                if raw:
                    try:
                        prediction = json.loads(raw["choices"][0]["message"]["content"])
                    except (KeyError, IndexError, TypeError, ValueError):
                        pass
                record = {
                    "experiment_id": plan["experiment_id"],
                    "mode": mode,
                    "case_id": case_id,
                    "input_fingerprint": evidence.input_fingerprint,
                    "model": model,
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
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "completed_at": datetime.now(UTC).isoformat(),
                    "request_sha256": sha256(request_path),
                    "response_format_fingerprint": fingerprint(response_format(mode)),
                }
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
                print(
                    json.dumps(
                        {
                            "mode": mode,
                            "case_id": case_id,
                            "status": result.status,
                            "error": result.error_code,
                        }
                    ),
                    flush=True,
                )
                if result.error_code and result.error_code.startswith("provider_"):
                    raise RuntimeError("Provider failure recorded; probe stopped without retry")
    print(json.dumps({"saved_calls": 12, "path": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly send at most 12 calls")
    args = parser.parse_args()
    asyncio.run(run(args.live))
