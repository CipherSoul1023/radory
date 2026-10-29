"""Offline checks for A5-D's frozen decomposition experiment."""

import hashlib

from run_experiment_a4e import messages_with_addendum
from run_experiment_a4r2 import ThinkingDisabledNebiusClient
from run_experiment_a5d import build_chunks, load_configuration, split_body

from app.search.extraction_contract import SemanticExtractionInput
from app.search.extractor import extraction_messages, extraction_specification


def test_a5d_frozen_split_preserves_every_nonempty_paragraph_once():
    config, _ = load_configuration()
    _, original, chunks = build_chunks(config)
    body = next(block.text for block in original.document.blocks if block.kind == "raw_content")
    expected = "\n\n".join(
        paragraph.strip() for paragraph in body.split("\n\n") if paragraph.strip()
    )
    actual = "\n\n".join(chunk.document.blocks[-1].text for chunk in chunks)
    assert actual == expected
    assert len(chunks) == 2
    assert [len(chunk.document.blocks[-1].text) for chunk in chunks] == [2352, 2141]
    assert [
        hashlib.sha256(chunk.document.blocks[-1].text.encode()).hexdigest() for chunk in chunks
    ] == [row["body_sha256"] for row in config["decomposition"]["expected_chunks"]]


def test_split_body_never_truncates_an_oversized_paragraph():
    try:
        split_body("x" * 11, 10)
    except ValueError as exc:
        assert str(exc) == "Evidence cannot be split without truncating a paragraph"
    else:
        raise AssertionError("Oversized paragraph should fail instead of being truncated")


def test_a5d_request_keeps_a4e_prompt_and_provider_controls(tmp_path):
    config, a4e = load_configuration()
    _, _, chunks = build_chunks(config)
    semantic = SemanticExtractionInput.from_document(chunks[0].document)
    extractor_messages = extraction_messages(semantic, extraction_specification())
    provider_messages = messages_with_addendum(extractor_messages, a4e)
    client = ThinkingDisabledNebiusClient(
        expected_messages=provider_messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "error.json",
    )
    payload = client.payload(provider_messages, config["model"], config["max_tokens"])
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert payload["max_tokens"] == 4096
    assert payload["response_format"]["type"] == "json_schema"
    assert "Grounding addendum for this experiment" in payload["messages"][0]["content"]


def test_a5d_acceptance_separates_technical_and_semantic_gates():
    config, _ = load_configuration()
    target = config["acceptance"]
    assert target["chunk_calls"] == target["backend_valid_chunks"] == 2
    assert target["aggregate_backend_valid"] is True
    assert target["expected_events"] == target["matched_events"] == 3
    assert target["signal_true_positives"] == 2
    assert target["signal_extra"] == target["signal_missing"] == 0
