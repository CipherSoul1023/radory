from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, json_type, nullable_json_type

if TYPE_CHECKING:
    from app.models.extraction_run import ExtractionRun
    from app.models.onboarding import Workspace
    from app.models.search_job import SearchJob


class RadarOpportunity(TimestampMixin, Base):
    __tablename__ = "radar_opportunities"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "seed_extraction_run_id",
            "seed_event_index",
            name="uq_radar_opportunities_workspace_event",
        ),
        CheckConstraint("seed_event_index >= 0", name="ck_radar_opportunities_event_index"),
        CheckConstraint(
            "status in ('running', 'completed', 'failed')",
            name="ck_radar_opportunities_status",
        ),
        CheckConstraint(
            "(status = 'completed' and report is not null and error_code is null) or "
            "(status = 'failed' and report is null and error_code is not null) or "
            "(status = 'running' and report is null and error_code is null)",
            name="ck_radar_opportunities_result_shape",
        ),
        Index("ix_radar_opportunities_workspace_created", "workspace_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    search_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_jobs.id", ondelete="CASCADE"), index=True
    )
    seed_extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), index=True
    )
    seed_event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_company: Mapped[str] = mapped_column(String(1200), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    discovery_observation_ids: Mapped[list[str]] = mapped_column(json_type, nullable=False)
    investigation_decision: Mapped[dict | None] = mapped_column(nullable_json_type, nullable=True)
    investigation_queries: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    investigation_observations: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    synthesis_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    synthesis_provider_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    synthesis_usage: Mapped[dict | None] = mapped_column(nullable_json_type, nullable=True)
    report: Mapped[dict | None] = mapped_column(nullable_json_type, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspace: Mapped[Workspace] = relationship()
    search_job: Mapped[SearchJob] = relationship()
    seed_extraction_run: Mapped[ExtractionRun] = relationship()
