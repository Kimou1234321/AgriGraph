"""ORM models for users and saved simulations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.api.database import Base

CONSTANTS: dict[str, Any] = {
    "EMAIL_MAX_LENGTH": 320,
    "NAME_MAX_LENGTH": 120,
    "SIMULATION_NAME_MAX_LENGTH": 120,
}


class User(Base):
    """Registered application user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(CONSTANTS["EMAIL_MAX_LENGTH"]), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(CONSTANTS["NAME_MAX_LENGTH"]), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    simulations: Mapped[list["SavedSimulation"]] = relationship(
        "SavedSimulation",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class SavedSimulation(Base):
    """User-owned saved counterfactual simulation."""

    __tablename__ = "saved_simulations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(CONSTANTS["SIMULATION_NAME_MAX_LENGTH"]), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenarios_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    horizon: Mapped[int] = mapped_column(Integer)
    pipeline_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="simulations")
