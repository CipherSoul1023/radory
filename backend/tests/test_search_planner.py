import uuid

import pytest

from app.search.planner import BrokerSearchContext, build_discovery_search_plans


def build_plans(submarkets: tuple[str, ...]):
    return build_discovery_search_plans(
        job_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        profile=BrokerSearchContext(
            country="South Africa",
            market="Johannesburg",
            submarkets=submarkets,
        ),
    )


@pytest.mark.parametrize(
    ("submarkets", "expected_phrase", "unexpected_phrase"),
    [
        ((), "Johannesburg new headquarters opening", "  "),
        (("Sandton",), "Sandton Johannesburg new headquarters opening", "Rosebank"),
        (
            ("Sandton", "Rosebank"),
            "Sandton Johannesburg new headquarters opening",
            "Rosebank Johannesburg new headquarters opening",
        ),
    ],
)
def test_planner_resolves_zero_one_and_multiple_submarkets(
    submarkets, expected_phrase, unexpected_phrase
):
    plans = build_plans(submarkets)
    office_opening_rank_two = next(
        plan for plan in plans if plan.signal_key == "office_opening" and plan.query_rank == 2
    )
    assert office_opening_rank_two.query_text == expected_phrase
    assert unexpected_phrase not in office_opening_rank_two.query_text


def test_planner_builds_exactly_26_workspace_owned_unique_plans():
    workspace_id = uuid.uuid4()
    plans = build_discovery_search_plans(
        job_id=uuid.uuid4(),
        workspace_id=workspace_id,
        profile=BrokerSearchContext(
            country="South Africa",
            market="Cape Town",
            submarkets=("Century City", "Bellville"),
        ),
    )
    assert len(plans) == 26
    assert len({(plan.signal_key, plan.query_rank) for plan in plans}) == 26
    assert {plan.query_rank for plan in plans} == {1, 2}
    assert {plan.workspace_id for plan in plans} == {workspace_id}
    assert not hasattr(plans[0], "broker_id")
