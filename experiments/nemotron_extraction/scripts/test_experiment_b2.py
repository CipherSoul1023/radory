"""Offline checks for B2's indexed compact first-pass experiment."""

import json

import pytest
from compare_experiment_b2 import companies_match
from run_experiment_a5d import build_chunks
from run_experiment_b2 import (
    PARAGRAPH_BREAK,
    IndexedCompactClient,
    IndexedValidationError,
    combine_indexed_inputs,
    indexed_evidence,
    load_configuration,
    messages,
    validate_output,
)


def indexed_chunks():
    _, a5d = load_configuration()
    _, _, chunks = build_chunks(a5d)
    return chunks, [indexed_evidence(chunk.document, chunk.input_fingerprint) for chunk in chunks]


def passage_containing(evidence, text: str) -> str:
    return next(passage.passage_id for passage in evidence.passages if text in passage.text)


def test_b2_uses_exact_b1_chunks_and_super():
    config, a5d = load_configuration()
    row, _, chunks = build_chunks(a5d)
    assert row["case_id"] == config["source_case_id"] == "pilot-v1-008"
    assert config["model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert [len(chunk.document.blocks[-1].text) for chunk in chunks] == [2352, 2141]


def test_indexed_evidence_preserves_every_nonblank_paragraph_exactly():
    chunks, indexed = indexed_chunks()
    for chunk, evidence in zip(chunks, indexed, strict=True):
        for block in chunk.document.blocks:
            source_without_breaks = PARAGRAPH_BREAK.sub("", block.text)
            indexed_text = "".join(
                passage.text
                for passage in evidence.passages
                if passage.source_block_id == block.block_id
            )
            assert indexed_text == source_without_breaks


def test_combined_evidence_collapses_only_the_identical_repeated_title():
    config, a5d = load_configuration()
    row, original, chunks = build_chunks(a5d)
    indexed = [indexed_evidence(chunk.document, chunk.input_fingerprint) for chunk in chunks]
    combined = combine_indexed_inputs(row, original, indexed)
    ids = [passage.passage_id for passage in combined.passages]
    assert len(ids) == len(set(ids))
    assert len(combined.passages) == sum(len(item.passages) for item in indexed) - 1
    assert config["source_case_id"] == row["case_id"]


def test_b2_payload_uses_passage_ids_and_default_reasoning(tmp_path):
    _, indexed = indexed_chunks()
    provider_messages = messages(indexed[0])
    config, _ = load_configuration()
    payload = IndexedCompactClient(
        expected_messages=provider_messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "error.json",
    ).payload(provider_messages, config["model"], config["max_tokens"])
    assert payload["response_format"]["json_schema"]["name"] == (
        "radory_indexed_compact_event_detection_v1"
    )
    assert "chat_template_kwargs" not in payload
    assert "reasoning_budget" not in payload
    assert "reasoning_effort" not in payload
    assert payload["max_tokens"] == 4096
    schema_text = json.dumps(payload["response_format"])
    assert "evidence_passage_ids" in schema_text
    assert '"quote"' not in schema_text
    assert '"summary"' not in schema_text
    assert '"locations"' not in schema_text


def test_b2_backend_accepts_one_event_with_two_grounded_signals():
    _, indexed = indexed_chunks()
    evidence = indexed[1]
    acquisition = passage_containing(evidence, "Aker Horizons AS")
    entry = passage_containing(evidence, "establish Aker")
    payload = {
        "outcome": "assessed",
        "events": [
            {
                "subject_company": {
                    "value": "Aker Horizons AS",
                    "evidence_passage_ids": [acquisition],
                },
                "signals": [
                    {
                        "signal_key": "ma_consolidation",
                        "evidence_passage_ids": [acquisition],
                    },
                    {
                        "signal_key": "market_entry",
                        "evidence_passage_ids": [entry],
                    },
                ],
            }
        ],
    }
    result = validate_output(json.dumps(payload), evidence)
    assert {signal.signal_key for signal in result.events[0].signals} == {
        "ma_consolidation",
        "market_entry",
    }


def test_b2_backend_rejects_unknown_passage_id():
    _, indexed = indexed_chunks()
    evidence = indexed[1]
    payload = {
        "outcome": "assessed",
        "events": [
            {
                "subject_company": {
                    "value": "Aker Horizons AS",
                    "evidence_passage_ids": ["missing-p999"],
                },
                "signals": [
                    {
                        "signal_key": "market_entry",
                        "evidence_passage_ids": ["missing-p999"],
                    }
                ],
            }
        ],
    }
    with pytest.raises(IndexedValidationError, match="invalid_passage_reference"):
        validate_output(json.dumps(payload), evidence)


def test_b2_backend_rejects_unsupported_company_literal():
    _, indexed = indexed_chunks()
    evidence = indexed[1]
    passage_id = passage_containing(evidence, "Aker Horizons AS")
    payload = {
        "outcome": "assessed",
        "events": [
            {
                "subject_company": {
                    "value": "Invented Holdings",
                    "evidence_passage_ids": [passage_id],
                },
                "signals": [
                    {
                        "signal_key": "market_entry",
                        "evidence_passage_ids": [passage_id],
                    }
                ],
            }
        ],
    }
    with pytest.raises(IndexedValidationError, match="unsupported_literal_fact"):
        validate_output(json.dumps(payload), evidence)


def test_b2_acceptance_requires_complete_grouped_result():
    config, _ = load_configuration()
    target = config["acceptance"]
    assert target["chunk_calls"] == target["backend_valid_chunks"] == 2
    assert target["truncations"] == target["invalid_passage_references"] == 0
    assert target["expected_events"] == target["matched_events"] == 3
    assert target["extra_events"] == 0
    assert target["signal_true_positives"] == 2
    assert target["signal_extra"] == target["signal_missing"] == 0


def test_b2_comparison_tolerates_source_encoding_marks_but_not_another_company():
    gold = "greenstreet 1 (pty) ltd (stanlib fund ii)"
    source_exact = "greenstreet 1 (pty) ltd (a oe stanlib fund ii a)"
    assert companies_match(gold, source_exact)
    assert not companies_match(gold, "mainstream renewable power ltd")
