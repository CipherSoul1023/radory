import json

import pytest
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.integrations.tavily.client import TavilyResponse, TavilyResult
from app.models import RadarOpportunity, SignalObservation
from app.search.extraction_engine import extract_search_job
from app.search.investigation import SemanticInvestigationPlanner
from app.search.opportunity_engine import build_radar_opportunity, list_radar_opportunities
from app.search.synthesis import RadarOpportunityReport, SynthesisResult
from tests.test_extraction_engine import FakeExtractor, discovery_job, supported_output
from tests.test_investigation import FakeClient


class FakeTavily:
    configured = True

    def execute(self, query):
        return TavilyResponse(
            request_id="investigation-request",
            results=[
                TavilyResult(
                    title="Acme plans a Johannesburg office",
                    url="https://example.com/investigation-acme",
                    content="Acme plans to open a Johannesburg office next year.",
                    raw_payload={
                        "raw_content": "Acme plans to open a Johannesburg office next year."
                    },
                )
            ],
        )


class FakeSynthesizer:
    model = "nemotron-ultra"

    async def synthesize(self, case):
        by_signal = {}
        for observation in case.observations:
            by_signal.setdefault(observation.signal_key, []).append(observation.observation_id)
        observation_ids = tuple(item.observation_id for item in case.observations)
        report = RadarOpportunityReport.model_validate(
            {
                "company_name": case.company_name,
                "headline": {
                    "text": "Acme has an emerging office requirement",
                    "observation_ids": observation_ids,
                },
                "summary": {
                    "text": "Discovery and investigation support an office-opening signal.",
                    "observation_ids": observation_ids,
                },
                "opportunity_stage": {
                    "value": "potential_future",
                    "observation_ids": observation_ids,
                },
                "signals": [
                    {"signal_key": key, "observation_ids": ids} for key, ids in by_signal.items()
                ],
                "why_it_matters": {
                    "text": "The premises decision may still be open.",
                    "observation_ids": observation_ids,
                },
                "key_findings": [
                    {
                        "text": "An office opening is planned.",
                        "observation_ids": observation_ids,
                    }
                ],
                "locations": [],
                "timing": [],
                "open_questions": ["Has a lease been signed?"],
                "supporting_source_ids": [item.source_id for item in case.sources],
            }
        )
        return SynthesisResult(
            status="succeeded",
            report=report,
            error_code=None,
            model=self.model,
            provider_request_id="ultra-request",
            usage={"total_tokens": 10},
        )


def planner():
    return SemanticInvestigationPlanner(
        FakeClient(
            json.dumps(
                {
                    "outcome": "investigate",
                    "rationale": "The lease status remains unresolved.",
                    "selected": [
                        {
                            "edge_id": "office_opening__signed_lease",
                            "reason": "Check whether the premises are committed.",
                        }
                    ],
                }
            )
        ),
        model="nemotron-super",
    )


def settings():
    return Settings(
        _env_file=None,
        nemotron_super_model="nemotron-super",
        nemotron_ultra_model="nemotron-ultra",
    )


@pytest.mark.asyncio
async def test_builds_one_persisted_report_from_discovery_and_investigation(
    search_db: Session, search_workspace: dict
):
    job = discovery_job(search_db, search_workspace, usable_results=1)
    await extract_search_job(
        search_db,
        search_job_id=job.id,
        extractor=FakeExtractor(supported_output()),
    )
    observation = search_db.query(SignalObservation).one()

    opportunity, created = await build_radar_opportunity(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        observation_id=observation.id,
        planner=planner(),
        tavily=FakeTavily(),
        extractor=FakeExtractor(supported_output()),
        synthesizer=FakeSynthesizer(),
        settings=settings(),
    )

    assert created is True
    assert opportunity.status == "completed"
    assert opportunity.report["company_name"] == "Acme"
    assert opportunity.investigation_decision["outcome"] == "investigate"
    assert len(opportunity.investigation_queries) == 1
    assert len(opportunity.investigation_observations) == 1
    assert opportunity.synthesis_model == "nemotron-ultra"
    assert search_db.query(RadarOpportunity).count() == 1

    repeated, created = await build_radar_opportunity(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        observation_id=observation.id,
        planner=planner(),
        tavily=FakeTavily(),
        extractor=FakeExtractor(supported_output()),
        synthesizer=FakeSynthesizer(),
        settings=settings(),
    )
    assert created is False
    assert repeated.id == opportunity.id
    assert search_db.query(RadarOpportunity).count() == 1


@pytest.mark.asyncio
async def test_completed_reports_are_workspace_scoped(search_db: Session, search_workspace: dict):
    job = discovery_job(search_db, search_workspace, usable_results=1)
    await extract_search_job(
        search_db,
        search_job_id=job.id,
        extractor=FakeExtractor(supported_output()),
    )
    observation = search_db.query(SignalObservation).one()
    await build_radar_opportunity(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        observation_id=observation.id,
        planner=planner(),
        tavily=FakeTavily(),
        extractor=FakeExtractor(supported_output()),
        synthesizer=FakeSynthesizer(),
        settings=settings(),
    )

    assert (
        len(
            list_radar_opportunities(
                search_db,
                workspace_id=search_workspace["workspace"].id,
            )
        )
        == 1
    )
    assert (
        list_radar_opportunities(
            search_db,
            workspace_id=job.id.__class__(int=0),
        )
        == []
    )
