"""Run C2's prompt-only semantic tuning on C1's frozen development cases."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from app.search.evidence import EvidenceBlock, PreparedDocument
from run_experiment_a5d import split_body
from run_experiment_b2 import (
    IndexedCompactClient,
    IndexedCompactOutput,
    IndexedValidationError,
    diagnostics,
    indexed_evidence,
    response_format,
    validate_output,
)
from run_experiment_b2 import (
    system_message as b2_system_message,
)
from run_pilot_v1 import (
    BASE,
    ROOT,
    fingerprint,
    get_settings,
    load_inputs,
    sha256,
    write_new,
)

PLAN_PATH = BASE / "cases" / "experiment_c2_v1.json"
C1_PLAN = BASE / "cases" / "experiment_c1_v1.json"
C1_RUNNER = BASE / "scripts" / "run_experiment_c1.py"
EXPERIMENT_A_PLAN = BASE / "cases" / "experiment_a_v1.json"
B2_PLAN = BASE / "cases" / "experiment_b2_v1.json"
B2_RUNNER = BASE / "scripts" / "run_experiment_b2.py"
OUT = BASE / "results" / "experiment_c2_v1"
LOCAL = BASE / "results" / "local" / "experiment_c2_v1"
CHUNK_OUTPUT = OUT / "indexed_compact_tuning_chunk_predictions.jsonl"
CASE_OUTPUT = OUT / "indexed_compact_tuning_case_aggregates.jsonl"
ARM = "indexed_compact_completeness_prompt_default_reasoning_4096"


PROMPT_ADDENDUM = """\

COMPLETENESS AND OUTCOME CHECK:
1. Inspect every supplied passage independently for a company action or transition.
2. Build a complete internal inventory of distinct supported events before returning JSON.
3. Re-scan every passage for secondary events involving the same or another company. Do not
   stop after the first event. This includes acquisitions or disposals mentioned alongside
   layoffs, restructuring or another primary event.
4. Merge signals only when they describe the same real-world event and subject company.
5. If the supplied material is understandable and contains no supported Radory event, return
   assessed with events [].
6. Use insufficient_evidence only when the supplied text is too incomplete or ambiguous to
   decide whether a relevant event exists.
