"""ConversationMessage model for individual chat messages."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import BaseModel

if TYPE_CHECKING:
    from packages.db.models.conversation import Conversation
    from packages.db.models.copilot_feedback import CopilotFeedback


class ConversationMessage(BaseModel):
    """Model for individual messages within a conversation."""

    __tablename__ = "conversation_messages"

    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    message_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )

    feedback: Mapped[Optional["CopilotFeedback"]] = relationship(
        "CopilotFeedback",
        back_populates="message",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ConversationMessage(id={self.id}, role={self.role})>"
