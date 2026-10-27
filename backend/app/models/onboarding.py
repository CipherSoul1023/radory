from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.base import TimestampMixin, json_type

if TYPE_CHECKING:
    from app.models.search_job import SearchJob


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clerk_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    memberships: Mapped[list[WorkspaceMember]] = relationship(back_populates="user")
    initiated_search_jobs: Mapped[list[SearchJob]] = relationship(
        back_populates="initiated_by_user"
    )


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        CheckConstraint(
            "provisioning_status in ('pending', 'failed', 'complete')",
            name="ck_workspaces_provisioning_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clerk_organization_id: Mapped[str | None] = mapped_column(
        String(64), unique=True, index=True, nullable=True
    )
    clerk_slug: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(256))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True, index=True
    )
    provisioning_status: Mapped[str] = mapped_column(String(20), default="pending")
    provisioning_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    members: Mapped[list[WorkspaceMember]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
    brokerage_profile: Mapped[BrokerageProfile | None] = relationship(
        back_populates="workspace", cascade="all, delete-orphan", uselist=False
    )
    search_jobs: Mapped[list[SearchJob]] = relationship(back_populates="workspace")


class WorkspaceMember(TimestampMixin, Base):
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_members_workspace_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    clerk_role: Mapped[str] = mapped_column(String(64), default="org:member")

    workspace: Mapped[Workspace] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class BrokerageProfile(TimestampMixin, Base):
    __tablename__ = "brokerage_profiles"
    __table_args__ = (
        CheckConstraint(
            "min_transaction_size_sqm > 0",
            name="ck_brokerage_profiles_min_transaction_size",
        ),
        CheckConstraint(
            "min_transaction_size_sqm <= ideal_transaction_size_min_sqm",
            name="ck_brokerage_profiles_min_ideal",
        ),
        CheckConstraint(
            "ideal_transaction_size_min_sqm <= ideal_transaction_size_max_sqm",
            name="ck_brokerage_profiles_ideal_range",
        ),
        CheckConstraint(
            "ideal_transaction_size_max_sqm <= max_transaction_size_sqm",
            name="ck_brokerage_profiles_ideal_max",
        ),
        CheckConstraint("country = 'South Africa'", name="ck_brokerage_profiles_country"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True, index=True
    )
    property_sectors: Mapped[list[str]] = mapped_column(json_type, default=list)
    custom_property_sectors: Mapped[list[str]] = mapped_column(json_type, default=list)
    country: Mapped[str] = mapped_column(String(100))
    primary_market: Mapped[str] = mapped_column(String(120))
    submarkets: Mapped[list[str]] = mapped_column(json_type, default=list)
    # Deprecated compatibility column. Active onboarding always persists an empty list.
    custom_submarkets: Mapped[list[str]] = mapped_column(json_type, default=list)
    min_transaction_size_sqm: Mapped[int] = mapped_column(Integer)
    ideal_transaction_size_min_sqm: Mapped[int] = mapped_column(Integer)
    ideal_transaction_size_max_sqm: Mapped[int] = mapped_column(Integer)
    max_transaction_size_sqm: Mapped[int] = mapped_column(Integer)
    industries: Mapped[list[str]] = mapped_column(json_type, default=list)
    custom_industries: Mapped[list[str]] = mapped_column(json_type, default=list)
    prospecting_horizon: Mapped[str] = mapped_column(String(30))
    opportunity_types: Mapped[list[str]] = mapped_column(json_type, default=list)
    priority_factors: Mapped[list[str]] = mapped_column(json_type, default=list)

    workspace: Mapped[Workspace] = relationship(back_populates="brokerage_profile")
    search_jobs: Mapped[list[SearchJob]] = relationship(back_populates="brokerage_profile")
