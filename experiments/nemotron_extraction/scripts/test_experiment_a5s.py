"""Offline checks for A5-S's finer decomposition experiment."""

import hashlib

from app.search.extraction_contract import SemanticExtractionInput
from app.search.extractor import extraction_messages, extraction_specification
from run_experiment_a3 import A3NebiusClient
from run_experiment_a4e import messages_with_addendum
from run_experiment_a5s import build_parts, load_configuration, preserved_output


def test_a5s_preserves_failed_parent_chunk_once():
    config, _, a5d, _ = load_configuration()
    _, _, parent_chunks, parts = build_parts(config, a5d)
    parent = parent_chunks[0].document.blocks[-1].text
    expected = "\n\n".join(
        paragraph.strip() for paragraph in parent.split("\n\n") if paragraph.strip()
    )
    actual = "\n\n".join(part.document.blocks[-1].text for part in parts)
    assert actual == expected
    assert [len(part.document.blocks[-1].text) for part in parts] == [1117, 1011, 220]
    assert [
        hashlib.sha256(part.document.blocks[-1].text.encode()).hexdigest()
        for part in parts
    ] == [row["body_sha256"] for row in config["decomposition"]["expected_parts"]]


def test_a5s_preserves_only_the_validated_a5r_event():
    config, _, _, _ = load_configuration()
    output = preserved_output(config)
    assert len(output.events) == 1
    event = output.events[0]
    assert event.subject_company.value == "Aker Horizons AS"
    assert {signal.signal_key for signal in event.signals} == {
        "ma_consolidation",
        "market_entry",
    }


def test_a5s_request_keeps_default_reasoning_and_a5r_prompt(tmp_path):
    config, _, a5d, a4e = load_configuration()
    _, _, _, parts = build_parts(config, a5d)
    semantic = SemanticExtractionInput.from_document(parts[0].document)
    messages = messages_with_addendum(
        extraction_messages(semantic, extraction_specification()), a4e
    )
    payload = A3NebiusClient(
        expected_messages=messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "error.json",
    ).payload(messages, config["model"], config["max_tokens"])
    assert "chat_template_kwargs" not in payload
    assert "reasoning_budget" not in payload
    assert "reasoning_effort" not in payload
    assert payload["max_tokens"] == 4096
    assert "Grounding addendum for this experiment" in payload["messages"][0]["content"]


def test_a5s_acceptance_requires_no_duplicates_or_missing_events():
    config, _, _, _ = load_configuration()
    target = config["acceptance"]
    assert target["new_part_calls"] == target["backend_valid_new_parts"] == 3
    assert target["expected_events"] == target["matched_events"] == 3
    assert target["extra_events"] == 0
    assert target["signal_true_positives"] == 2
    assert target["signal_extra"] == target["signal_missing"] == 0
