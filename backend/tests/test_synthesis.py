import json
from uuid import UUID

import pytest

from app.core.config import Settings
from app.search.synthesis import (
    RadarOpportunityReport,
    SemanticSynthesizer,
    SynthesisCase,
    SynthesisObservation,
    SynthesisSource,
    SynthesisValidationError,
    synthesize_opportunity,
    validate_synthesis_report,
)

DISCOVERY_ID = UUID("00000000-0000-0000-0000-000000000001")
INVESTIGATION_ID = UUID("00000000-0000-0000-0000-000000000002")


def synthesis_case() -> SynthesisCase:
    return SynthesisCase(
        company_name="Acme",
        observations=(
            SynthesisObservation(
                observation_id=DISCOVERY_ID,
                origin="discovery",
                signal_key="market_entry",
                subject_company="Acme",
                summary="Acme plans to enter South Africa.",
                stage="planned",
                locations=(
                    {
                        "country": {"value": "South Africa"},
                        "market": None,
                        "submarket": None,
                    },
                ),
                timing=(),
                missing_facts=("workplace_plans",),
                source_ids=("discovery-1",),
            ),
            SynthesisObservation(
                observation_id=INVESTIGATION_ID,
                origin="investigation",
                signal_key="office_opening",
                subject_company="Acme",
                summary="Acme is evaluating a Johannesburg office.",
                stage="underway",
                locations=(
                    {
                        "country": {"value": "South Africa"},
                        "market": {"value": "Johannesburg"},
                        "submarket": None,
                    },
                ),
                timing=({"expression": "2027", "precision": "year"},),
                missing_facts=(),
                source_ids=("investigation-1",),
            ),
        ),
        sources=(
            SynthesisSource(
                source_id="discovery-1",
                origin="discovery",
                title="Acme enters South Africa",
                url="https://example.com/discovery",
            ),
            SynthesisSource(
                source_id="investigation-1",
                origin="investigation",
                title="Acme evaluates Johannesburg office",
                url="https://example.com/investigation",
            ),
        ),
    )


def report_payload() -> dict:
    return {
        "company_name": "Acme",
        "headline": {
            "text": "Acme is evaluating Johannesburg office space",
            "observation_ids": [str(DISCOVERY_ID), str(INVESTIGATION_ID)],
        },
        "summary": {
            "text": "Acme plans to enter South Africa and is evaluating an office.",
            "observation_ids": [str(DISCOVERY_ID), str(INVESTIGATION_ID)],
        },
        "opportunity_stage": {
            "value": "active_evaluation",
            "observation_ids": [str(INVESTIGATION_ID)],
        },
        "signals": [
            {"signal_key": "market_entry", "observation_ids": [str(DISCOVERY_ID)]},
            {
                "signal_key": "office_opening",
                "observation_ids": [str(INVESTIGATION_ID)],
            },
        ],
        "why_it_matters": {
            "text": "The location decision appears unresolved.",
            "observation_ids": [str(INVESTIGATION_ID)],
        },
        "key_findings": [
            {
                "text": "South African entry is planned.",
                "observation_ids": [str(DISCOVERY_ID)],
            },
            {
                "text": "Johannesburg office evaluation is underway.",
                "observation_ids": [str(INVESTIGATION_ID)],
            },
        ],
        "locations": [
            {
                "country": "South Africa",
                "market": "Johannesburg",
                "submarket": None,
                "observation_ids": [str(INVESTIGATION_ID)],
            }
        ],
        "timing": [{"expression": "2027", "observation_ids": [str(INVESTIGATION_ID)]}],
        "open_questions": ["Has a lease already been signed?"],
        "supporting_source_ids": ["discovery-1", "investigation-1"],
    }


def test_validates_combined_discovery_and_investigation_report():
    report = RadarOpportunityReport.model_validate(report_payload())

    assert validate_synthesis_report(report, synthesis_case()) is report
    assert {signal.signal_key for signal in report.signals} == {
        "market_entry",
        "office_opening",
    }


def test_rejects_signal_cited_to_wrong_observation():
    payload = report_payload()
    payload["signals"][1]["observation_ids"] = [str(DISCOVERY_ID)]
    report = RadarOpportunityReport.model_validate(payload)

    with pytest.raises(SynthesisValidationError, match="unsupported_signal_reference"):
        validate_synthesis_report(report, synthesis_case())


def test_rejects_location_not_present_in_validated_observations():
    payload = report_payload()
    payload["locations"][0]["market"] = "Cape Town"
    report = RadarOpportunityReport.model_validate(payload)

    with pytest.raises(SynthesisValidationError, match="unsupported_location"):
        validate_synthesis_report(report, synthesis_case())


class FakeClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = []

    async def chat_completion(self, messages, model=None, max_tokens=None):
        self.calls.append((messages, model, max_tokens))
        return {
            "id": "ultra-request-1",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(self.payload)},
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        }


@pytest.mark.asyncio
async def test_ultra_synthesizer_returns_validated_report():
    client = FakeClient(report_payload())
    synthesizer = SemanticSynthesizer(client, model="nemotron-ultra")

    result = await synthesizer.synthesize(synthesis_case())

    assert result.status == "succeeded"
    assert result.report is not None
    assert result.report.opportunity_stage.value == "active_evaluation"
    assert client.calls[0][1:] == ("nemotron-ultra", 4096)


@pytest.mark.asyncio
async def test_ultra_synthesizer_rejects_unknown_source():
    payload = report_payload()
    payload["supporting_source_ids"] = ["invented-source"]
    result = await SemanticSynthesizer(
        FakeClient(payload),
        model="nemotron-ultra",
    ).synthesize(synthesis_case())

    assert result.status == "failed"
    assert result.error_code == "unknown_source_reference"


@pytest.mark.asyncio
async def test_default_synthesis_coordinator_uses_configured_ultra_model():
    client = FakeClient(report_payload())
    settings = Settings(
        _env_file=None,
        nemotron_ultra_model="nvidia/nemotron-ultra",
        nemotron_synthesis_max_tokens=6000,
    )

    result = await synthesize_opportunity(
        synthesis_case(),
        client=client,
        settings=settings,
    )

    assert result.status == "succeeded"
    assert client.calls[0][1:] == ("nvidia/nemotron-ultra", 6000)