Do not reveal this internal inventory or reasoning; return only the schema-conforming JSON."""


def system_message() -> str:
    """Return B2's frozen instructions plus C2's sole prompt-only change."""
    return b2_system_message() + PROMPT_ADDENDUM


def messages(evidence) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_message()},
        {"role": "user", "content": evidence.model_dump_json()},
    ]


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def build_holdout(config: dict) -> list[dict]:
    available = {row["case_id"]: (row, evidence) for row, evidence, _ in load_inputs()}
    selected = []
    for case_plan in config["cases"]:
        case_id = case_plan["case_id"]
        row, evidence = available[case_id]
        input_path = BASE / "data_local" / "pilot_v1" / "inputs" / f"{case_id}.json"
        if (
            row["variant"] != case_plan["variant"]
            or row["input_fingerprint"] != case_plan["input_fingerprint"]
            or sha256(input_path) != case_plan["input_sha256"]
        ):
            raise ValueError(f"Frozen source input changed: {case_id}")
        title = next(
            block for block in evidence.document.blocks if block.kind == "title"
        )
        body = next(
            block for block in evidence.document.blocks if block.kind != "title"
        )
        bodies = split_body(body.text, config["max_chunk_characters"])
        if len(bodies) != len(case_plan["chunks"]):
            raise ValueError(f"Frozen chunk count changed: {case_id}")
        chunks = []
        for body_text, expected in zip(bodies, case_plan["chunks"], strict=True):
            if (
                len(body_text) != expected["body_characters"]
                or hashlib.sha256(body_text.encode("utf-8")).hexdigest()
                != expected["body_sha256"]
            ):
                raise ValueError(
                    f"Frozen chunk changed: {case_id}/{expected['chunk_id']}"
                )
            document = PreparedDocument(
                content_basis=evidence.document.content_basis,
                provider_published_at=evidence.document.provider_published_at,
                blocks=(
                    title,
                    EvidenceBlock(
                        block_id=f"{body.block_id}_{expected['chunk_id'].replace('-', '_')}",
                        kind=body.kind,
                        text=body_text,
                    ),
                ),
            )
            chunk_fingerprint = fingerprint(
                {
                    "experiment": config["experiment_id"],
                    "source_input_fingerprint": row["input_fingerprint"],
                    "chunk_id": expected["chunk_id"],
                    "document": {
                        "content_basis": document.content_basis,
                        "provider_published_at": (
                            document.provider_published_at.isoformat()
                            if document.provider_published_at is not None
                            else None
                        ),
                        "blocks": [
                            {
                                "block_id": block.block_id,
                                "kind": block.kind,
                                "text": block.text,
                            }
                            for block in document.blocks
                        ],
                    },
                }
            )
            chunks.append(
                {
                    "chunk_id": expected["chunk_id"],
                    "document": document,
                    "indexed": indexed_evidence(document, chunk_fingerprint),
                }
            )
        selected.append(
            {"plan": case_plan, "row": row, "evidence": evidence, "chunks": chunks}
        )
    return selected


def load_configuration() -> tuple[dict, list[dict]]:
    config = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    prerequisites = {
        C1_PLAN: config["c1_plan_sha256"],
        C1_RUNNER: config["c1_runner_sha256"],
        EXPERIMENT_A_PLAN: config["experiment_a_plan_sha256"],
        B2_PLAN: config["b2_plan_sha256"],
        B2_RUNNER: config["b2_runner_sha256"],
        ROOT / "backend/app/search/signal_library.py": config["signal_library_sha256"],
    }
    for path, expected_hash in prerequisites.items():
        if sha256(path) != expected_hash:
            raise ValueError(f"Frozen prerequisite changed: {path.name}")
    if fingerprint(response_format()) != config["response_format_fingerprint"]:
        raise ValueError("C2 response format differs from B2")
    if (
        hashlib.sha256(PROMPT_ADDENDUM.encode("utf-8")).hexdigest()
        != config["prompt_addendum_sha256"]
    ):
        raise ValueError("C2 prompt addendum changed")
    experiment_a = json.loads(EXPERIMENT_A_PLAN.read_text(encoding="utf-8"))
    tuning_ids = {case["case_id"] for case in experiment_a["cases"]}
    selected_ids = [case["case_id"] for case in config["cases"]]
    if tuning_ids.intersection(selected_ids):
        raise ValueError("C2 includes a case from Experiment A")
    if len(selected_ids) != len(set(selected_ids)) or len(selected_ids) != 8:
        raise ValueError("C2 requires the eight unique C1 development cases")
    if sum(len(case["chunks"]) for case in config["cases"]) != config["max_live_calls"]:
        raise ValueError("C2 call ceiling differs from frozen chunks")
    if config["max_live_calls"] != 16 or config["retries"] != 0:
        raise ValueError("C2 call bounds changed")
    if config["reasoning_mode"] != "provider_default" or config["max_tokens"] != 4096:
        raise ValueError("C2 reasoning mode or token limit changed")
    return config, build_holdout(config)


def aggregate_case(
    config: dict, case: dict, outputs: list[IndexedCompactOutput | None]
) -> dict:
    events = [
        event.model_dump(mode="json")
        for output in outputs
        if output is not None
        for event in output.events
    ]
    valid_outputs = [output for output in outputs if output is not None]
    if events or any(output.outcome == "assessed" for output in valid_outputs):
        outcome = "assessed"
    else:
        outcome = "insufficient_evidence"
    prediction = {"outcome": outcome, "events": events}
    indexed_inputs = [chunk["indexed"] for chunk in case["chunks"]]
    passages = {}
    for evidence in indexed_inputs:
        for passage in evidence.passages:
            existing = passages.get(passage.passage_id)
            if existing is not None and existing != passage:
                raise ValueError(
                    f"Conflicting repeated passage ID: {passage.passage_id}"
                )
            passages[passage.passage_id] = passage
    status, error = "succeeded", None
    try:
        validated = IndexedCompactOutput.model_validate(prediction)
        for event in validated.events:
            company_ids = event.subject_company.evidence_passage_ids
            if any(passage_id not in passages for passage_id in company_ids):
                raise IndexedValidationError("invalid_passage_reference")
            if not any(
                event.subject_company.value in passages[passage_id].text
                for passage_id in company_ids
            ):
                raise IndexedValidationError("unsupported_literal_fact")
            for signal in event.signals:
                if any(
                    passage_id not in passages
                    for passage_id in signal.evidence_passage_ids
                ):
                    raise IndexedValidationError("invalid_passage_reference")
    except (IndexedValidationError, ValueError) as exc:
        if isinstance(exc, IndexedValidationError):
            error = exc.code
        else:
            error = "invalid_output_schema"
        status = "failed"
    return {
        "experiment_id": config["experiment_id"],
        "arm": ARM,
        "case_id": case["row"]["case_id"],
        "scoring_set": case["plan"]["scoring_set"],
        "variant": case["row"]["variant"],
        "input_fingerprint": case["row"]["input_fingerprint"],
        "prediction": prediction,
        "validation_status": status,
        "error": error,
        "validation_checks": {
            "json_object": True,
            "typed_schema": status == "succeeded" or error != "invalid_output_schema",
            "allowed_signal_keys": status == "succeeded"
            or error != "invalid_output_schema",
            "passage_references_valid": error != "invalid_passage_reference",
            "passage_reference_count": sum(
                len(event["subject_company"]["evidence_passage_ids"])
                + sum(
                    len(signal["evidence_passage_ids"]) for signal in event["signals"]
                )
                for event in events
            ),
            "invalid_passage_references": (
                [] if error != "invalid_passage_reference" else ["aggregate"]
            ),
            "schema_errors": [],
        },
        "aggregation": {
            "validated_chunk_outputs_included": len(valid_outputs),
            "chunk_count": len(case["chunks"]),
            "deduplication": "none",
            "semantic_merging": "none",
            "event_count": len(events),
        },
    }


async def run(live: bool, resume: bool = False) -> None:
    config, cases = load_configuration()
    settings = get_settings()
    if settings.nemotron_super_model != config["model"] or not settings.nebius_api_key:
        raise ValueError(
            "Configured Nebius credentials and frozen Super model required"
        )
    expected_calls = [
        (case["row"]["case_id"], chunk["chunk_id"])
        for case in cases
        for chunk in case["chunks"]
    ]
    saved_chunks = read_jsonl(CHUNK_OUTPUT)
    saved_aggregates = read_jsonl(CASE_OUTPUT)
    saved_calls = [(row["case_id"], row["chunk_id"]) for row in saved_chunks]
    saved_case_ids = [row["case_id"] for row in saved_aggregates]
    expected_case_ids = [case["row"]["case_id"] for case in cases]
    if saved_calls != expected_calls[: len(saved_calls)]:
        raise ValueError("Saved C2 calls are not an exact frozen prefix")
    if saved_case_ids != expected_case_ids[: len(saved_case_ids)]:
        raise ValueError("Saved C2 aggregates are not an exact frozen prefix")
    remaining_calls = len(expected_calls) - len(saved_calls)
    print(
        json.dumps(
            {
                "preflight": "passed",
                "experiment": config["experiment_id"],
                "cases": len(cases),
                "clear_cases": sum(
                    case["plan"]["scoring_set"] == "clear" for case in cases
                ),
                "manual_review_cases": sum(
                    case["plan"]["scoring_set"] == "manual_review" for case in cases
                ),
                "calls": len(expected_calls),
                "saved_calls": len(saved_calls),
                "remaining_calls": remaining_calls,
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "reasoning_mode": config["reasoning_mode"],
                "contract": config["contract"],
                "resume": resume,
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return
    if resume:
        if not CHUNK_OUTPUT.exists() or not CASE_OUTPUT.exists() or not LOCAL.exists():
            raise FileNotFoundError("C2 resume requires preserved partial artifacts")
        if remaining_calls == 0 and len(saved_aggregates) == len(cases):
            raise FileExistsError("C2 is already complete")
        write_new(
            LOCAL / "resume_metadata.json",
            {
                "resumed_at": datetime.now(UTC).isoformat(),
                "saved_provider_calls": len(saved_calls),
                "remaining_new_provider_calls": remaining_calls,
                "repeated_provider_calls": 0,
                "reason": "resume after aggregate-only passage-count failure",
                "runner_sha256": sha256(Path(__file__)),
                "gold_loaded_by_runner": False,
            },
        )
        chunk_mode = case_mode = "a"
    else:
        if CHUNK_OUTPUT.exists() or CASE_OUTPUT.exists() or LOCAL.exists():
            raise FileExistsError("Existing C2 run found; use prefix-safe --resume")
        OUT.mkdir(parents=True, exist_ok=True)
        LOCAL.mkdir(parents=True)
        write_new(
            LOCAL / "run_metadata.json",
            {
                "started_at": datetime.now(UTC).isoformat(),
                "experiment_id": config["experiment_id"],
                "arm": ARM,
                "case_ids": expected_case_ids,
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "response_format": response_format(),
                "reasoning_mode": config["reasoning_mode"],
                "chat_template_kwargs": "not sent",
                "contract": config["contract"],
                "plan_sha256": sha256(PLAN_PATH),
                "runner_sha256": sha256(Path(__file__)),
                "automatic_retries": 0,
                "sampling": "provider defaults; no sampling fields sent",
                "http_timeout_seconds": config["timeout_seconds"],
                "gold_loaded_by_runner": False,
            },
        )
        chunk_mode = case_mode = "x"
    saved_by_call = {(row["case_id"], row["chunk_id"]): row for row in saved_chunks}
    saved_aggregate_ids = set(saved_case_ids)
    new_provider_calls = 0
    with (
        CHUNK_OUTPUT.open(chunk_mode, encoding="utf-8", newline="\n") as chunk_stream,
        CASE_OUTPUT.open(case_mode, encoding="utf-8", newline="\n") as case_stream,
    ):
        for case in cases:
            outputs = []
            case_id = case["row"]["case_id"]
            case_local = LOCAL / case_id
            case_local.mkdir(exist_ok=True)
            for chunk in case["chunks"]:
                chunk_id = chunk["chunk_id"]
                saved = saved_by_call.get((case_id, chunk_id))
                if saved is not None:
                    outputs.append(
                        IndexedCompactOutput.model_validate(saved["validated_output"])
                        if saved["validation_status"] == "succeeded"
                        else None
                    )
                    continue
                indexed = chunk["indexed"]
                provider_messages = messages(indexed)
                request_path = case_local / f"{chunk_id}_request.json"
                response_path = case_local / f"{chunk_id}_response.json"
                client = IndexedCompactClient(
                    expected_messages=provider_messages,
                    model=config["model"],
                    max_tokens=config["max_tokens"],
                    error_path=case_local / f"{chunk_id}_http_error.json",
                )
                write_new(
                    request_path,
                    client.payload(
                        provider_messages, config["model"], config["max_tokens"]
                    ),
                )
                started = time.monotonic()
                raw = await client.chat_completion(
                    provider_messages,
                    model=config["model"],
                    max_tokens=config["max_tokens"],
                )
                write_new(response_path, raw)
                prediction = None
                output = None
                status, error = "failed", None
                choice = (raw.get("choices") or [{}])[0]
                if choice.get("finish_reason") != "stop":
                    error = "incomplete_model_response"
                try:
                    content = choice["message"]["content"]
                    prediction = json.loads(content)
                    if error is None:
                        output = validate_output(content, indexed)
                        status = "succeeded"
                except IndexedValidationError as exc:
                    error = exc.code
                except (KeyError, IndexError, TypeError, ValueError):
                    error = error or "invalid_provider_response"
                outputs.append(output)
                usage = raw.get("usage") or {}
                record = {
                    "experiment_id": config["experiment_id"],
                    "arm": ARM,
                    "case_id": case_id,
                    "scoring_set": case["plan"]["scoring_set"],
                    "variant": case["row"]["variant"],
                    "source_input_fingerprint": case["row"]["input_fingerprint"],
                    "chunk_id": chunk_id,
                    "indexed_input_fingerprint": indexed.input_fingerprint,
                    "body_characters": len(chunk["document"].blocks[-1].text),
                    "passage_count": len(indexed.passages),
                    "model": config["model"],
                    "max_tokens": config["max_tokens"],
                    "reasoning_mode": config["reasoning_mode"],
                    "contract": config["contract"],
                    "prediction": prediction,
                    "raw_response": raw,
                    "validation_status": status,
                    "error": error,
                    "validation_checks": diagnostics(raw, indexed),
                    "validated_output": output.model_dump(mode="json")
                    if output
                    else None,
                    "completed_at": datetime.now(UTC).isoformat(),
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "request_sha256": sha256(request_path),
                    "response_format_fingerprint": config[
                        "response_format_fingerprint"
                    ],
                }
                chunk_stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                chunk_stream.flush()
                os.fsync(chunk_stream.fileno())
                new_provider_calls += 1
                print(
                    json.dumps(
                        {
                            "case_id": case_id,
                            "chunk_id": chunk_id,
                            "status": status,
                            "error": error,
                            "events": len(output.events) if output else None,
                            "finish_reason": choice.get("finish_reason"),
                            "reasoning_tokens": (
                                usage.get("completion_tokens_details") or {}
                            ).get("reasoning_tokens"),
                        }
                    ),
                    flush=True,
                )
                if error and error.startswith("provider_"):
                    raise RuntimeError(
                        "Provider failure recorded; C2 stopped without retry"
                    )
            if case_id not in saved_aggregate_ids:
                aggregate = aggregate_case(config, case, outputs)
                case_stream.write(json.dumps(aggregate, ensure_ascii=False) + "\n")
                case_stream.flush()
                os.fsync(case_stream.fileno())
    final_chunks = read_jsonl(CHUNK_OUTPUT)
    final_aggregates = read_jsonl(CASE_OUTPUT)
    print(
        json.dumps(
            {
                "saved_chunk_responses": len(final_chunks),
                "saved_case_aggregates": len(final_aggregates),
                "new_provider_calls": new_provider_calls,
                "repeated_provider_calls": 0,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.live, args.resume))
