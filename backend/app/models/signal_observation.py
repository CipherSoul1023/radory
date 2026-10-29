from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
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
    from app.models.extraction_run import ExtractionRun


class SignalObservation(TimestampMixin, Base):
    __tablename__ = "signal_observations"
    __table_args__ = (
        UniqueConstraint(
            "extraction_run_id",
            "event_index",
            "signal_key",
            name="uq_signal_observations_run_event_signal",
        ),
        ForeignKeyConstraint(
            ["extraction_run_id", "workspace_id"],
            ["extraction_runs.id", "extraction_runs.workspace_id"],
            ondelete="CASCADE",
            name="fk_signal_observations_run_workspace",
        ),
        CheckConstraint("event_index >= 0", name="ck_signal_observations_event_index"),
        CheckConstraint(
            "stage in ('planned', 'underway', 'completed', 'cancelled', 'unclear')",
            name="ck_signal_observations_stage",
        ),
        CheckConstraint("length(subject_company) > 0", name="ck_signal_observations_company"),
        CheckConstraint("length(summary) > 0", name="ck_signal_observations_summary"),
        Index("ix_signal_observations_workspace_created", "workspace_id", "created_at"),
        Index("ix_signal_observations_workspace_signal", "workspace_id", "signal_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(index=True)
    event_index: Mapped[int] = mapped_column(Integer, nullable=False)
    signal_key: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_company: Mapped[str] = mapped_column(String(1200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_company_evidence: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    summary_evidence: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    signal_evidence: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    stage_evidence: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    locations: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    timing: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    related_companies: Mapped[list[dict]] = mapped_column(json_type, nullable=False)
    missing_facts: Mapped[list[str]] = mapped_column(json_type, nullable=False)

    extraction_run: Mapped[ExtractionRun] = relationship(back_populates="observations")
