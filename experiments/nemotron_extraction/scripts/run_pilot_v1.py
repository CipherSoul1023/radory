"""One bounded pilot using the unchanged extraction adapter; no answer-key inputs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.integrations.nebius.client import NebiusClient  # noqa: E402
from app.search.evidence import (  # noqa: E402
    PREPARATION_VERSION,
    EvidenceBlock,
    PreparedDocument,
    PreparedEvidence,
    fingerprint,
)
from app.search.extraction_contract import (  # noqa: E402
    SemanticExtractionInput,
    SemanticExtractionOutput,
)
from app.search.extractor import (  # noqa: E402
    SemanticExtractor,
    extraction_messages,
    extraction_specification,
)
from app.search.signal_library import SIGNAL_LIBRARY  # noqa: E402

BASE = ROOT / "experiments" / "nemotron_extraction"
PACK = BASE / "data_local" / "pilot_v1" / "pilot_v1_label_pack.jsonl"
RESULTS = BASE / "results"
EXPECTED_IDS = [f"pilot-v1-{i:03d}" for i in range(1, 25)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def load_inputs() -> list[tuple[dict, PreparedEvidence, list[dict]]]:
    """Reconstruct only allowed semantic fields and compare both messages to snapshots."""
    rows = [json.loads(line) for line in PACK.read_text(encoding="utf-8").splitlines()]
    if [row["case_id"] for row in rows] != EXPECTED_IDS:
        raise ValueError("Expected exactly the 24 ordered pilot case IDs")
    frozen_system = (PACK.parent / "system_message.txt").read_text(encoding="utf-8")
    specification = extraction_specification()
    prepared = []
    for row in rows:
        if row["allowed_signal_keys"] != list(SIGNAL_LIBRARY):
            raise ValueError("Signal catalogue differs from the frozen pilot")
        payload = {
            "schema_version": "1",
            "content_basis": row["variant"],
            "coverage": row["coverage"],
            "provider_published_at": row["published_at"],
            "blocks": row["evidence_blocks"],
        }
        semantic = SemanticExtractionInput.model_validate(payload)
        frozen = (PACK.parent / "inputs" / f"{row['case_id']}.json").read_text(encoding="utf-8")
        if payload != json.loads(frozen):
            raise ValueError("Label-pack evidence differs from frozen input")
        actual_fingerprint = fingerprint(
            {"preparation_version": PREPARATION_VERSION, "input": payload}
        )
        if actual_fingerprint != row["input_fingerprint"]:
            raise ValueError("Input fingerprint mismatch")
        messages = extraction_messages(semantic, specification)
        if messages != [
            {"role": "system", "content": frozen_system},
            {"role": "user", "content": frozen},
        ]:
            raise ValueError("Current extraction messages differ from frozen pilot messages")
        document = PreparedDocument(
            content_basis=semantic.content_basis,
            provider_published_at=semantic.provider_published_at,
            blocks=tuple(EvidenceBlock(**block.model_dump()) for block in semantic.blocks),
        )
        evidence = PreparedEvidence(
            workspace_id=uuid5(NAMESPACE_URL, "radory-disposable-pilot-v1"),
            document=document,
            content_hash=hashlib.sha256(
                "".join(b.text for b in document.blocks if b.kind != "title").encode("utf-8")
            ).hexdigest(),
            input_fingerprint=actual_fingerprint,
            sources=(),
        )
        prepared.append((row, evidence, messages))
    return prepared


def diagnostics(response: dict | None, semantic: SemanticExtractionInput) -> dict:
    """Independent structural diagnostics, including for backend-rejected responses."""
    result = {
        "json_object": False,
        "typed_schema": False,
        "allowed_signal_keys": None,
        "valid_enums": None,
        "quotes_match_input": None,
        "quote_count": 0,
        "unmatched_quotes": [],
        "schema_errors": [],
    }
    try:
        content = response["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (KeyError, IndexError, TypeError, ValueError):
        return result
    if not isinstance(parsed, dict):
        return result
    result["json_object"] = True
    try:
        SemanticExtractionOutput.model_validate_json(content)
        result["typed_schema"] = True
    except ValueError as exc:
        result["schema_errors"] = [
            {"location": list(e["loc"]), "type": e["type"]}
            for e in exc.errors(include_input=False, include_url=False, include_context=False)
        ]
    events = parsed.get("events")
    if not isinstance(events, list):
        return result
    try:
        result["allowed_signal_keys"] = all(
            s["signal_key"] in SIGNAL_LIBRARY for e in events for s in e["signals"]
        )
        result["valid_enums"] = parsed["outcome"] in {"assessed", "insufficient_evidence"} and all(
            e["stage"]["value"] in {"planned", "underway", "completed", "cancelled", "unclear"}
            and all(
                loc["role"] in {"event_location", "origin", "destination", "unclear"}
                for loc in e["locations"]
            )
            and all(
                t["precision"]
                in {"day", "month", "quarter", "year", "range", "relative", "unclear"}
                for t in e["timing"]
            )
            for e in events
        )
    except (KeyError, TypeError):
        pass
    blocks = {block.block_id: block.text for block in semantic.blocks}

    def walk(value, path=""):
        if isinstance(value, dict):
            if "quote" in value:
                result["quote_count"] += 1
                quote, block_id = value.get("quote"), value.get("block_id")
                if (
                    not isinstance(quote, str)
                    or not isinstance(block_id, str)
                    or (block_id not in blocks or quote not in blocks[block_id])
                ):
                    result["unmatched_quotes"].append(path)
            for key, child in value.items():
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(parsed)
    result["quotes_match_input"] = not result["unmatched_quotes"]
    return result


class RecordingClient:
    """Record the complete provider JSON before the existing adapter validates it."""

    def __init__(self, client, expected_messages, raw_path):
        self.client = client
        self.expected_messages = expected_messages
        self.raw_path = raw_path
        self.response = None
        self.calls = 0

    async def chat_completion(self, messages, model=None, max_tokens=None):
        if messages != self.expected_messages:
            raise ValueError("Request differs from audited frozen messages")
        if self.calls:
            raise ValueError("One request per case; retries are forbidden")
        self.calls += 1
        response = await self.client.chat_completion(messages, model=model, max_tokens=max_tokens)
        write_new(self.raw_path, response)
        self.response = response
        return response


async def run(live: bool) -> None:
    prepared = load_inputs()
    settings = get_settings()
    model = settings.nemotron_super_model
    if not model or not settings.nebius_api_key:
        raise ValueError("Configured Super model and Nebius credentials required")
    print(
        json.dumps(
            {
                "preflight": "passed",
                "cases": len(prepared),
                "model": model,
                "gold_in_request_construction": False,
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return
    output = RESULTS / "pilot_v1_nemotron_predictions.jsonl"
    local = RESULTS / "local" / "pilot_v1"
    if output.exists() or local.exists():
        raise FileExistsError("Existing pilot output found; will not overwrite or rerun")
    local.mkdir(parents=True)
    client = NebiusClient()
    metadata = {
        "started_at": datetime.now(UTC).isoformat(),
        "model": model,
        "max_tokens": 4096,
        "temperature": "provider default (not sent)",
        "top_p": "provider default (not sent)",
        "response_format": "not sent; existing prompt supplies JSON schema",
        "thinking": "provider default (not sent)",
        "http_timeout_seconds": 60,
        "max_requests": 24,
        "automatic_retries": 0,
        "endpoint": settings.nebius_base_url.rstrip("/") + "/chat/completions",
        "label_pack_sha256": sha256(PACK),
        "system_message_sha256": sha256(PACK.parent / "system_message.txt"),
        "specification_fingerprint": fingerprint(extraction_specification()),
        "runner_sha256": sha256(Path(__file__)),
        "production_source_sha256": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in [
                ROOT / "backend/app/search/extractor.py",
                ROOT / "backend/app/search/extraction_contract.py",
                ROOT / "backend/app/integrations/nebius/client.py",
            ]
        },
    }
    write_new(local / "run_metadata.json", metadata)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        for row, evidence, messages in prepared:
            case_id = row["case_id"]
            write_new(
                local / f"{case_id}_request.json",
                {
                    "model": model,
                    "messages": messages,
                    "max_tokens": 4096,
                },
            )
            recorder = RecordingClient(client, messages, local / f"{case_id}_response.json")
            started = time.monotonic()
            result = await SemanticExtractor(recorder, model=model).extract(evidence)
            raw = recorder.response
            prediction = None
            if raw is not None:
                try:
                    prediction = json.loads(raw["choices"][0]["message"]["content"])
                except (KeyError, IndexError, TypeError, ValueError):
                    pass
            record = {
                "case_id": case_id,
                "variant": row["variant"],
                "input_fingerprint": row["input_fingerprint"],
                "model": model,
                "request_settings": {"max_tokens": 4096, "other_sampling": "provider defaults"},
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
                "request_sha256": sha256(local / f"{case_id}_request.json"),
            }
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            print(
                json.dumps(
                    {"case_id": case_id, "status": result.status, "error": result.error_code}
                ),
                flush=True,
            )
    print(json.dumps({"saved_cases": 24, "path": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly send at most 24 requests")
    args = parser.parse_args()
    asyncio.run(run(args.live))
