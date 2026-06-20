"""Service for submitting and storing user feedback on conversation messages."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import ConflictError, ForbiddenError, NotFoundError
from packages.db.models import CopilotFeedback, ConversationMessage

from packages.langfuse.client import get_langfuse_client
from services.tracing import to_trace_id


async def _get_message_and_validate(
    assistant_message_id: UUID, user_id: UUID, db: AsyncSession
) -> ConversationMessage:
    """Load message with conversation and validate ownership and role. Raises if invalid."""
    stmt = (
        select(ConversationMessage)
        .options(selectinload(ConversationMessage.conversation))
        .where(ConversationMessage.id == assistant_message_id)
    )
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()
    if not message:
        raise NotFoundError("Conversation message", assistant_message_id)
    if message.conversation.user_id != user_id:
        raise ForbiddenError(
            "Cannot modify feedback for a message in another user's conversation"
        )
    if message.role == "user":
        raise ForbiddenError(
            "Cannot modify feedback for a user message; only assistant messages can be rated"
        )
    return message


class FeedbackService:
    """Handle feedback submission and Langfuse score annotation."""

    async def submit_feedback(
        self,
        assistant_message_id: UUID,
        user_id: UUID,
        category: str,
        reason: str | None,
        db: AsyncSession,
    ) -> CopilotFeedback:
        """
        Store feedback for a conversation message (the id is the message id).

        Raises:
            NotFoundError: Message not found.
            ForbiddenError: Message belongs to another user's conversation, or message role is user (only assistant messages can be rated).
            ConflictError: Feedback already submitted for this message.
        """
        message = await _get_message_and_validate(assistant_message_id, user_id, db)

        existing = await db.execute(
            select(CopilotFeedback).where(
                CopilotFeedback.message_id == assistant_message_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("Feedback already submitted for this message")

        feedback = CopilotFeedback(
            message_id=assistant_message_id,
            user_id=user_id,
            category=category,
            reason=reason,
        )
        db.add(feedback)
        await db.flush()
        await db.refresh(feedback)

        self._create_langfuse_score(
            trace_id=to_trace_id(message.id),
            category=category,
            reason=reason,
            score_id=str(assistant_message_id),
        )

        await db.commit()
        return feedback

    async def delete_feedback(
        self,
        assistant_message_id: UUID,
        user_id: UUID,
        db: AsyncSession,
    ) -> None:
        """
        Remove feedback for a conversation message.
        Idempotent: returns successfully even if no feedback exists for the message.

        Raises:
            NotFoundError: Message not found.
            ForbiddenError: Message belongs to another user or is a user message.
        """
        await _get_message_and_validate(assistant_message_id, user_id, db)
        stmt = select(CopilotFeedback).where(
            CopilotFeedback.message_id == assistant_message_id
        )
        result = await db.execute(stmt)
        feedback = result.scalar_one_or_none()
        if not feedback:
            await db.commit()
            return
        if feedback.user_id != user_id:
            raise ForbiddenError(
                "Cannot delete feedback for a message in another user's conversation"
            )
        await db.delete(feedback)
        await db.commit()

    async def update_feedback(
        self,
        assistant_message_id: UUID,
        user_id: UUID,
        category: str | None,
        reason: str | None,
        db: AsyncSession,
    ) -> CopilotFeedback:
        """
        Update existing feedback for a conversation message.

        At least one of category or reason must be provided.

        Raises:
            NotFoundError: Message or feedback not found.
            ForbiddenError: Message belongs to another user or is a user message.
        """
        await _get_message_and_validate(assistant_message_id, user_id, db)
        stmt = select(CopilotFeedback).where(
            CopilotFeedback.message_id == assistant_message_id
        )
        result = await db.execute(stmt)
        feedback = result.scalar_one_or_none()
        if not feedback:
            raise NotFoundError("Feedback", assistant_message_id)
        if feedback.user_id != user_id:
            raise ForbiddenError(
                "Cannot update feedback for a message in another user's conversation"
            )
        if category is not None:
            feedback.category = category
        if reason is not None:
            feedback.reason = reason
        await db.flush()
        await db.refresh(feedback)
        if category is not None or reason is not None:
            self._create_langfuse_score(
                trace_id=to_trace_id(assistant_message_id),
                category=feedback.category,
                reason=feedback.reason,
                score_id=str(assistant_message_id),
            )
        await db.commit()
        return feedback

    def _create_langfuse_score(
        self,
        trace_id: str,
        category: str,
        reason: str | None,
        score_id: str,
    ) -> None:
        """Create a user_feedback score on the Langfuse trace (idempotent by score_id)."""
        langfuse = get_langfuse_client()
        if not langfuse:
            return
        try:
            langfuse.create_score(
                trace_id=trace_id,
                name="user_feedback",
                value=1 if category == "positive" else 0,
                data_type="BOOLEAN",
                comment=reason,
                score_id=score_id,
            )
            langfuse.flush()
        except Exception:
            pass  # Do not fail feedback storage if Langfuse fails


def get_feedback_service() -> FeedbackService:
    """Return the feedback service instance."""
    return FeedbackService()
