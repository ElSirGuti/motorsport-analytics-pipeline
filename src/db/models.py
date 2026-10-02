"""Modelos SQLAlchemy 2.x de la biblioteca de sesiones.

Los tipos son portables: ``Uuid`` (nativo en PostgreSQL, CHAR(32) en SQLite) y JSON
generico con variante JSONB en PostgreSQL.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# JSON generico; en PostgreSQL se usa JSONB (indexable / mas eficiente).
JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class LibrarySession(Base):
    """Una sesion analizada guardada en la biblioteca.

    ``payload`` es flexible: ``{"session": {...}, "stint": {...}, "extras": {...}}``
    (extras puede traer optimal_lap, setup, data_quality, ...).
    """

    __tablename__ = "library_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    sim: Mapped[Optional[str]] = mapped_column(String(80))
    vehicle: Mapped[Optional[str]] = mapped_column(String(160))
    venue: Mapped[Optional[str]] = mapped_column(String(160))
    driver: Mapped[Optional[str]] = mapped_column(String(160))
    best_lap_s: Mapped[Optional[float]] = mapped_column(Float)
    n_laps: Mapped[Optional[int]] = mapped_column(Integer)
    source_filename: Mapped[Optional[str]] = mapped_column(String(260))
    file_sha256: Mapped[Optional[str]] = mapped_column(String(64))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    # Reservado para un futuro sistema de usuarios (hoy siempre NULL).
    owner_id: Mapped[Optional[str]] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)

    __table_args__ = (
        Index("ix_library_sessions_dedupe", "file_sha256", "venue"),
        Index("ix_library_sessions_venue_vehicle", "venue", "vehicle"),
        Index("ix_library_sessions_created_at", "created_at"),
    )
