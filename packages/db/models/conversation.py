"""Conversation model for persisting chat history."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import BaseModel

if TYPE_CHECKING:
    from packages.db.models.conversation_message import ConversationMessage
    from packages.db.models.project import Project
    from packages.db.models.user import User


class Conversation(BaseModel):
    """Model for persisting orchestrator chat conversations."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "session_id",
            name="uq_conversations_user_id_session_id",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    project_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    stage: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    plan_data: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    execution_log: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
    )

    charts: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
    )

    report: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    project: Mapped[Optional["Project"]] = relationship(
        "Project", back_populates="conversations"
    )
    messages: Mapped[list["ConversationMessage"]] = relationship(
        "ConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, session_id={self.session_id}, title={self.title})>"
