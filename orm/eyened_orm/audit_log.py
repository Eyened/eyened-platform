from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

__all__ = ["AuditLog"]


class AuditLog(Base):
    """Append-only audit record, written in the same transaction as the data it describes.

    The authoritative compliance sink (design §3, Sink 1). ``ActorID`` is a plain
    nullable integer, not a FK: audit rows must outlive the ``Creator`` they name.
    Trusted paths (CLI/worker) leave ``ActorID`` NULL and set ``TrustedPath``.
    """

    __tablename__ = "AuditLog"

    AuditLogID: Mapped[int] = mapped_column(primary_key=True)
    # Python-side default so the buffered stdout event mirrors the row without a DB round-trip.
    Timestamp: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    ActorID: Mapped[Optional[int]] = mapped_column(default=None)
    TrustedPath: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    Action: Mapped[str] = mapped_column(String(16))
    Entity: Mapped[str] = mapped_column(String(64))
    EntityID: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    ProjectID: Mapped[Optional[int]] = mapped_column(default=None)
    Changes: Mapped[Optional[dict]] = mapped_column(JSON, default=None)
