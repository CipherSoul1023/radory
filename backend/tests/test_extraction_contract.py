import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.search.extraction_contract import (
    MAX_INPUT_CHARACTERS,
    ExtractionValidationError,
    SemanticExtractionInput,
    validate_semantic_output,
)
from app.search.signal_library import SIGNAL_LIBRARY

ARTICLE = "Acme Technologies plans to launch in South Africa in 2027. Its city is unknown."


def fact(value, quote=ARTICLE):
    return {"value": value, "evidence": [{"block_id": "body", "quote": quote}]}


@pytest.fixture
def semantic_input():
    return SemanticExtractionInput.model_validate(
        {
            "schema_version": "1",
            "content_basis": "raw_content",
            "coverage": "all_selected_text",
            "provider_published_at": None,
            "blocks": [{"block_id": "body", "kind": "raw_content", "text": ARTICLE}],
        }
    )


@pytest.fixture
def candidate_output():
    return {
        "outcome": "assessed",
        "events": [
            {
                "subject_company": fact("Acme Technologies"),
                "related_companies": [],
                "summary": fact("Acme plans a South African launch."),
                "signals": [{"signal_key": "market_entry", "evidence": fact("unused")["evidence"]}],
                "stage": {"value": "planned", "evidence": fact("unused")["evidence"]},
                "locations": [
                    {
                        "country": fact("South Africa"),
                        "market": None,
                        "submarket": None,
                        "role": "destination",
                    }
                ],
                "timing": [
                    {
                        "expression": "2027",
                        "precision": "year",
                        "evidence": fact("unused")["evidence"],
                    }
                ],
                "missing_facts": ["event_location", "workplace_plans"],
            }
        ],
    }


def test_supported_candidate_preserves_unknowns(semantic_input, candidate_output):
    output = validate_semantic_output(json.dumps(candidate_output), semantic_input)
    event = output.events[0]
    assert event.subject_company.value == "Acme Technologies"
    assert event.locations[0].market is None
    assert event.timing[0].expression == "2027"


@pytest.mark.parametrize("signal_key", list(SIGNAL_LIBRARY))
def test_contract_accepts_all_catalogue_keys(semantic_input, candidate_output, signal_key):
    # This checks the catalogue contract, not whether this article supports each signal.
    candidate_output["events"][0]["signals"][0]["signal_key"] = signal_key
    assert validate_semantic_output(json.dumps(candidate_output), semantic_input)


def test_multiple_signals_and_companies_are_supported(semantic_input, candidate_output):
    article = ARTICLE + " Beta Ltd completed its office relocation."
    semantic_input.blocks[0].text = article
    second = deepcopy(candidate_output["events"][0])
    second["subject_company"] = fact("Beta Ltd", article)
    second["signals"] = [
        {"signal_key": key, "evidence": fact("unused", article)["evidence"]}
        for key in ("office_relocation", "completed_move")
    ]
    second["summary"] = fact("Beta completed its relocation.", article)
    second["stage"] = {"value": "completed", "evidence": fact("unused", article)["evidence"]}
    second["locations"] = []
    second["timing"] = []
    candidate_output["events"].append(second)
    output = validate_semantic_output(json.dumps(candidate_output), semantic_input)
    assert len(output.events) == 2
    assert len(output.events[1].signals) == 2


@pytest.mark.parametrize("outcome", ["assessed", "insufficient_evidence"])
def test_empty_outcomes_are_successful_and_distinct(semantic_input, outcome):
    output = validate_semantic_output(
        json.dumps({"outcome": outcome, "events": []}), semantic_input
    )
    assert output.outcome == outcome and output.events == []


@pytest.mark.parametrize(
    "fault",
    [
        "unknown_signal",
        "missing_field",
        "extra_field",
        "coercion",
        "duplicate_signal",
        "missing_stage_evidence",
        "insufficient_with_events",
        "missing_fact_evidence",
    ],
)
def test_malformed_candidates_are_failures(semantic_input, candidate_output, fault):
    event = candidate_output["events"][0]
    if fault == "unknown_signal":
        event["signals"][0]["signal_key"] = "executive_hire"
    elif fault == "missing_field":
        del event["locations"]
    elif fault == "extra_field":
        event["workspace_id"] = "model-must-not-choose-tenant"
    elif fault == "coercion":
        event["subject_company"]["value"] = 123
    elif fault == "duplicate_signal":
        event["signals"].append(deepcopy(event["signals"][0]))
    elif fault == "missing_stage_evidence":
        event["stage"]["evidence"] = []
    elif fault == "missing_fact_evidence":
        event["locations"][0]["country"]["evidence"] = []
    else:
        candidate_output["outcome"] = "insufficient_evidence"
    with pytest.raises(ExtractionValidationError, match="invalid_output_schema"):
        validate_semantic_output(json.dumps(candidate_output), semantic_input)


@pytest.mark.parametrize("fault", ["quote", "block", "geography", "date", "company"])
def test_unsupported_evidence_is_rejected(semantic_input, candidate_output, fault):
    event = candidate_output["events"][0]
    if fault == "quote":
        event["signals"][0]["evidence"][0]["quote"] = "An invented quotation"
    elif fault == "block":
        event["signals"][0]["evidence"][0]["block_id"] = "another-document"
    elif fault == "geography":
        event["locations"][0]["market"] = fact("Pretoria")
    elif fault == "date":
        event["timing"][0]["expression"] = "2027-01-01"
    else:
        event["subject_company"]["value"] = "Different Company"
    with pytest.raises(ExtractionValidationError):
        validate_semantic_output(json.dumps(candidate_output), semantic_input)


def test_invalid_json_is_not_reinterpreted_as_zero_signals(semantic_input):
    with pytest.raises(ExtractionValidationError, match="invalid_output_schema"):
        validate_semantic_output("not JSON: private response text", semantic_input)


def test_large_and_duplicate_blocks_fail_without_silent_truncation(semantic_input):
    payload = semantic_input.model_dump()
    payload["blocks"][0]["text"] = "x" * (MAX_INPUT_CHARACTERS + 1)
    with pytest.raises(ValidationError):
        SemanticExtractionInput.model_validate(payload)
    payload = semantic_input.model_dump()
    payload["blocks"].append(deepcopy(payload["blocks"][0]))
    with pytest.raises(ValidationError, match="unique"):
        SemanticExtractionInput.model_validate(payload)
