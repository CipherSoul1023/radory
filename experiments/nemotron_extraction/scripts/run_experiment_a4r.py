"""Run the bounded default-versus-no-think A4-R experiment."""

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

from run_experiment_a import PLAN_PATH as A_PLAN_PATH
from run_experiment_a3 import (
    A3_PLAN_PATH,
    A3NebiusClient,
    response_format,
)
from run_experiment_a3 import ARM as A3_ARM
from run_experiment_a3 import OUT as A3_OUT
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

PLAN_PATH = BASE / "cases" / "experiment_a4r_v1.json"
OUT = BASE / "results" / "experiment_a4r_v1"
LOCAL = BASE / "results" / "local" / "experiment_a4r_v1"
ARMS = ("a4r_default_4096", "a4r_no_think_4096")


class DirectiveRecordingClient:
    """Inject the arm directive at the provider boundary and record the response."""

    def __init__(
        self,
        client,
        extractor_messages: list[dict[str, str]],
        provider_messages: list[dict[str, str]],
        raw_path: Path,
    ) -> None:
        self.client = client
        self.extractor_messages = extractor_messages
        self.provider_messages = provider_messages
        self.raw_path = raw_path
        self.response = None
        self.calls = 0

    async def chat_completion(self, messages, model=None, max_tokens=None):
        if messages != self.extractor_messages:
            raise ValueError("Extractor request differs from audited frozen messages")
        if self.calls:
            raise ValueError("One request per case; retries are forbidden")
        self.calls += 1
        response = await self.client.chat_completion(
            self.provider_messages,
            model=model,
            max_tokens=max_tokens,
        )
        write_new(self.raw_path, response)
        self.response = response
        return response


def load_configuration() -> tuple[dict, dict]:
    config = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    parent = json.loads(A_PLAN_PATH.read_text(encoding="utf-8"))
    a3_predictions = A3_OUT / f"{A3_ARM}_predictions.jsonl"
    if sha256(A3_PLAN_PATH) != config["a3_plan_sha256"]:
        raise ValueError("Frozen A3 plan changed")
    if sha256(a3_predictions) != config["a3_predictions_sha256"]:
        raise ValueError("Frozen A3 predictions changed")
    if fingerprint(response_format()) != config["response_format_fingerprint"]:
        raise ValueError("Pattern-free strict provider schema changed")
    if config["model"] != parent["model"] or config["max_tokens"] != 4096:
        raise ValueError(
            "A4-R model or token limit differs from the frozen configuration"
        )
    if config["max_live_calls"] != 10 or config["retries"] != 0:
        raise ValueError("A4-R live-call bounds changed")
    if [arm["name"] for arm in config["arms"]] != list(ARMS):
        raise ValueError("A4-R arms changed")
    return config, parent


def messages_for_arm(messages: list[dict[str, str]], arm: str) -> list[dict[str, str]]:
    changed = copy.deepcopy(messages)
    if arm == ARMS[0]:
        return changed
    if arm != ARMS[1] or changed[0].get("role") != "system":
        raise ValueError("Unsupported A4-R arm or message structure")
    changed[0]["content"] = "/no_think\n" + changed[0]["content"]
    return changed


async def run(arm: str | None, live: bool) -> None:
    config, parent = load_configuration()
    selected_ids = [row["case_id"] for row in config["cases"]]
    parent_ids = {row["case_id"] for row in parent["cases"]}
    if not set(selected_ids).issubset(parent_ids):
        raise ValueError("A4-R includes a case outside frozen Experiment A")
    inputs = {
        row["case_id"]: (row, evidence, messages)
        for row, evidence, messages in load_inputs()
    }
    prepared = [inputs[case_id] for case_id in selected_ids]
    for planned, (row, _, _) in zip(config["cases"], prepared, strict=True):
        if row["variant"] != planned["variant"]:
            raise ValueError("A4-R evidence variant changed")
    settings = get_settings()
    if settings.nemotron_super_model != config["model"] or not settings.nebius_api_key:
        raise ValueError(
            "Configured Nebius credentials and frozen Super model required"
        )
    print(
        json.dumps(
            {
                "preflight": "passed",
                "arm": arm,
                "cases": selected_ids,
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "directive": None if arm == ARMS[0] else "/no_think",
                "directive_placement": None
                if arm == ARMS[0]
                else "first line of system message",
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return
    if arm not in ARMS:
        raise ValueError("Choose an explicit A4-R arm")
    if arm == ARMS[1]:
        default_output = OUT / f"{ARMS[0]}_predictions.jsonl"
        if not default_output.exists() or len(
            default_output.read_text(encoding="utf-8").splitlines()
        ) != len(selected_ids):
            raise ValueError("Complete the default arm before the no-think arm")
    output = OUT / f"{arm}_predictions.jsonl"
    arm_local = LOCAL / arm
    if output.exists() or arm_local.exists():
        raise FileExistsError("Existing A4-R arm found; no overwriting or paid retries")
    OUT.mkdir(parents=True, exist_ok=True)
    arm_local.mkdir(parents=True)
    write_new(
        arm_local / "run_metadata.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "experiment_id": config["experiment_id"],
            "arm": arm,
            "model": config["model"],
            "max_tokens": config["max_tokens"],
            "response_format": response_format(),
            "directive": None if arm == ARMS[0] else "/no_think",
            "directive_placement": None
            if arm == ARMS[0]
            else "first line of system message",
            "plan_sha256": sha256(PLAN_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "automatic_retries": 0,
            "sampling_and_reasoning": "provider defaults; no request-level reasoning controls",
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
            messages = messages_for_arm(original_messages, arm)
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
            recorder = DirectiveRecordingClient(
                client,
                original_messages,
                messages,
                arm_local / f"{case_id}_response.json",
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
                "arm": arm,
                "case_id": case_id,
                "role": next(
                    item["role"]
                    for item in config["cases"]
                    if item["case_id"] == case_id
                ),
                "variant": row["variant"],
                "input_fingerprint": row["input_fingerprint"],
                "model": config["model"],
                "max_tokens": config["max_tokens"],
                "directive": None if arm == ARMS[0] else "/no_think",
                "prediction": prediction,
                "raw_response": raw,
                "validation_status": result.status,
                "error": result.error_code,
                "validation_checks": diagnostics(
                    raw, SemanticExtractionInput.from_document(evidence.document)
                ),
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
                        "arm": arm,
                        "case_id": case_id,
                        "status": result.status,
                        "error": result.error_code,
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
                    "Provider failure recorded; A4-R stopped without retry"
                )
    print(json.dumps({"arm": arm, "saved_cases": len(selected_ids)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.arm, args.live))
