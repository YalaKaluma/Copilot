"""Unit tests for FeedbackService."""

from uuid import uuid4

import pytest

from core.exceptions import ConflictError, ForbiddenError, NotFoundError
from services.feedback_service import FeedbackService


class TestFeedbackServiceSubmitFeedback:
    """Test submit_feedback validation and storage."""

    @pytest.mark.asyncio
    async def test_raises_not_found_when_message_missing(self, mocker):
        """When message does not exist, raise NotFoundError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()

        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = msg_result

        message_id = uuid4()
        user_id = uuid4()

        with pytest.raises(NotFoundError, match="Conversation message"):
            await service.submit_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                category="positive",
                reason=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_conversation_owned_by_other_user(self, mocker):
        """When message belongs to another user's conversation, raise ForbiddenError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()

        mock_conversation = mocker.Mock()
        mock_conversation.user_id = uuid4()  # different from caller
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation

        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = msg_result

        message_id = uuid4()
        user_id = uuid4()

        with pytest.raises(ForbiddenError, match="another user's conversation"):
            await service.submit_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                category="positive",
                reason=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_message_role_is_user(self, mocker):
        """When message role is 'user', raise ForbiddenError; only assistant messages can be rated."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()

        user_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "user"
        mock_message.conversation = mock_conversation

        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = msg_result

        message_id = uuid4()

        with pytest.raises(ForbiddenError, match="user message.*only assistant"):
            await service.submit_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                category="positive",
                reason=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_conflict_when_feedback_already_submitted(self, mocker):
        """When feedback already exists for the message, raise ConflictError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()

        user_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation

        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        existing_result = mocker.Mock()
        existing_result.scalar_one_or_none.return_value = (
            mocker.Mock()
        )  # existing feedback
        mock_db.execute.side_effect = [msg_result, existing_result]

        message_id = uuid4()

        with pytest.raises(ConflictError, match="already submitted"):
            await service.submit_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                category="positive",
                reason=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_success_creates_feedback_and_commits(self, mocker):
        """When message is assistant and no existing feedback, create feedback and commit."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()

        user_id = uuid4()
        message_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.id = message_id
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation

        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        existing_result = mocker.Mock()
        existing_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [msg_result, existing_result]

        mock_db.add = mocker.Mock()
        mock_db.refresh = mocker.AsyncMock()
        mock_db.commit = mocker.AsyncMock()
        mocker.patch.object(service, "_create_langfuse_score", return_value=None)

        result = await service.submit_feedback(
            assistant_message_id=message_id,
            user_id=user_id,
            category="negative",
            reason="Not helpful",
            db=mock_db,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_any_call()
        assert result is not None


class TestFeedbackServiceDeleteFeedback:
    """Test delete_feedback validation and removal."""

    @pytest.mark.asyncio
    async def test_raises_not_found_when_message_missing(self, mocker):
        """When message does not exist, raise NotFoundError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = msg_result

        message_id = uuid4()
        user_id = uuid4()

        with pytest.raises(NotFoundError, match="Conversation message"):
            await service.delete_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_conversation_owned_by_other_user(self, mocker):
        """When message belongs to another user's conversation, raise ForbiddenError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = uuid4()
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        mock_db.execute.return_value = msg_result

        message_id = uuid4()
        user_id = uuid4()

        with pytest.raises(ForbiddenError, match="another user's conversation"):
            await service.delete_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_success_when_no_feedback_idempotent(self, mocker):
        """When message exists but has no feedback, return without error (idempotent)."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        message_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        feedback_result = mocker.Mock()
        feedback_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [msg_result, feedback_result]
        mock_db.commit = mocker.AsyncMock()

        await service.delete_feedback(
            assistant_message_id=message_id,
            user_id=user_id,
            db=mock_db,
        )

        mock_db.delete.assert_not_called()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_feedback_owned_by_other_user(self, mocker):
        """When feedback exists but was submitted by another user, raise ForbiddenError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        message_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation
        mock_feedback = mocker.Mock()
        mock_feedback.user_id = uuid4()  # different from caller
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        feedback_result = mocker.Mock()
        feedback_result.scalar_one_or_none.return_value = mock_feedback
        mock_db.execute.side_effect = [msg_result, feedback_result]
        mock_db.delete = mocker.AsyncMock()

        with pytest.raises(ForbiddenError, match="another user's conversation"):
            await service.delete_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_success_deletes_feedback_and_commits(self, mocker):
        """When feedback exists and user owns it, delete and commit."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        message_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation
        mock_feedback = mocker.Mock()
        mock_feedback.user_id = user_id
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        feedback_result = mocker.Mock()
        feedback_result.scalar_one_or_none.return_value = mock_feedback
        mock_db.execute.side_effect = [msg_result, feedback_result]
        mock_db.delete = mocker.AsyncMock()
        mock_db.commit = mocker.AsyncMock()

        await service.delete_feedback(
            assistant_message_id=message_id,
            user_id=user_id,
            db=mock_db,
        )

        mock_db.delete.assert_called_once_with(mock_feedback)
        mock_db.commit.assert_called_once()


