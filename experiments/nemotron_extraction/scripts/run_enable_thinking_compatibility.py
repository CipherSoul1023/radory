"""Run a two-call Nebius enable_thinking compatibility probe."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from run_pilot_v1 import BASE, get_settings, sha256, write_new

PLAN_PATH = BASE / "cases" / "enable_thinking_compatibility_v1.json"
OUT = BASE / "results" / "enable_thinking_compatibility_v1"
LOCAL = BASE / "results" / "local" / "enable_thinking_compatibility_v1"
ARMS = ("provider_default", "enable_thinking_false")


def response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "reasoning_control_probe",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"answer": {"type": "integer"}},
                "required": ["answer"],
                "additionalProperties": False,
            },
        },
    }


def load_plan() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if [arm["name"] for arm in plan["arms"]] != list(ARMS):
        raise ValueError("Compatibility-probe arms changed")
    if plan["max_live_calls"] != 2 or plan["retries"] != 0:
        raise ValueError("Compatibility-probe call bounds changed")
    if plan["model"] != "nvidia/nemotron-3-super-120b-a12b":
        raise ValueError("Compatibility-probe model changed")
    return plan


def payload_for_arm(plan: dict, arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError("Unknown compatibility-probe arm")
    payload = {
        "model": plan["model"],
        "messages": [{"role": "user", "content": plan["synthetic_task"]}],
        "max_tokens": plan["max_tokens"],
        "temperature": plan["temperature"],
        "top_p": plan["top_p"],
        "response_format": response_format(),
    }
    if arm == ARMS[1]:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    return payload


def parsed_answer(response: dict | None) -> int | None:
    try:
        content = response["choices"][0]["message"]["content"]
        answer = json.loads(content)["answer"]
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return answer if isinstance(answer, int) and not isinstance(answer, bool) else None


def response_summary(arm: str, status_code: int, response: dict | None, plan: dict) -> dict:
    choice = (response or {}).get("choices", [{}])[0]
    message = choice.get("message", {})
    usage = (response or {}).get("usage", {})
    details = usage.get("completion_tokens_details", {}) or {}
    reasoning_tokens = details.get("reasoning_tokens")
    answer = parsed_answer(response)
    accepted = 200 <= status_code < 300
    final_answer_present = bool(message.get("content"))
    if arm == ARMS[0]:
        classification = "control"
    elif not accepted:
        classification = "rejected"
    elif reasoning_tokens is None:
        classification = "inconclusive"
    elif reasoning_tokens == 0 and answer == plan["expected_answer"] and final_answer_present:
        classification = "effective"
    else:
        classification = "accepted_but_ineffective"
    return {
        "arm": arm,
        "http_status": status_code,
        "provider_accepted": accepted,
        "classification": classification,
        "finish_reason": choice.get("finish_reason"),
        "reasoning_tokens": reasoning_tokens,
        "completion_tokens": usage.get("completion_tokens"),
        "final_answer_present": final_answer_present,
        "parsed_answer": answer,
        "answer_correct": answer == plan["expected_answer"],
    }


async def run(live: bool) -> None:
    plan = load_plan()
    baseline = payload_for_arm(plan, ARMS[0])
    treatment = payload_for_arm(plan, ARMS[1])
    changed_keys = {
        key for key in set(baseline) | set(treatment) if baseline.get(key) != treatment.get(key)
    }
    if changed_keys != {"chat_template_kwargs"}:
        raise ValueError("Treatment differs by more than chat_template_kwargs")
    settings = get_settings()
    if settings.nemotron_super_model != plan["model"] or not settings.nebius_api_key:
        raise ValueError("Configured Nebius credentials and frozen Super model required")
    print(
        json.dumps(
            {
                "preflight": "passed",
                "calls": 2,
                "model": plan["model"],
                "changed_keys": sorted(changed_keys),
                "live": live,
            }
        ),
        flush=True,
    )
    if not live:
        return
    output = OUT / "results.json"
    if output.exists() or LOCAL.exists():
        raise FileExistsError("Existing compatibility probe found; no overwrite or retry")
    OUT.mkdir(parents=True, exist_ok=True)
    LOCAL.mkdir(parents=True)
    write_new(
        LOCAL / "run_metadata.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "experiment_id": plan["experiment_id"],
            "plan_sha256": sha256(PLAN_PATH),
            "runner_sha256": sha256(Path(__file__)),
            "automatic_retries": 0,
            "maximum_provider_calls": 2,
            "request_difference": ["chat_template_kwargs"],
        },
    )
    summaries = []
    async with httpx.AsyncClient(timeout=plan["timeout_seconds"]) as client:
        for arm in ARMS:
            payload = payload_for_arm(plan, arm)
            request_path = LOCAL / f"{arm}_request.json"
            response_path = LOCAL / f"{arm}_response.json"
            write_new(request_path, payload)
            started = time.monotonic()
            response = await client.post(
                settings.nebius_base_url.rstrip("/") + "/chat/completions",
                headers={"Authorization": "Bearer " + settings.nebius_api_key},
                json=payload,
            )
            try:
                response_json = response.json()
            except ValueError:
                response_json = {"non_json_response": True}
            write_new(response_path, response_json)
            summary = response_summary(arm, response.status_code, response_json, plan)
            summary.update(
                {
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "request_sha256": sha256(request_path),
                    "response_sha256": sha256(response_path),
                }
            )
            summaries.append(summary)
            print(json.dumps(summary), flush=True)
            if arm == ARMS[0] and not summary["provider_accepted"]:
                raise RuntimeError("Control request failed; treatment was not sent")
    conclusion = summaries[1]["classification"]
    result = {
        "experiment_id": plan["experiment_id"],
        "model": plan["model"],
        "provider": plan["provider"],
        "calls_made": len(summaries),
        "results": summaries,
        "conclusion": conclusion,
        "proceed_to_a4r2": conclusion == "effective",
        "completed_at": datetime.now(UTC).isoformat(),
    }
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"saved": str(output), "conclusion": conclusion}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.live))
