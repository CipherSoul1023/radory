from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.integrations.nebius.client import NebiusClient
from app.models import (
    ExtractionSource,
    RadarOpportunity,
    SearchJob,
    SearchQuery,
    SearchResult,
    SignalObservation,
)
from app.search.evidence import (
    PREPARATION_VERSION,
    EvidenceBlock,
    PreparedDocument,
    PreparedEvidence,
    fingerprint,
    normalize_text,
)
from app.search.extractor import ExtractionResult, SemanticExtractor
from app.search.investigation import (
    InvestigationExecution,
    SemanticInvestigationPlanner,
    investigate_observation,
)
from app.search.synthesis import (
    SemanticSynthesizer,
    SynthesisCase,
    SynthesisObservation,
    SynthesisResult,
    SynthesisSource,
)
from app.search.tavily_client import RadarTavilyClient


class OpportunityNotFound(RuntimeError):
    pass


class OpportunityAlreadyRunning(RuntimeError):
    pass


class OpportunityNotConfigured(RuntimeError):
    pass


class OpportunityBuildFailed(RuntimeError):
    def __init__(self, opportunity: RadarOpportunity, code: str):
        self.opportunity = opportunity
        self.code = code
        super().__init__(f"Opportunity build failed: {code}")


class Extractor(Protocol):
    model: str
    max_output_tokens: int

    async def extract(self, evidence: PreparedEvidence) -> ExtractionResult: ...


class Synthesizer(Protocol):
    model: str

    async def synthesize(self, case: SynthesisCase) -> SynthesisResult: ...


@dataclass(frozen=True)
class DiscoveryBundle:
    seed: SignalObservation
    search_job: SearchJob
    observations: tuple[SynthesisObservation, ...]
    sources: tuple[SynthesisSource, ...]


@dataclass(frozen=True)
class InvestigationBundle:
    observations: tuple[SynthesisObservation, ...]
    sources: tuple[SynthesisSource, ...]
    query_payloads: tuple[dict, ...]


def _quote_values(observation: SignalObservation) -> tuple[str, ...]:
    values: list[str] = []
    for collection in (
        observation.subject_company_evidence,
        observation.summary_evidence,
        observation.signal_evidence,
        observation.stage_evidence,
    ):
        for item in collection:
            quote = item.get("quote") if isinstance(item, dict) else None
            if isinstance(quote, str) and quote not in values:
                values.append(quote)
    return tuple(values)


def _discovery_bundle(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    observation_id: uuid.UUID,
) -> DiscoveryBundle:
    seed = db.scalar(
        select(SignalObservation).where(
            SignalObservation.id == observation_id,
            SignalObservation.workspace_id == workspace_id,
        )
    )
    if seed is None:
        raise OpportunityNotFound("Signal observation not found")
    observations = list(
        db.scalars(
            select(SignalObservation)
            .where(
                SignalObservation.workspace_id == workspace_id,
                SignalObservation.extraction_run_id == seed.extraction_run_id,
                SignalObservation.event_index == seed.event_index,
                SignalObservation.subject_company == seed.subject_company,
            )
            .order_by(SignalObservation.signal_key)
        )
    )
    results = list(
        db.scalars(
            select(SearchResult)
            .join(ExtractionSource, ExtractionSource.search_result_id == SearchResult.id)
            .where(ExtractionSource.extraction_run_id == seed.extraction_run_id)
            .order_by(SearchResult.created_at, SearchResult.id)
        )
    )
    if not results:
        raise OpportunityNotFound("Discovery evidence not found")
    job = db.scalar(
        select(SearchJob)
        .join(SearchQuery, SearchQuery.job_id == SearchJob.id)
        .where(SearchQuery.id == results[0].search_query_id, SearchJob.workspace_id == workspace_id)
    )
    if job is None:
        raise OpportunityNotFound("Discovery search job not found")

    passages = tuple(dict.fromkeys(quote for item in observations for quote in _quote_values(item)))
    sources = tuple(
        SynthesisSource(
            source_id=f"discovery:{result.id}",
            origin="discovery",
            title=result.title,
            url=result.url,
            published_at=result.published_at,
            supporting_passages=passages,
        )
        for result in results
    )
    source_ids = tuple(source.source_id for source in sources)
    return DiscoveryBundle(
        seed=seed,
        search_job=job,
        observations=tuple(
            SynthesisObservation(
                observation_id=item.id,
                origin="discovery",
                signal_key=item.signal_key,
                subject_company=item.subject_company,
                summary=item.summary,
                stage=item.stage,
                locations=tuple(item.locations),
                timing=tuple(item.timing),
                missing_facts=tuple(item.missing_facts),
                source_ids=source_ids,
            )
            for item in observations
        ),
        sources=sources,
    )


