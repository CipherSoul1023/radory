from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

json_type = JSON().with_variant(JSONB(), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    clerk_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    memberships: Mapped[list[WorkspaceMember]] = relationship(back_populates="user")


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
        CheckConstraint("minimum_sqm >= 0", name="ck_brokerage_profiles_minimum_sqm"),
        CheckConstraint("minimum_sqm <= ideal_minimum_sqm", name="ck_brokerage_profiles_min_ideal"),
        CheckConstraint(
            "ideal_minimum_sqm <= ideal_maximum_sqm",
            name="ck_brokerage_profiles_ideal_range",
        ),
        CheckConstraint("ideal_maximum_sqm <= maximum_sqm", name="ck_brokerage_profiles_ideal_max"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True, index=True
    )
    property_sectors: Mapped[list[str]] = mapped_column(json_type)
    country: Mapped[str] = mapped_column(String(100))
    primary_metro: Mapped[str] = mapped_column(String(120))
    submarkets: Mapped[list[str]] = mapped_column(json_type)
    minimum_sqm: Mapped[int] = mapped_column(Integer)
    ideal_minimum_sqm: Mapped[int] = mapped_column(Integer)
    ideal_maximum_sqm: Mapped[int] = mapped_column(Integer)
    maximum_sqm: Mapped[int] = mapped_column(Integer)
    industries: Mapped[list[str]] = mapped_column(json_type)
    prospecting_horizon: Mapped[str] = mapped_column(String(30))
    opportunity_types: Mapped[list[str]] = mapped_column(json_type)
    priorities: Mapped[list[str]] = mapped_column(json_type)

    workspace: Mapped[Workspace] = relationship(back_populates="brokerage_profile")
