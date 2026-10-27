"""Offline evaluation CLI and bounded, explicitly injected extraction batch runner."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.models import SearchJob, SearchQuery, SearchResult
from app.search.evidence import (
    PreparedEvidence,
    fingerprint,
    group_identical_evidence,
    prepare_search_result,
)
from app.search.extraction_contract import SemanticExtractionInput
from app.search.extractor import ExtractionResult, SemanticExtractor


@dataclass(frozen=True)
class EvaluatedEvidence:
    evidence: PreparedEvidence
    result: ExtractionResult


async def evaluate_prepared_evidence(
    items: Iterable[PreparedEvidence],
    extractor: SemanticExtractor,
    *,
    max_model_calls: int,
) -> list[EvaluatedEvidence]:
    groups = group_identical_evidence(items)
    # Reject the whole batch before any call rather than silently exceed a budget.
    if max_model_calls < 0 or len(groups) > max_model_calls:
        raise ValueError("Unique evidence count exceeds the explicit evaluation call budget")
    return [EvaluatedEvidence(item, await extractor.extract(item)) for item in groups]


def _fixture_evidence(case: dict) -> list[PreparedEvidence]:
    """Use transient ORM records to exercise preparation; never connect to a database."""
    workspace_id = uuid5(NAMESPACE_URL, "radory-offline-evaluation-workspace")
    job = SearchJob(id=uuid5(NAMESPACE_URL, case["name"]), workspace_id=workspace_id)
    prepared = []
    for index, source in enumerate(case["sources"]):
        query = SearchQuery(
            id=uuid5(job.id, f"query-{index}"),
            job_id=job.id,
            job=job,
            signal_key=source["discovery_signal"],
            query_text=source["query_text"],
            preferred_domains=source.get("preferred_domains", ["example.com"]),
            include_domains_mode="prefer",
        )
        result = SearchResult(
            id=uuid5(job.id, f"result-{index}"),
            search_query_id=query.id,
            search_query=query,
            result_rank=1,
            title=source["title"],
            url=source["url"],
            content=source["snippet"],
            raw_payload={"raw_content": source.get("raw_content")},
            created_at=datetime(2026, 10, 27, tzinfo=UTC),
            provider_score=0.9,
            published_at=None,
        )
        prepared.append(prepare_search_result(result, workspace_id=workspace_id))
    return prepared


class FixtureCompletionClient:
    """Replay explicitly authored outputs; this does not simulate model reasoning."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.calls = 0

    async def chat_completion(self, messages, model=None, max_tokens=None) -> dict:
        payload = SemanticExtractionInput.model_validate_json(messages[1]["content"])
        response = self.responses[fingerprint(payload.model_dump(mode="json"))]
        self.calls += 1
        return {
            "id": f"offline-fixture-{self.calls}",
            "model": "offline-fixture",
            "choices": [{"finish_reason": "stop", "message": {"content": response}}],
        }


def candidate_signature(result: ExtractionResult) -> dict:
    events = []
    if result.output is not None:
        for event in result.output.events:
            events.append(
                {
                    "company": event.subject_company.value,
                    "signals": sorted(signal.signal_key for signal in event.signals),
                    "stage": event.stage.value,
                    "locations": [
                        {
                            "country": location.country.value if location.country else None,
                            "market": location.market.value if location.market else None,
                            "submarket": location.submarket.value if location.submarket else None,
                            "role": location.role,
                        }
                        for location in event.locations
                    ],
                    "timing": [timing.expression for timing in event.timing],
                    "missing_facts": sorted(event.missing_facts),
                }
            )
    return {
        "status": result.status,
        "error_code": result.error_code,
        "outcome": result.output.outcome if result.output else None,
        "events": events,
    }


async def run_fixture_evaluation(path: Path) -> dict:
    cases = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for case in cases:
        try:
            prepared = _fixture_evidence(case)
        except ValueError:
            rows.append(
                {
                    "case": case["name"],
                    "passed": case.get("expected_preparation_error", False),
                    "preparation_status": "unavailable",
                    "source_count": len(case["sources"]),
                    "unique_inputs": 0,
                    "model_calls": 0,
                    "evaluations": [],
                }
            )
            continue
        responses = {}
        response = case["model_response"]
        response_text = response if isinstance(response, str) else json.dumps(response)
        for item in prepared:
            payload = SemanticExtractionInput.from_document(item.document).model_dump(mode="json")
            responses[fingerprint(payload)] = response_text
        client = FixtureCompletionClient(responses)
        evaluated = await evaluate_prepared_evidence(
            prepared,
            SemanticExtractor(client, model="offline-fixture"),
            max_model_calls=case["max_model_calls"],
        )
        evaluations = []
        for item in evaluated:
            signature = candidate_signature(item.result)
            evaluations.append(
                {
                    "input_fingerprint": item.evidence.input_fingerprint,
                    "content_basis": item.evidence.document.content_basis,
                    "signature": signature,
                    "passed": signature == case["expected"],
                    "candidate_output": (
                        item.result.output.model_dump(mode="json") if item.result.output else None
                    ),
                    "sources": [
                        {
                            "result_id": str(source.search_result_id),
                            "query_id": str(source.search_query_id),
                            "job_id": str(source.search_job_id),
                            "workspace_id": str(source.workspace_id),
                            "url": source.url,
                            "discovery_signal": source.discovery_signal,
                            "matched_preferred_domains": list(source.matched_preferred_domains),
                        }
                        for source in item.evidence.sources
                    ],
                }
            )
        rows.append(
            {
                "case": case["name"],
                "passed": bool(evaluations) and all(row["passed"] for row in evaluations),
                "preparation_status": "prepared",
                "source_count": len(prepared),
                "unique_inputs": len(evaluated),
                "model_calls": client.calls,
                "evaluations": evaluations,
            }
        )
    return {
        "mode": "offline_fixture_replay",
        "limitations": [
            "Synthetic documents and authored model responses; not measured Nemotron accuracy.",
            "Quotation matching does not prove semantic entailment.",
            "Duplicate reuse is within this batch; no durable cache or cross-process claim exists.",
        ],
        "cases": len(rows),
        "passed": sum(row["passed"] for row in rows),
        "failed": sum(not row["passed"] for row in rows),
        "model_calls": sum(row["model_calls"] for row in rows),
        "live_provider_calls": 0,
        "results": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Create a new report; never overwrite one")
    args = parser.parse_args()
    report = asyncio.run(run_fixture_evaluation(args.fixtures))
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as output:
            output.write(rendered)
        print(
            json.dumps(
                {
                    key: report[key]
                    for key in (
                        "mode",
                        "cases",
                        "passed",
                        "failed",
                        "model_calls",
                        "live_provider_calls",
                    )
                }
            )
        )
    else:
        print(rendered)
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