def _claim_opportunity(db: Session, bundle: DiscoveryBundle) -> tuple[RadarOpportunity, bool]:
    existing = db.scalar(
        select(RadarOpportunity).where(
            RadarOpportunity.workspace_id == bundle.seed.workspace_id,
            RadarOpportunity.seed_extraction_run_id == bundle.seed.extraction_run_id,
            RadarOpportunity.seed_event_index == bundle.seed.event_index,
        )
    )
    if existing is not None and existing.status == "completed":
        return existing, False
    if existing is not None and existing.status == "running":
        raise OpportunityAlreadyRunning("This opportunity is already being built")
    opportunity = existing or RadarOpportunity(
        workspace_id=bundle.seed.workspace_id,
        search_job_id=bundle.search_job.id,
        seed_extraction_run_id=bundle.seed.extraction_run_id,
        seed_event_index=bundle.seed.event_index,
        subject_company=bundle.seed.subject_company,
        discovery_observation_ids=[str(item.observation_id) for item in bundle.observations],
        investigation_queries=[],
        investigation_observations=[],
    )
    opportunity.status = "running"
    opportunity.investigation_decision = None
    opportunity.investigation_queries = []
    opportunity.investigation_observations = []
    opportunity.synthesis_model = None
    opportunity.synthesis_provider_request_id = None
    opportunity.synthesis_usage = None
    opportunity.report = None
    opportunity.error_code = None
    opportunity.error_message = None
    db.add(opportunity)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent = db.scalar(
            select(RadarOpportunity).where(
                RadarOpportunity.workspace_id == bundle.seed.workspace_id,
                RadarOpportunity.seed_extraction_run_id == bundle.seed.extraction_run_id,
                RadarOpportunity.seed_event_index == bundle.seed.event_index,
            )
        )
        if concurrent is None:
            raise
        if concurrent.status == "completed":
            return concurrent, False
        raise OpportunityAlreadyRunning("This opportunity is already being built") from None
    db.refresh(opportunity)
    return opportunity, True


def _published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _prepared_result(workspace_id: uuid.UUID, result) -> PreparedEvidence | None:
    raw = result.raw_payload.get("raw_content")
    if isinstance(raw, str) and raw.strip():
        body = normalize_text(raw)
        basis = "raw_content"
    elif result.content.strip():
        body = normalize_text(result.content)
        basis = "snippet"
    else:
        return None
    blocks = []
    title = normalize_text(result.title)
    if title:
        blocks.append(EvidenceBlock(block_id="title", kind="title", text=title))
    blocks.append(EvidenceBlock(block_id="body", kind=basis, text=body))
    document = PreparedDocument(
        content_basis=basis,
        provider_published_at=_published_at(result.published_date),
        blocks=tuple(blocks),
    )
    return PreparedEvidence(
        workspace_id=workspace_id,
        document=document,
        content_hash=hashlib.sha256(body.encode()).hexdigest(),
        input_fingerprint=fingerprint(
            {"preparation_version": PREPARATION_VERSION, "input": document.semantic_payload()}
        ),
        sources=(),
    )


