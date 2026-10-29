"""Offline checks for B1's compact first-pass experiment."""

import json

import pytest
from compare_experiment_b1 import match_compact_events
from run_experiment_a5d import build_chunks
from run_experiment_b1 import (
    CompactDetectionClient,
    CompactValidationError,
    compact_messages,
    load_configuration,
    validate_compact_output,
)

from app.search.extraction_contract import SemanticExtractionInput


def aker_entry_quote(semantic: SemanticExtractionInput) -> str:
    body = next(block.text for block in semantic.blocks if block.block_id == "body_chunk_002")
    start = body.index("Aker does not have a presence")
    return body[start : body.index(".", start) + 1]


def test_b1_uses_exact_a5r_chunks_and_super():
    config, a5d = load_configuration()
    row, _, chunks = build_chunks(a5d)
    assert row["case_id"] == config["source_case_id"] == "pilot-v1-008"
    assert config["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert [len(chunk.document.blocks[-1].text) for chunk in chunks] == [2352, 2141]


def test_b1_payload_uses_compact_schema_and_default_reasoning(tmp_path):
    config, a5d = load_configuration()
    _, _, chunks = build_chunks(a5d)
    messages = compact_messages(chunks[0].document)
    payload = CompactDetectionClient(
        expected_messages=messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "error.json",
    ).payload(messages, config["model"], config["max_tokens"])
    assert payload["response_format"]["json_schema"]["name"] == (
        "radory_compact_event_detection_v1"
    )
    assert "chat_template_kwargs" not in payload
    assert "reasoning_budget" not in payload
    assert "reasoning_effort" not in payload
    assert payload["max_tokens"] == 4096
    schema_text = json.dumps(payload["response_format"])
    assert "summary" not in schema_text
    assert "locations" not in schema_text
    assert "timing" not in schema_text
    assert "related_companies" not in schema_text


def test_b1_backend_accepts_grounded_minimal_event():
    _, a5d = load_configuration()
    _, _, chunks = build_chunks(a5d)
    semantic = SemanticExtractionInput.from_document(chunks[1].document)
    quote = aker_entry_quote(semantic)
    payload = {
        "outcome": "assessed",
        "events": [
            {
                "subject_company": {
                    "value": "Aker",
                    "evidence": [{"block_id": "body_chunk_002", "quote": quote}],
                },
                "signals": [
                    {
                        "signal_key": "market_entry",
                        "evidence": [{"block_id": "body_chunk_002", "quote": quote}],
                    }
                ],
            }
        ],
    }
    result = validate_compact_output(json.dumps(payload), semantic)
    assert result.events[0].signals[0].signal_key == "market_entry"


def test_b1_backend_rejects_unsupported_company_literal():
    _, a5d = load_configuration()
    _, _, chunks = build_chunks(a5d)
    semantic = SemanticExtractionInput.from_document(chunks[1].document)
    quote = aker_entry_quote(semantic)
    payload = {
        "outcome": "assessed",
        "events": [
            {
                "subject_company": {
                    "value": "Invented Holdings",
                    "evidence": [{"block_id": "body_chunk_002", "quote": quote}],
                },
                "signals": [
                    {
                        "signal_key": "market_entry",
                        "evidence": [{"block_id": "body_chunk_002", "quote": quote}],
                    }
                ],
            }
        ],
    }
    with pytest.raises(CompactValidationError, match="unsupported_literal_fact"):
        validate_compact_output(json.dumps(payload), semantic)


def test_b1_acceptance_requires_all_events_and_no_truncation():
    config, _ = load_configuration()
    target = config["acceptance"]
    assert target["chunk_calls"] == target["backend_valid_chunks"] == 2
    assert target["truncations"] == 0
    assert target["expected_events"] == target["matched_events"] == 3
    assert target["extra_events"] == 0
    assert target["signal_true_positives"] == 2
    assert target["signal_extra"] == target["signal_missing"] == 0


def test_b1_comparison_never_matches_an_unrelated_company():
    expected = [
        {
            "subject_company": "greenstreet 1 (pty) ltd (stanlib fund ii)",
            "signals": ["ma_consolidation"],
            "quotes": [],
        }
    ]
    unrelated = [
        {
            "subject_company": "mainstream renewable power ltd",
            "signals": ["ma_consolidation"],
            "quotes": [],
        }
    ]
    alias = [
        {
            "subject_company": "stanlib fund ii",
            "signals": ["ma_consolidation"],
            "quotes": [],
        }
    ]
    assert match_compact_events(expected, unrelated) == []
    assert match_compact_events(expected, alias) == [(0, 0)]
