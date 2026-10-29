"""Typed, non-persistent synthesis of discovery and investigation observations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.core.config import Settings, get_settings
from app.integrations.nebius.client import NebiusClient, NebiusNotConfigured
from app.search.signal_library import SIGNAL_LIBRARY

SYNTHESIS_VERSION = "1"
OpportunityStage = Literal[
    "potential_future",
    "active_evaluation",
    "committed",
    "fulfilled",
    "weak_speculative",
    "unknown",
    "cancelled",
]


class SynthesisModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SynthesisSource(SynthesisModel):
    source_id: str = Field(min_length=1, max_length=128)
    origin: Literal["discovery", "investigation"]
    title: str = Field(min_length=1, max_length=2000)
    url: str = Field(min_length=1, max_length=8000)
    published_at: datetime | None = None
    supporting_passages: Annotated[tuple[str, ...], Field(max_length=20)] = ()


class SynthesisObservation(SynthesisModel):
    observation_id: UUID
    origin: Literal["discovery", "investigation"]
    signal_key: str
    subject_company: str = Field(min_length=1, max_length=1200)
    summary: str = Field(min_length=1, max_length=4000)
    stage: Literal["planned", "underway", "completed", "cancelled", "unclear"]
    locations: Annotated[tuple[dict, ...], Field(max_length=20)] = ()
    timing: Annotated[tuple[dict, ...], Field(max_length=20)] = ()
    missing_facts: Annotated[tuple[str, ...], Field(max_length=20)] = ()
    source_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=50)]

    @field_validator("signal_key")
    @classmethod
    def known_signal(cls, value: str) -> str:
        if value not in SIGNAL_LIBRARY:
            raise ValueError("Observation signal is not in the Radory catalogue")
        return value


class SynthesisCase(SynthesisModel):
    company_name: str = Field(min_length=1, max_length=1200)
    observations: Annotated[tuple[SynthesisObservation, ...], Field(min_length=1, max_length=100)]
    sources: Annotated[tuple[SynthesisSource, ...], Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def validate_provenance(self) -> Self:
        observation_ids = [item.observation_id for item in self.observations]
        source_ids = [item.source_id for item in self.sources]
        if len(observation_ids) != len(set(observation_ids)):
            raise ValueError("Synthesis observations must be unique")
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Synthesis sources must be unique")
        known_sources = set(source_ids)
        for observation in self.observations:
            if observation.subject_company != self.company_name:
                raise ValueError("All observations must belong to the synthesis company")
            if not set(observation.source_ids) <= known_sources:
                raise ValueError("Observation references an unknown synthesis source")
        return self


class SupportedNarrative(SynthesisModel):
    text: str = Field(min_length=1, max_length=4000)
    observation_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]


class SupportedOpportunityStage(SynthesisModel):
    value: OpportunityStage
    observation_ids: Annotated[tuple[UUID, ...], Field(max_length=20)] = ()

    @model_validator(mode="after")
    def known_stage_can_be_uncited(self) -> Self:
        if self.value != "unknown" and not self.observation_ids:
            raise ValueError("A known opportunity stage requires observations")
        return self


class ReportSignal(SynthesisModel):
    signal_key: str
    observation_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]

    @field_validator("signal_key")
    @classmethod
    def known_signal(cls, value: str) -> str:
        if value not in SIGNAL_LIBRARY:
            raise ValueError("Report signal is not in the Radory catalogue")
        return value


class ReportLocation(SynthesisModel):
    country: str | None = Field(default=None, max_length=100)
    market: str | None = Field(default=None, max_length=120)
    submarket: str | None = Field(default=None, max_length=120)
    observation_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]

    @model_validator(mode="after")
    def has_location(self) -> Self:
        if self.country is None and self.market is None and self.submarket is None:
            raise ValueError("Omit a report location when all fields are unknown")
        return self


class ReportTiming(SynthesisModel):
    expression: str = Field(min_length=1, max_length=1200)
    observation_ids: Annotated[tuple[UUID, ...], Field(min_length=1, max_length=20)]


class RadarOpportunityReport(SynthesisModel):
    company_name: str = Field(min_length=1, max_length=1200)
    headline: SupportedNarrative
    summary: SupportedNarrative
    opportunity_stage: SupportedOpportunityStage
    signals: Annotated[tuple[ReportSignal, ...], Field(min_length=1, max_length=17)]
    why_it_matters: SupportedNarrative
    key_findings: Annotated[tuple[SupportedNarrative, ...], Field(min_length=1, max_length=10)]
    locations: Annotated[tuple[ReportLocation, ...], Field(max_length=10)] = ()
    timing: Annotated[tuple[ReportTiming, ...], Field(max_length=10)] = ()
    open_questions: Annotated[tuple[str, ...], Field(max_length=10)] = ()
    supporting_source_ids: Annotated[tuple[str, ...], Field(min_length=1, max_length=30)]

    @model_validator(mode="after")
    def unique_values(self) -> Self:
        signal_keys = [item.signal_key for item in self.signals]
        if len(signal_keys) != len(set(signal_keys)):
            raise ValueError("Report signals must be unique")
        if len(self.supporting_source_ids) != len(set(self.supporting_source_ids)):
            raise ValueError("Report sources must be unique")
        if len(self.open_questions) != len(set(self.open_questions)):
            raise ValueError("Open questions must be unique")
        return self


class SynthesisValidationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class SynthesisNotConfigured(RuntimeError):
    pass


def _literal_values(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"value", "expression"} and isinstance(nested, str):
                found.add(nested)
            found.update(_literal_values(nested))
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found.update(_literal_values(nested))
    return found


def validate_synthesis_report(
    report: RadarOpportunityReport,
    case: SynthesisCase,
) -> RadarOpportunityReport:
    if report.company_name != case.company_name:
        raise SynthesisValidationError("company_mismatch")

    observations = {item.observation_id: item for item in case.observations}
    sources = {item.source_id: item for item in case.sources}

    def check_observations(ids: tuple[UUID, ...]) -> None:
        if not set(ids) <= observations.keys():
            raise SynthesisValidationError("unknown_observation_reference")

    narratives = (report.headline, report.summary, report.why_it_matters, *report.key_findings)
    for narrative in narratives:
        check_observations(narrative.observation_ids)
    check_observations(report.opportunity_stage.observation_ids)

    for signal in report.signals:
        check_observations(signal.observation_ids)
        if any(
            observations[item].signal_key != signal.signal_key for item in signal.observation_ids
        ):
            raise SynthesisValidationError("unsupported_signal_reference")

    supported_locations = _literal_values(
        [observation.locations for observation in case.observations]
    )
    supported_timing = _literal_values([observation.timing for observation in case.observations])
    for location in report.locations:
        check_observations(location.observation_ids)
        for value in (location.country, location.market, location.submarket):
            if value is not None and value not in supported_locations:
                raise SynthesisValidationError("unsupported_location")
    for timing in report.timing:
        check_observations(timing.observation_ids)
        if timing.expression not in supported_timing:
            raise SynthesisValidationError("unsupported_timing")
    if not set(report.supporting_source_ids) <= sources.keys():
        raise SynthesisValidationError("unknown_source_reference")
    return report


SYSTEM_INSTRUCTIONS = """You synthesize one concise Radory tenant-representation report.
The input contains validated discovery and investigation observations with source provenance.
Return only JSON matching the supplied schema. Combine both origins into one coherent report.
Do not treat investigation as more authoritative merely because it happened later.
Resolve duplicate findings and explicitly reflect contradictions or uncertainty in the summary.
Use only supplied signal keys, observation IDs, source IDs, locations and timing expressions.
Do not invent companies, properties, leases, mandates, locations, dates, headcount or stages.
An executed lease or completed move closes that matching premises search, while an explicitly
different phase or disposal may remain separate. Keep unknown facts unknown.
Write for a commercial tenant-representation broker: concise, factual and actionable.
Do not output a confidence percentage. Open questions must be genuine evidence gaps.
Every headline, summary, stage, signal, finding, location and timing claim must cite observations.
"""


class CompletionClient(Protocol):
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> dict: ...


@dataclass(frozen=True)
class SynthesisResult:
    status: Literal["succeeded", "failed"]
    report: RadarOpportunityReport | None
    error_code: str | None
    model: str
    provider_request_id: str | None = None
    usage: dict[str, int] | None = None


class SemanticSynthesizer:
    def __init__(self, client: CompletionClient, *, model: str, max_output_tokens: int = 4096):
        if not model.strip():
            raise ValueError("An explicit model is required")
        if not 1 <= max_output_tokens <= 8192:
            raise ValueError("Output token limit must be between 1 and 8192")
        self.client = client
        self.model = model
        self.max_output_tokens = max_output_tokens

    async def synthesize(self, case: SynthesisCase) -> SynthesisResult:
        messages = [
            {
                "role": "system",
                "content": SYSTEM_INSTRUCTIONS
                + "\nOutput schema:\n"
                + json.dumps(RadarOpportunityReport.model_json_schema()),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "version": SYNTHESIS_VERSION,
                        "case": case.model_dump(mode="json"),
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            response = await self.client.chat_completion(
                messages,
                model=self.model,
                max_tokens=self.max_output_tokens,
            )
        except NebiusNotConfigured:
            return self._failure("model_not_configured")
        except httpx.HTTPStatusError as exc:
            return self._failure(f"provider_http_{exc.response.status_code}")
        except httpx.RequestError:
            return self._failure("provider_transport_error")
        except ValueError:
            return self._failure("invalid_provider_response")

        try:
            choices = response["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                return self._failure("invalid_provider_response")
            choice = choices[0]
            if choice.get("finish_reason") != "stop":
                return self._failure("incomplete_model_response")
            report = RadarOpportunityReport.model_validate_json(choice["message"]["content"])
            validate_synthesis_report(report, case)
        except (KeyError, TypeError, ValidationError):
            return self._failure("invalid_synthesis_output")
        except SynthesisValidationError as exc:
            return self._failure(exc.code)

        usage = response.get("usage")
        safe_usage = {
            key: value
            for key, value in (usage.items() if isinstance(usage, dict) else [])
            if key in {"prompt_tokens", "completion_tokens", "total_tokens"}
            and type(value) is int
            and value >= 0
        }
        return SynthesisResult(
            status="succeeded",
            report=report,
            error_code=None,
            model=self.model,
            provider_request_id=response.get("id") if isinstance(response.get("id"), str) else None,
            usage=safe_usage or None,
        )

    def _failure(self, code: str) -> SynthesisResult:
        return SynthesisResult(
            status="failed",
            report=None,
            error_code=code,
            model=self.model,
        )


async def synthesize_opportunity(
    case: SynthesisCase,
    *,
    client: CompletionClient | None = None,
    settings: Settings | None = None,
) -> SynthesisResult:
    config = settings or get_settings()
    if not config.nemotron_ultra_model:
        raise SynthesisNotConfigured("NEMOTRON_ULTRA_MODEL is required")
    synthesizer = SemanticSynthesizer(
        client or NebiusClient(),
        model=config.nemotron_ultra_model,
        max_output_tokens=config.nemotron_synthesis_max_tokens,
    )
    return await synthesizer.synthesize(case)
