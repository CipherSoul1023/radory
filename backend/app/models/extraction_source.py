from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.extraction_run import ExtractionRun
    from app.models.search_result import SearchResult


class ExtractionSource(TimestampMixin, Base):
    __tablename__ = "extraction_sources"
    __table_args__ = (
        UniqueConstraint(
            "extraction_run_id",
            "search_result_id",
            name="uq_extraction_sources_run_result",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("extraction_runs.id", ondelete="CASCADE"), index=True
    )
    search_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_results.id", ondelete="CASCADE"), index=True
    )

    extraction_run: Mapped[ExtractionRun] = relationship(back_populates="sources")
    search_result: Mapped[SearchResult] = relationship()