class TestFeedbackServiceUpdateFeedback:
    """Test update_feedback validation and update."""

    @pytest.mark.asyncio
    async def test_raises_not_found_when_message_missing(self, mocker):
        """When message does not exist, raise NotFoundError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = msg_result

        message_id = uuid4()
        user_id = uuid4()

        with pytest.raises(NotFoundError, match="Conversation message"):
            await service.update_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                category="positive",
                reason=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_not_found_when_no_feedback(self, mocker):
        """When message exists but has no feedback, raise NotFoundError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        message_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        feedback_result = mocker.Mock()
        feedback_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [msg_result, feedback_result]

        with pytest.raises(NotFoundError, match="Feedback"):
            await service.update_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                category="positive",
                reason=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_raises_forbidden_when_feedback_owned_by_other_user(self, mocker):
        """When feedback exists but was submitted by another user, raise ForbiddenError."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        message_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation
        mock_feedback = mocker.Mock()
        mock_feedback.user_id = uuid4()
        mock_feedback.category = "positive"
        mock_feedback.reason = None
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        feedback_result = mocker.Mock()
        feedback_result.scalar_one_or_none.return_value = mock_feedback
        mock_db.execute.side_effect = [msg_result, feedback_result]

        with pytest.raises(ForbiddenError, match="another user's conversation"):
            await service.update_feedback(
                assistant_message_id=message_id,
                user_id=user_id,
                category="negative",
                reason=None,
                db=mock_db,
            )

    @pytest.mark.asyncio
    async def test_success_updates_feedback_and_commits(self, mocker):
        """When feedback exists and user owns it, update and commit."""
        service = FeedbackService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        message_id = uuid4()
        mock_conversation = mocker.Mock()
        mock_conversation.user_id = user_id
        mock_message = mocker.Mock()
        mock_message.role = "assistant"
        mock_message.conversation = mock_conversation
        mock_feedback = mocker.Mock()
        mock_feedback.user_id = user_id
        mock_feedback.category = "positive"
        mock_feedback.reason = "Was good"
        msg_result = mocker.Mock()
        msg_result.scalar_one_or_none.return_value = mock_message
        feedback_result = mocker.Mock()
        feedback_result.scalar_one_or_none.return_value = mock_feedback
        mock_db.execute.side_effect = [msg_result, feedback_result]
        mock_db.flush = mocker.AsyncMock()
        mock_db.refresh = mocker.AsyncMock()
        mock_db.commit = mocker.AsyncMock()
        mocker.patch.object(service, "_create_langfuse_score", return_value=None)

        result = await service.update_feedback(
            assistant_message_id=message_id,
            user_id=user_id,
            category="negative",
            reason="Changed mind",
            db=mock_db,
        )

        assert mock_feedback.category == "negative"
        assert mock_feedback.reason == "Changed mind"
        mock_db.commit.assert_called_once()
        assert result is mock_feedback
