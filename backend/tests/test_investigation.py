import json

import pytest
from sqlalchemy.orm import Session

from app.integrations.tavily.client import TavilyResponse, TavilyResult
from app.models import SignalObservation
from app.search.extraction_engine import extract_search_job
from app.search.investigation import (
    INVESTIGATION_EDGES,
    INVESTIGATION_SOURCE_REGISTRY,
    InvestigationCase,
    InvestigationDecision,
    InvestigationObservation,
    SemanticInvestigationPlanner,
    build_investigation_plans,
    candidate_edges,
    investigate_observation,
    load_investigation_case,
)
from app.search.signal_library import SIGNAL_LIBRARY
from tests.test_extraction_engine import FakeExtractor, discovery_job, supported_output


def case() -> InvestigationCase:
    return InvestigationCase(
        company_name='Acme "Holdings"',
        country="South Africa",
        market="Johannesburg",
        submarket="Sandton",
        observations=(
            InvestigationObservation(
                signal_key="market_entry",
                summary="Acme plans to enter South Africa.",
                stage="planned",
                missing_facts=("workplace_plans",),
                supporting_passages=("Acme plans to enter South Africa.",),
            ),
        ),
    )


def test_catalogue_covers_all_signals_and_sources():
    assert len(INVESTIGATION_EDGES) == 67
    assert len(INVESTIGATION_SOURCE_REGISTRY) == 30
    assert {edge.initial_signal for edge in INVESTIGATION_EDGES.values()} == set(SIGNAL_LIBRARY)
    assert all(edge.initial_signal != edge.target_signal for edge in INVESTIGATION_EDGES.values())


def test_candidates_are_only_for_observed_signals_and_ordered_by_priority():
    candidates = candidate_edges(case())

    assert len(candidates) == 6
    assert {edge.initial_signal for edge in candidates} == {"market_entry"}
    assert [edge.priority for edge in candidates] == sorted(edge.priority for edge in candidates)


def test_builds_only_ai_selected_queries_and_escapes_quotes():
    decision = InvestigationDecision.model_validate(
        {
            "outcome": "investigate",
            "rationale": "The physical workplace plan is unresolved.",
            "selected": [
                {
                    "edge_id": "market_entry__office_opening",
                    "reason": "Determine whether a physical office is planned.",
                }
            ],
        }
    )

    plans = build_investigation_plans(case(), decision)

    assert len(plans) == 1
    assert plans[0].query_text == '"Acme Holdings" "South Africa" new office plans'
    assert plans[0].target_signal == "office_opening"
    assert plans[0].include_domains_mode == "prefer"


def test_stop_decision_creates_no_queries():
    decision = InvestigationDecision(
        outcome="stop",
        rationale="The matching office move is already completed.",
    )

    assert build_investigation_plans(case(), decision) == ()


def test_rejects_edge_unavailable_to_observed_signal():
    decision = InvestigationDecision.model_validate(
        {
            "outcome": "investigate",
            "rationale": "Try an unrelated route.",
            "selected": [
                {
                    "edge_id": "signed_lease__completed_move",
                    "reason": "Not available for market entry.",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="unavailable"):
        build_investigation_plans(case(), decision)


class FakeClient:
    def __init__(self, content):
        self.content = content
        self.calls = []

    async def chat_completion(self, messages, model=None, max_tokens=None):
        self.calls.append((messages, model, max_tokens))
        return {
            "id": "request-1",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": self.content},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


@pytest.mark.asyncio
async def test_semantic_planner_selects_from_bounded_candidates():
    client = FakeClient(
        json.dumps(
            {
                "outcome": "investigate",
                "rationale": "The workplace plan is unresolved.",
                "selected": [
                    {
                        "edge_id": "market_entry__office_opening",
                        "reason": "Check for a physical office plan.",
                    }
                ],
            }
        )
    )
    planner = SemanticInvestigationPlanner(client, model="nemotron-super")

    result = await planner.decide(case())

    assert result.status == "succeeded"
    assert result.decision is not None
    assert result.decision.selected[0].edge_id == "market_entry__office_opening"
    sent_payload = json.loads(client.calls[0][0][1]["content"])
    assert len(sent_payload["candidate_edges"]) == 6
    assert client.calls[0][1:] == ("nemotron-super", 2048)


@pytest.mark.asyncio
async def test_semantic_planner_rejects_unavailable_edge():
    client = FakeClient(
        json.dumps(
            {
                "outcome": "investigate",
                "rationale": "Invalid route.",
                "selected": [
                    {
                        "edge_id": "signed_lease__completed_move",
                        "reason": "Not a candidate.",
                    }
                ],
            }
        )
    )

    result = await SemanticInvestigationPlanner(client, model="nemotron-super").decide(case())

    assert result.status == "failed"
    assert result.error_code == "invalid_investigation_decision"


class FakeTavily:
    configured = True

    def __init__(self):
        self.calls = []

    def execute(self, query):
        self.calls.append(query)
        return TavilyResponse(
            request_id="tavily-1",
            results=[
                TavilyResult(
                    title="Acme considers a Johannesburg office",
                    url="https://example.com/acme",
                    content="Acme is considering office options.",
                    raw_payload={"raw_content": "Acme is considering office options."},
                )
            ],
        )


@pytest.mark.asyncio
async def test_loads_workspace_case_and_executes_bounded_live_queries(
    search_db: Session, search_workspace: dict
):
    job = discovery_job(search_db, search_workspace, usable_results=1)
    await extract_search_job(
        search_db,
        search_job_id=job.id,
        extractor=FakeExtractor(supported_output()),
    )
    observation = search_db.query(SignalObservation).one()
    loaded = load_investigation_case(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        observation_id=observation.id,
    )
    assert loaded.company_name == "Acme"
    assert loaded.country == job.country

    client = FakeClient(
        json.dumps(
            {
                "outcome": "investigate",
                "rationale": "The office commitment is unresolved.",
                "selected": [
                    {
                        "edge_id": "office_opening__signed_lease",
                        "reason": "Check whether the requirement is already committed.",
                    }
                ],
            }
        )
    )
    tavily = FakeTavily()

    execution = await investigate_observation(
        search_db,
        workspace_id=search_workspace["workspace"].id,
        observation_id=observation.id,
        planner=SemanticInvestigationPlanner(client, model="nemotron-super"),
        tavily=tavily,
    )

    assert execution.decision.outcome == "investigate"
    assert len(execution.queries) == 1
    assert execution.queries[0].request_id == "tavily-1"
    assert tavily.calls[0].include_raw_content is True
    assert tavily.calls[0].max_results == 5
