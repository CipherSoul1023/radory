from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, json_type

if TYPE_CHECKING:
    from app.models.search_job import SearchJob
    from app.models.search_result import SearchResult


class SearchQuery(TimestampMixin, Base):
    __tablename__ = "search_queries"
    __table_args__ = (
        UniqueConstraint(
            "job_id", "signal_key", "query_rank", name="uq_search_queries_job_signal_rank"
        ),
        CheckConstraint("query_rank in (1, 2)", name="ck_search_queries_rank"),
        CheckConstraint("length(query_text) > 0", name="ck_search_queries_query_text"),
        CheckConstraint(
            "include_domains_mode in ('prefer', 'restrict')",
            name="ck_search_queries_domain_mode",
        ),
        CheckConstraint(
            "search_depth in ('basic', 'advanced', 'fast', 'ultra-fast')",
            name="ck_search_queries_depth",
        ),
        CheckConstraint("max_results between 1 and 20", name="ck_search_queries_max_results"),
        CheckConstraint(
            "status in ('pending', 'running', 'succeeded', 'failed')",
            name="ck_search_queries_status",
        ),
        CheckConstraint("attempt_count >= 0", name="ck_search_queries_attempt_count"),
        CheckConstraint(
            "dispatch_attempt_count >= 0", name="ck_search_queries_dispatch_attempt_count"
        ),
        Index("ix_search_queries_dispatch", "status", "next_attempt_at", "last_dispatched_at"),
        Index("ix_search_queries_lease", "status", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_jobs.id", ondelete="CASCADE"), index=True
    )
    signal_key: Mapped[str] = mapped_column(String(64), nullable=False)
    query_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    preferred_domains: Mapped[list[str]] = mapped_column(json_type, default=list, nullable=False)
    include_domains_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    search_depth: Mapped[str] = mapped_column(String(16), default="basic", nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    include_raw_content: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dispatch_attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_response_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    provider_usage: Mapped[dict | None] = mapped_column(json_type, nullable=True)

    job: Mapped[SearchJob] = relationship(back_populates="queries")
    results: Mapped[list[SearchResult]] = relationship(
        back_populates="search_query",
        cascade="all, delete-orphan",
        order_by="SearchResult.result_rank",
    )
