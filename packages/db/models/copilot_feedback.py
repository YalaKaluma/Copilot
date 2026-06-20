"""CopilotFeedback model for user feedback on a copilot response."""

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.db.base import BaseModel

if TYPE_CHECKING:
    from packages.db.models.user import User
    from packages.db.models.conversation_message import ConversationMessage


class CopilotFeedback(BaseModel):
    """User feedback on a single conversation message (one feedback per message)."""

    __tablename__ = "copilot_feedback"

    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    message: Mapped["ConversationMessage"] = relationship(
        "ConversationMessage",
        back_populates="feedback",
    )
    user: Mapped["User"] = relationship("User", back_populates="copilot_feedback")

    def __repr__(self) -> str:
        return f"<CopilotFeedback(id={self.id}, message_id={self.message_id}, category={self.category})>"
