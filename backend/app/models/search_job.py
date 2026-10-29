from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, json_type

if TYPE_CHECKING:
    from app.models.onboarding import BrokerageProfile, User, Workspace
    from app.models.search_query import SearchQuery


class SearchJob(TimestampMixin, Base):
    __tablename__ = "search_jobs"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending', 'running', 'completed', 'partial_failed', 'failed')",
            name="ck_search_jobs_status",
        ),
        CheckConstraint(
            "pipeline_status in ('pending', 'running', 'completed', 'partial_failed', 'failed')",
            name="ck_search_jobs_pipeline_status",
        ),
        Index("ix_search_jobs_workspace_created", "workspace_id", "created_at"),
        Index(
            "uq_search_jobs_active_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text(
                "status in ('pending', 'running') or pipeline_status in ('pending', 'running')"
            ),
            sqlite_where=text(
                "status in ('pending', 'running') or pipeline_status in ('pending', 'running')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    initiated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    brokerage_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("brokerage_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    pipeline_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    pipeline_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pipeline_error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pipeline_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pipeline_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    market: Mapped[str] = mapped_column(String(120), nullable=False)
    configured_submarkets: Mapped[list[str]] = mapped_column(
        json_type, default=list, nullable=False
    )
    resolved_submarket: Mapped[str | None] = mapped_column(String(120), nullable=True)
    brokerage_profile_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    search_context_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="search_jobs")
    initiated_by_user: Mapped[User | None] = relationship(back_populates="initiated_search_jobs")
    brokerage_profile: Mapped[BrokerageProfile | None] = relationship(back_populates="search_jobs")
    queries: Mapped[list[SearchQuery]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="SearchQuery.query_rank"
    )
