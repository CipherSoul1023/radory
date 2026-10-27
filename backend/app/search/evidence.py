"""Deterministic, read-only preparation of stored discovery evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from app.models.search_result import SearchResult

PREPARATION_VERSION = "1"


class EvidenceUnavailable(ValueError):
    pass


class EvidenceWorkspaceMismatch(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceBlock:
    block_id: str
    kind: Literal["title", "snippet", "raw_content"]
    text: str


@dataclass(frozen=True)
class PreparedDocument:
    content_basis: Literal["raw_content", "snippet"]
    provider_published_at: datetime | None
    blocks: tuple[EvidenceBlock, ...]

    def semantic_payload(self) -> dict:
        return {
            "schema_version": "1",
            "content_basis": self.content_basis,
            # This describes supplied text, not completeness of the original webpage.
            "coverage": "all_selected_text",
            "provider_published_at": (
                self.provider_published_at.isoformat() if self.provider_published_at else None
            ),
            "blocks": [
                {"block_id": block.block_id, "kind": block.kind, "text": block.text}
                for block in self.blocks
            ],
        }


@dataclass(frozen=True)
class EvidenceSource:
    search_result_id: UUID
    search_query_id: UUID
    search_job_id: UUID
    workspace_id: UUID
    discovery_signal: str
    query_text: str
    title: str
    url: str
    normalized_url: str
    source_hostname: str
    result_rank: int
    provider_score: float | None
    provider_published_at: datetime | None
    provider_result_id: str | None
    provider_request_id: str | None
    provider_response_time_seconds: float | None
    provider_usage: dict | None
    preferred_domains: tuple[str, ...]
    include_domains_mode: str
    matched_preferred_domains: tuple[str, ...]
    snippet: str | None
    raw_payload: dict
    retrieved_at: datetime


@dataclass(frozen=True)
class PreparedEvidence:
    workspace_id: UUID
    document: PreparedDocument
    content_hash: str
    input_fingerprint: str
    sources: tuple[EvidenceSource, ...]


def fingerprint(value: dict) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    # Preserve wording, paragraph boundaries, punctuation, and within-line spacing for quotes.
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


def source_url_parts(url: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
            raise ValueError
        if parsed.username is not None or parsed.password is not None:
            raise ValueError
        hostname = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        host = f"[{hostname}]" if ":" in hostname else hostname
        if parsed.port is not None:
            host = f"{host}:{parsed.port}"
        # Keep paths and query parameters: they can select different articles.
        normalized = urlunsplit((parsed.scheme.lower(), host, parsed.path, parsed.query, ""))
        return hostname, normalized
    except (ValueError, UnicodeError):
        raise EvidenceUnavailable(
            "Evidence URL must be an HTTP(S) URL without credentials"
        ) from None


def prepare_search_result(result: SearchResult, *, workspace_id: UUID) -> PreparedEvidence:
    query = result.search_query
    job = query.job
    if job.workspace_id != workspace_id:
        raise EvidenceWorkspaceMismatch("Evidence does not belong to the requested workspace")
    if result.id is None or result.created_at is None:
        raise EvidenceUnavailable("Evidence must be a persisted search result")

    raw_content = result.raw_payload.get("raw_content")
    if isinstance(raw_content, str) and raw_content.strip():
        body = normalize_text(raw_content)
        basis = "raw_content"
    elif isinstance(result.content, str) and result.content.strip():
        body = normalize_text(result.content)
        basis = "snippet"
    else:
        raise EvidenceUnavailable("No usable raw content or snippet")

    hostname, normalized_url = source_url_parts(result.url)
    preferred_domains = tuple(query.preferred_domains)
    matches = tuple(
        domain
        for domain in preferred_domains
        if hostname == domain.lower().rstrip(".")
        or hostname.endswith("." + domain.lower().rstrip("."))
    )
    blocks = []
    title = normalize_text(result.title)
    if title:
        blocks.append(EvidenceBlock(block_id="title", kind="title", text=title))
    blocks.append(EvidenceBlock(block_id="body", kind=basis, text=body))
    document = PreparedDocument(
        content_basis=basis,
        provider_published_at=result.published_at,
        blocks=tuple(blocks),
    )
    source = EvidenceSource(
        search_result_id=result.id,
        search_query_id=query.id,
        search_job_id=job.id,
        workspace_id=job.workspace_id,
        discovery_signal=query.signal_key,
        query_text=query.query_text,
        title=result.title,
        url=result.url,
        normalized_url=normalized_url,
        source_hostname=hostname,
        result_rank=result.result_rank,
        provider_score=result.provider_score,
        provider_published_at=result.published_at,
        provider_result_id=result.provider_result_id,
        provider_request_id=query.provider_request_id,
        provider_response_time_seconds=query.provider_response_time_seconds,
        provider_usage=deepcopy(query.provider_usage),
        preferred_domains=preferred_domains,
        include_domains_mode=query.include_domains_mode,
        matched_preferred_domains=matches,
        snippet=result.content,
        raw_payload=deepcopy(result.raw_payload),
        retrieved_at=result.created_at,
    )
    return PreparedEvidence(
        workspace_id=job.workspace_id,
        document=document,
        content_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        input_fingerprint=fingerprint(
            {"preparation_version": PREPARATION_VERSION, "input": document.semantic_payload()}
        ),
        sources=(source,),
    )


def group_identical_evidence(items: Iterable[PreparedEvidence]) -> list[PreparedEvidence]:
    """Group exact semantic inputs per workspace; retain every discovery occurrence."""
    groups: dict[tuple[UUID, str], PreparedEvidence] = {}
    for item in items:
        key = (item.workspace_id, item.input_fingerprint)
        existing = groups.get(key)
        if existing is None:
            groups[key] = item
            continue
        sources = {source.search_result_id: source for source in existing.sources}
        sources.update({source.search_result_id: source for source in item.sources})
        groups[key] = replace(existing, sources=tuple(sources.values()))
    return list(groups.values())