def _company_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _event_passages(event) -> tuple[str, ...]:
    passages: list[str] = []

    def add(quotes) -> None:
        for quote in quotes:
            if quote.quote not in passages:
                passages.append(quote.quote)

    add(event.subject_company.evidence)
    add(event.summary.evidence)
    add(event.stage.evidence)
    for signal in event.signals:
        add(signal.evidence)
    for location in event.locations:
        for fact in (location.country, location.market, location.submarket):
            if fact is not None:
                add(fact.evidence)
    for timing in event.timing:
        add(timing.evidence)
    return tuple(passages)


async def _extract_investigation(
    execution: InvestigationExecution,
    *,
    opportunity: RadarOpportunity,
    workspace_id: uuid.UUID,
    company_name: str,
    extractor: Extractor,
) -> InvestigationBundle:
    observations: list[SynthesisObservation] = []
    sources: dict[str, SynthesisSource] = {}
    query_payloads: list[dict] = []
    extraction_cache: dict[str, ExtractionResult] = {}
    for executed in execution.queries:
        result_payloads = []
        for rank, result in enumerate(executed.results, start=1):
            prepared = _prepared_result(workspace_id, result)
            source_hash = hashlib.sha256(result.url.encode()).hexdigest()[:16]
            source_id = f"investigation:{source_hash}"
            extraction: ExtractionResult | None = None
            if prepared is not None:
                extraction = extraction_cache.get(prepared.input_fingerprint)
                if extraction is None:
                    extraction = await extractor.extract(prepared)
                    extraction_cache[prepared.input_fingerprint] = extraction
            passages: list[str] = []
            if extraction is not None and extraction.output is not None:
                for event_index, event in enumerate(extraction.output.events):
                    if _company_key(event.subject_company.value) != _company_key(company_name):
                        continue
                    passages.extend(_event_passages(event))
                    for signal in event.signals:
                        observation_id = uuid.uuid5(
                            opportunity.id,
                            f"{source_id}:{event_index}:{signal.signal_key}",
                        )
                        observations.append(
                            SynthesisObservation(
                                observation_id=observation_id,
                                origin="investigation",
                                signal_key=signal.signal_key,
                                subject_company=event.subject_company.value,
                                summary=event.summary.value,
                                stage=event.stage.value,
                                locations=tuple(
                                    item.model_dump(mode="json") for item in event.locations
                                ),
                                timing=tuple(item.model_dump(mode="json") for item in event.timing),
                                missing_facts=tuple(event.missing_facts),
                                source_ids=(source_id,),
                            )
                        )
            if source_id not in sources:
                sources[source_id] = SynthesisSource(
                    source_id=source_id,
                    origin="investigation",
                    title=result.title,
                    url=result.url,
                    published_at=_published_at(result.published_date),
                    supporting_passages=tuple(dict.fromkeys(passages)),
                )
            evidence_text = ""
            content_basis = None
            if prepared is not None:
                content_basis = prepared.document.content_basis
                evidence_text = prepared.document.blocks[-1].text
            result_payloads.append(
                {
                    "rank": rank,
                    "source_id": source_id,
                    "title": result.title,
                    "url": result.url,
                    "content": result.content,
                    "published_date": result.published_date,
                    "provider_score": result.score,
                    "content_basis": content_basis,
                    "evidence_text": evidence_text,
                    "extraction_status": extraction.status if extraction else "skipped",
                    "extraction_error_code": extraction.error_code if extraction else None,
                }
            )
        query_payloads.append(
            {
                "edge_id": executed.plan.edge_id,
                "target_signal": executed.plan.target_signal,
                "query_text": executed.plan.query_text,
                "request_id": executed.request_id,
                "results": result_payloads,
            }
        )
    unique_observations = {observation.observation_id: observation for observation in observations}
    return InvestigationBundle(
        observations=tuple(unique_observations.values()),
        sources=tuple(sources.values()),
        query_payloads=tuple(query_payloads),
    )


