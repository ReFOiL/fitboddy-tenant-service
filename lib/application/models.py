from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from application.db import Base


class DiscoveryProfileModel(Base):
    __tablename__ = "discovery_profiles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    is_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    looking_for_trainer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)


class TrainerClientRelationModel(Base):
    __tablename__ = "trainer_client_relations"
    __table_args__ = (UniqueConstraint("trainer_user_id", "client_user_id", name="uq_trainer_client_pair"),)

    relation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    trainer_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
