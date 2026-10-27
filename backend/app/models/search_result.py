from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import json_type

if TYPE_CHECKING:
    from app.models.search_query import SearchQuery


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (
        UniqueConstraint("search_query_id", "result_rank", name="uq_search_results_query_rank"),
        CheckConstraint("result_rank > 0", name="ck_search_results_rank"),
        CheckConstraint("length(url) > 0", name="ck_search_results_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    search_query_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("search_queries.id", ondelete="CASCADE"), index=True
    )
    result_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_result_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    search_query: Mapped[SearchQuery] = relationship(back_populates="results")
