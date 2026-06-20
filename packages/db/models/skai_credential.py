"""SKAI credential model for storing per-user Cognito tokens."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import BaseModel

if TYPE_CHECKING:
    from packages.db.models.user import User


class SkaiCredential(BaseModel):
    """Stores per-user SKAI Cognito credentials for API access."""

    __tablename__ = "skai_credentials"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="User owning these SKAI credentials",
    )

    skai_username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="SKAI username used for Cognito authentication",
    )

    refresh_token: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Cognito refresh token",
    )

    id_token: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Cached Cognito ID token used for SKAI API requests",
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="ID token expiration timestamp",
    )

    last_refreshed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last time the tokens were refreshed",
    )

    user: Mapped["User"] = relationship("User", back_populates="skai_credentials")

    def __repr__(self) -> str:
        return f"<SkaiCredential(user_id={self.user_id})>"
