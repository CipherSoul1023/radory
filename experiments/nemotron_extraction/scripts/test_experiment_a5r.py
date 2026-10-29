"""Offline checks for A5-R's frozen reasoning comparison."""

from app.search.extraction_contract import SemanticExtractionInput
from app.search.extractor import extraction_messages, extraction_specification
from run_experiment_a3 import A3NebiusClient
from run_experiment_a4e import messages_with_addendum
from run_experiment_a4r2 import ThinkingDisabledNebiusClient
from run_experiment_a5d import build_chunks
from run_experiment_a5r import load_configuration


def test_a5r_uses_a5d_exact_chunks():
    config, a5d, _ = load_configuration()
    row, _, chunks = build_chunks(a5d)
    assert row["case_id"] == config["source_case_id"] == "pilot-v1-008"
    assert [len(chunk.document.blocks[-1].text) for chunk in chunks] == [2352, 2141]


def test_a5r_payload_differs_only_by_thinking_control(tmp_path):
    config, a5d, a4e = load_configuration()
    _, _, chunks = build_chunks(a5d)
    semantic = SemanticExtractionInput.from_document(chunks[0].document)
    extractor_messages = extraction_messages(semantic, extraction_specification())
    messages = messages_with_addendum(extractor_messages, a4e)
    reasoning_on = A3NebiusClient(
        expected_messages=messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "reasoning-on-error.json",
    ).payload(messages, config["model"], config["max_tokens"])
    reasoning_off = ThinkingDisabledNebiusClient(
        expected_messages=messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "reasoning-off-error.json",
    ).payload(messages, config["model"], config["max_tokens"])
    assert "chat_template_kwargs" not in reasoning_on
    assert reasoning_off.pop("chat_template_kwargs") == {"enable_thinking": False}
    assert reasoning_on == reasoning_off


def test_a5r_does_not_invent_a_reasoning_budget_or_effort(tmp_path):
    config, a5d, a4e = load_configuration()
    _, _, chunks = build_chunks(a5d)
    semantic = SemanticExtractionInput.from_document(chunks[1].document)
    messages = messages_with_addendum(
        extraction_messages(semantic, extraction_specification()), a4e
    )
    payload = A3NebiusClient(
        expected_messages=messages,
        model=config["model"],
        max_tokens=config["max_tokens"],
        error_path=tmp_path / "error.json",
    ).payload(messages, config["model"], config["max_tokens"])
    assert "reasoning_budget" not in payload
    assert "reasoning_effort" not in payload
    assert "enable_thinking" not in payload


def test_a5r_acceptance_requires_technical_and_semantic_success():
    config, _, _ = load_configuration()
    target = config["acceptance"]
    assert target["chunk_calls"] == target["backend_valid_chunks"] == 2
    assert target["aggregate_backend_valid"] is True
    assert target["expected_events"] == target["matched_events"] == 3
    assert target["signal_true_positives"] == 2
    assert target["signal_extra"] == target["signal_missing"] == 0
