from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, nullable_json_type

if TYPE_CHECKING:
    from app.models.extraction_source import ExtractionSource
    from app.models.onboarding import Workspace
    from app.models.signal_observation import SignalObservation


class ExtractionRun(TimestampMixin, Base):
    __tablename__ = "extraction_runs"
    __table_args__ = (
        CheckConstraint(
            "status in ('succeeded', 'failed')",
            name="ck_extraction_runs_status",
        ),
        CheckConstraint(
            "content_basis in ('raw_content', 'snippet')",
            name="ck_extraction_runs_content_basis",
        ),
        CheckConstraint("model_calls >= 0", name="ck_extraction_runs_model_calls"),
        CheckConstraint(
            "(status = 'succeeded' and error_code is null and validated_output is not null) "
            "or (status = 'failed' and error_code is not null and validated_output is null)",
            name="ck_extraction_runs_result_shape",
        ),
        Index("ix_extraction_runs_workspace_created", "workspace_id", "created_at"),
        UniqueConstraint("id", "workspace_id", name="uq_extraction_runs_id_workspace"),
        Index(
            "uq_extraction_runs_success_cache",
            "workspace_id",
            "cache_key",
            unique=True,
            postgresql_where=text("status = 'succeeded'"),
            sqlite_where=text("status = 'succeeded'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), index=True
    )
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    preparation_version: Mapped[str] = mapped_column(String(32), nullable=False)
    extraction_version: Mapped[str] = mapped_column(String(32), nullable=False)
    specification_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    content_basis: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_usage: Mapped[dict | None] = mapped_column(nullable_json_type, nullable=True)
    model_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    validated_output: Mapped[dict | None] = mapped_column(nullable_json_type, nullable=True)

    workspace: Mapped[Workspace] = relationship()
    sources: Mapped[list[ExtractionSource]] = relationship(
        back_populates="extraction_run", cascade="all, delete-orphan"
    )
    observations: Mapped[list[SignalObservation]] = relationship(
        back_populates="extraction_run", cascade="all, delete-orphan"
    )