def _mark_failed(
    db: Session,
    opportunity: RadarOpportunity,
    *,
    code: str,
    message: str,
) -> None:
    opportunity.status = "failed"
    opportunity.report = None
    opportunity.error_code = code[:64]
    opportunity.error_message = message[:1000]
    db.commit()


async def build_radar_opportunity(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    observation_id: uuid.UUID,
    planner: SemanticInvestigationPlanner | None = None,
    tavily: RadarTavilyClient | None = None,
    extractor: Extractor | None = None,
    synthesizer: Synthesizer | None = None,
    settings: Settings | None = None,
) -> tuple[RadarOpportunity, bool]:
    config = settings or get_settings()
    bundle = _discovery_bundle(
        db,
        workspace_id=workspace_id,
        observation_id=observation_id,
    )
    opportunity, created = _claim_opportunity(db, bundle)
    if not created:
        return opportunity, False
    if not config.nemotron_super_model or not config.nemotron_ultra_model:
        _mark_failed(
            db,
            opportunity,
            code="models_not_configured",
            message="Nemotron Super and Ultra models are required",
        )
        raise OpportunityNotConfigured("Nemotron Super and Ultra models are required")

    selected_extractor = extractor or SemanticExtractor(
        NebiusClient(),
        model=config.nemotron_super_model,
        max_output_tokens=config.nemotron_extraction_max_tokens,
    )
    selected_synthesizer = synthesizer or SemanticSynthesizer(
        NebiusClient(),
        model=config.nemotron_ultra_model,
        max_output_tokens=config.nemotron_synthesis_max_tokens,
    )
    try:
        investigation = await investigate_observation(
            db,
            workspace_id=workspace_id,
            observation_id=observation_id,
            planner=planner,
            tavily=tavily,
            settings=config,
        )
        opportunity.investigation_decision = investigation.decision.model_dump(mode="json")
        investigation_bundle = await _extract_investigation(
            investigation,
            opportunity=opportunity,
            workspace_id=workspace_id,
            company_name=bundle.seed.subject_company,
            extractor=selected_extractor,
        )
        case = SynthesisCase(
            company_name=bundle.seed.subject_company,
            observations=bundle.observations + investigation_bundle.observations,
            sources=bundle.sources + investigation_bundle.sources,
        )
        synthesis = await selected_synthesizer.synthesize(case)
        if synthesis.status != "succeeded" or synthesis.report is None:
            raise OpportunityBuildFailed(
                opportunity,
                synthesis.error_code or "synthesis_failed",
            )
    except OpportunityBuildFailed as exc:
        _mark_failed(db, opportunity, code=exc.code, message=str(exc))
        raise
    except Exception as exc:
        code = type(exc).__name__.lower()[:64]
        _mark_failed(db, opportunity, code=code, message="Opportunity pipeline failed")
        raise OpportunityBuildFailed(opportunity, code) from exc

    opportunity.investigation_queries = list(investigation_bundle.query_payloads)
    opportunity.investigation_observations = [
        item.model_dump(mode="json") for item in investigation_bundle.observations
    ]
    opportunity.synthesis_model = synthesis.model
    opportunity.synthesis_provider_request_id = synthesis.provider_request_id
    opportunity.synthesis_usage = synthesis.usage
    opportunity.report = synthesis.report.model_dump(mode="json")
    opportunity.status = "completed"
    opportunity.error_code = None
    opportunity.error_message = None
    db.commit()
    db.refresh(opportunity)
    return opportunity, True


def list_radar_opportunities(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    limit: int = 100,
) -> list[RadarOpportunity]:
    if not 1 <= limit <= 200:
        raise ValueError("Opportunity limit must be between 1 and 200")
    return list(
        db.scalars(
            select(RadarOpportunity)
            .where(
                RadarOpportunity.workspace_id == workspace_id,
                RadarOpportunity.status == "completed",
            )
            .order_by(RadarOpportunity.updated_at.desc())
            .limit(limit)
        )
    )
