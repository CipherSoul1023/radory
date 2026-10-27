"""Experimental semantic extraction contract; no persistence or search dispatch."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.search.evidence import PreparedDocument
from app.search.signal_library import SIGNAL_LIBRARY

MAX_INPUT_CHARACTERS = 60_000
MAX_OUTPUT_CHARACTERS = 100_000
Text = Annotated[str, Field(min_length=1, max_length=1200, pattern=r"\S")]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class InputBlock(ContractModel):
    block_id: Annotated[str, Field(min_length=1, max_length=64)]
    kind: Literal["title", "snippet", "raw_content"]
    text: Annotated[str, Field(min_length=1, max_length=MAX_INPUT_CHARACTERS, pattern=r"\S")]


class SemanticExtractionInput(ContractModel):
    schema_version: Literal["1"]
    content_basis: Literal["raw_content", "snippet"]
    coverage: Literal["all_selected_text", "partial"]
    provider_published_at: datetime | None
    blocks: Annotated[list[InputBlock], Field(min_length=1, max_length=256)]

    @model_validator(mode="after")
    def validate_blocks(self) -> Self:
        if len({block.block_id for block in self.blocks}) != len(self.blocks):
            raise ValueError("Evidence block IDs must be unique")
        if not any(block.kind == self.content_basis for block in self.blocks):
            raise ValueError("Evidence must contain the declared content basis")
        if any(block.kind not in {"title", self.content_basis} for block in self.blocks):
            raise ValueError("Evidence block kind conflicts with content basis")
        if sum(len(block.text) for block in self.blocks) > MAX_INPUT_CHARACTERS:
            raise ValueError("Evidence exceeds the evaluation input limit; no text was truncated")
        return self

    @classmethod
    def from_document(cls, document: PreparedDocument) -> SemanticExtractionInput:
        payload = document.semantic_payload()
        payload["provider_published_at"] = document.provider_published_at
        return cls.model_validate(payload)


class EvidenceQuote(ContractModel):
    block_id: Annotated[str, Field(min_length=1, max_length=64)]
    quote: Annotated[str, Field(min_length=1, max_length=2000, pattern=r"\S")]


Quotes = Annotated[list[EvidenceQuote], Field(min_length=1, max_length=8)]


class SupportedText(ContractModel):
    value: Text
    evidence: Quotes


class RelatedCompany(ContractModel):
    company: SupportedText
    role: SupportedText


class SupportedSignal(ContractModel):
    signal_key: Annotated[
        str,
        Field(max_length=64, json_schema_extra={"enum": list(SIGNAL_LIBRARY)}),
    ]
    evidence: Quotes

    @field_validator("signal_key")
    @classmethod
    def existing_signal(cls, value: str) -> str:
        if value not in SIGNAL_LIBRARY:
            raise ValueError("Signal key is not in the Radory catalogue")
        return value


class EventStage(ContractModel):
    value: Literal["planned", "underway", "completed", "cancelled", "unclear"]
    evidence: Annotated[list[EvidenceQuote], Field(max_length=8)]

    @model_validator(mode="after")
    def require_stage_evidence(self) -> Self:
        if self.value != "unclear" and not self.evidence:
            raise ValueError("A stated event stage requires evidence")
        return self


class EventLocation(ContractModel):
    country: SupportedText | None
    market: SupportedText | None
    submarket: SupportedText | None
    role: Literal["event_location", "origin", "destination", "unclear"]

    @model_validator(mode="after")
    def require_location(self) -> Self:
        if self.country is None and self.market is None and self.submarket is None:
            raise ValueError("Omit wholly unknown locations instead of adding empty records")
        return self


class EventTiming(ContractModel):
    expression: Text
    precision: Literal["day", "month", "quarter", "year", "range", "relative", "unclear"]
    evidence: Quotes


MissingFact = Literal[
    "company_identity",
    "event_location",
    "event_timing",
    "event_stage",
    "local_headcount",
    "workplace_plans",
]


class ExtractedEvent(ContractModel):
    subject_company: SupportedText
    related_companies: Annotated[list[RelatedCompany], Field(max_length=20)]
    summary: SupportedText
    signals: Annotated[list[SupportedSignal], Field(min_length=1, max_length=17)]
    stage: EventStage
    locations: Annotated[list[EventLocation], Field(max_length=20)]
    timing: Annotated[list[EventTiming], Field(max_length=20)]
    missing_facts: Annotated[list[MissingFact], Field(max_length=6)]

    @model_validator(mode="after")
    def unique_classifications(self) -> Self:
        keys = [signal.signal_key for signal in self.signals]
        if len(set(keys)) != len(keys):
            raise ValueError("An event must not repeat the same signal")
        if len(set(self.missing_facts)) != len(self.missing_facts):
            raise ValueError("Missing facts must be unique")
        return self


class SemanticExtractionOutput(ContractModel):
    outcome: Literal["assessed", "insufficient_evidence"]
    events: Annotated[list[ExtractedEvent], Field(max_length=20)]

    @model_validator(mode="after")
    def consistent_outcome(self) -> Self:
        if self.outcome == "insufficient_evidence" and self.events:
            raise ValueError("Insufficient evidence cannot contain accepted event candidates")
        return self


class ExtractionValidationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        # Do not echo model output, request headers, or document content in errors.
        super().__init__(code)


def validate_semantic_output(
    response_text: str, evidence: SemanticExtractionInput
) -> SemanticExtractionOutput:
    if len(response_text) > MAX_OUTPUT_CHARACTERS:
        raise ExtractionValidationError("output_too_large")
    try:
        output = SemanticExtractionOutput.model_validate_json(response_text)
    except ValidationError:
        raise ExtractionValidationError("invalid_output_schema") from None

    blocks = {block.block_id: block.text for block in evidence.blocks}

    def check_quotes(quotes: list[EvidenceQuote]) -> None:
        for quote in quotes:
            if quote.block_id not in blocks or quote.quote not in blocks[quote.block_id]:
                raise ExtractionValidationError("unmatched_evidence_quote")

    def check_text(fact: SupportedText, *, verbatim: bool = False) -> None:
        check_quotes(fact.evidence)
        if verbatim and not any(fact.value in quote.quote for quote in fact.evidence):
            raise ExtractionValidationError("unsupported_literal_fact")

    for event in output.events:
        check_text(event.subject_company, verbatim=True)
        check_text(event.summary)
        check_quotes(event.stage.evidence)
        for related in event.related_companies:
            check_text(related.company, verbatim=True)
            check_text(related.role)
        for signal in event.signals:
            check_quotes(signal.evidence)
        for location in event.locations:
            for fact in (location.country, location.market, location.submarket):
                if fact is not None:
                    check_text(fact, verbatim=True)
        for timing in event.timing:
            check_quotes(timing.evidence)
            if not any(timing.expression in quote.quote for quote in timing.evidence):
                raise ExtractionValidationError("unsupported_literal_fact")
    return output
