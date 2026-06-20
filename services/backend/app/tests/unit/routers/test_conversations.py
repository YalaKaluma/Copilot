"""Unit tests for conversations router (to_conversation_detail mapper)."""

from datetime import datetime, UTC
from uuid import uuid4

from routers.conversations import to_conversation_detail


class TestToConversationDetail:
    """Test mapping conversation ORM to ConversationDetail with feedback."""

    def test_includes_feedback_on_message_when_present(self):
        """Messages with feedback have feedback in the response; others have null."""
        conv_id = uuid4()
        session_id = "session-123"
        msg_with_feedback_id = uuid4()
        msg_without_feedback_id = uuid4()

        mock_feedback = type("Feedback", (), {})()
        mock_feedback.category = "positive"
        mock_feedback.reason = "Helpful"

        msg_with_feedback = type("Message", (), {})()
        msg_with_feedback.id = msg_with_feedback_id
        msg_with_feedback.role = "assistant"
        msg_with_feedback.content = "Reply"
        msg_with_feedback.message_metadata = None
        msg_with_feedback.feedback = mock_feedback
        msg_with_feedback.created_at = datetime.now(UTC)
        msg_with_feedback.updated_at = datetime.now(UTC)

        msg_without_feedback = type("Message", (), {})()
        msg_without_feedback.id = msg_without_feedback_id
        msg_without_feedback.role = "user"
        msg_without_feedback.content = "Hi"
        msg_without_feedback.message_metadata = None
        msg_without_feedback.feedback = None
        msg_without_feedback.created_at = datetime.now(UTC)
        msg_without_feedback.updated_at = datetime.now(UTC)

        mock_conv = type("Conversation", (), {})()
        mock_conv.id = conv_id
        mock_conv.session_id = session_id
        mock_conv.title = "Chat"
        mock_conv.stage = "done"
        mock_conv.plan_data = None
        mock_conv.execution_log = None
        mock_conv.created_at = datetime.now(UTC)
        mock_conv.updated_at = datetime.now(UTC)
        mock_conv.messages = [msg_with_feedback, msg_without_feedback]
        mock_conv.report = None
        mock_conv.project_id = None
        mock_conv.charts = [
            {"id": "chart-1", "title": "Sales", "chart_type": "bar", "data": []},
        ]

        detail = to_conversation_detail(mock_conv)

        assert detail.id == conv_id
        assert detail.session_id == session_id
        assert len(detail.messages) == 2
        assert detail.charts is not None
        assert len(detail.charts) == 1
        assert detail.charts[0].id == "chart-1"
        assert detail.charts[0].title == "Sales"
        assert detail.charts[0].chart_type == "bar"
        assert detail.project_id is None

        m1, m2 = detail.messages
        assert m1.id == msg_with_feedback_id
        assert m1.feedback is not None
        assert m1.feedback.category == "positive"
        assert m1.feedback.reason == "Helpful"

        assert m2.id == msg_without_feedback_id
        assert m2.feedback is None

    def test_includes_project_id_when_set(self):
        """Conversation with project_id maps to detail with project_id."""
        conv_id = uuid4()
        project_id = uuid4()
        session_id = "session-with-project"

        mock_conv = type("Conversation", (), {})()
        mock_conv.id = conv_id
        mock_conv.session_id = session_id
        mock_conv.title = "Project Chat"
        mock_conv.stage = "done"
        mock_conv.plan_data = None
        mock_conv.execution_log = None
        mock_conv.created_at = datetime.now(UTC)
        mock_conv.updated_at = datetime.now(UTC)
        mock_conv.messages = []
        mock_conv.report = "Report text"
        mock_conv.project_id = project_id
        mock_conv.charts = []

        detail = to_conversation_detail(mock_conv)

        assert detail.id == conv_id
        assert detail.project_id == project_id
        assert detail.report == "Report text"
