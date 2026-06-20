"""Unit tests for ConversationService behavior."""

from datetime import datetime, UTC
from uuid import uuid4

import pytest

from core.exceptions import NotFoundError
from services.conversation_service import ConversationService


class TestConversationServiceCreateOrUpdate:
    """Test create/update behavior for conversation persistence."""

    @pytest.mark.asyncio
    async def test_reuses_soft_deleted_conversation(self, mocker):
        """Soft-deleted sessions are returned as-is; no restore, no re-insert (caller gets stale row)."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        conversation_id = uuid4()

        existing = mocker.Mock()
        existing.id = conversation_id
        existing.is_deleted = True
        existing.deleted_at = datetime.now(UTC)
        existing.stage = None
        existing.plan_data = None
        existing.execution_log = None

        select_result = mocker.Mock()
        select_result.scalar_one_or_none.return_value = existing
        message_ids_result = mocker.Mock()
        message_ids_result.all.return_value = []  # no existing messages
        mock_db.execute.side_effect = [select_result, message_ids_result]

        result = await service.create_or_update_conversation(
            user_id=uuid4(),
            session_id="session-123",
            stage="done",
            plan_data={"goal": "test"},
            execution_log=[],
            charts=None,
            messages=[],
            db=mock_db,
        )

        # Service returns the soft-deleted row without restoring or re-inserting
        assert result is existing
        assert existing.is_deleted is True
        assert existing.deleted_at is not None
        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_merge_updates_existing_and_inserts_new_messages(self, mocker):
        """When conversation exists, existing message rows are updated and new ones inserted."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        conversation_id = uuid4()
        user_id = uuid4()
        msg_a_id = uuid4()
        msg_b_id = uuid4()
        msg_c_id = uuid4()

        existing_conv = mocker.Mock()
        existing_conv.id = conversation_id
        existing_conv.is_deleted = False
        existing_conv.deleted_at = None
        existing_conv.stage = None
        existing_conv.plan_data = None
        existing_conv.execution_log = None

        existing_row_a = mocker.Mock()
        existing_row_a.id = msg_a_id
        existing_row_a.role = "user"
        existing_row_a.content = "old"
        existing_row_a.message_metadata = None

        select_conv_result = mocker.Mock()
        select_conv_result.scalar_one_or_none.return_value = existing_conv
        select_msg_ids_result = mocker.Mock()
        select_msg_ids_result.all.return_value = [(msg_a_id,), (msg_b_id,)]
        select_rows_result = mocker.Mock()
        select_rows_result.scalars.return_value.all.return_value = [
            existing_row_a,
            mocker.Mock(
                id=msg_b_id, role="assistant", content="old b", message_metadata=None
            ),
        ]
        mock_db.execute.side_effect = [
            select_conv_result,
            select_msg_ids_result,
            select_rows_result,
        ]

        messages = [
            {"id": msg_a_id, "role": "user", "content": "updated a", "metadata": None},
            {
                "id": msg_b_id,
                "role": "assistant",
                "content": "updated b",
                "metadata": None,
            },
            {"id": msg_c_id, "role": "user", "content": "new c", "metadata": None},
        ]

        conv = await service.create_or_update_conversation(
            user_id=user_id,
            session_id="session-merge",
            stage="done",
            plan_data=None,
            execution_log=None,
            charts=None,
            messages=messages,
            db=mock_db,
        )

        assert conv is existing_conv
        assert existing_row_a.role == "user"
        assert existing_row_a.content == "updated a"
        assert existing_row_a.message_metadata is None
        mock_db.add.assert_called_once()
        (added_msg,) = mock_db.add.call_args[0]
        assert added_msg.id == msg_c_id
        assert added_msg.content == "new c"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_merge_deletes_messages_not_in_request(self, mocker):
        """When conversation exists, message rows not in the request are deleted."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        conversation_id = uuid4()
        user_id = uuid4()
        msg_a_id = uuid4()
        msg_b_id = uuid4()
        msg_removed_id = uuid4()

        existing_conv = mocker.Mock()
        existing_conv.id = conversation_id
        existing_conv.is_deleted = False
        existing_conv.deleted_at = None
        existing_conv.stage = None
        existing_conv.plan_data = None
        existing_conv.execution_log = None

        row_a = mocker.Mock(
            id=msg_a_id, role="user", content="a", message_metadata=None
        )
        row_b = mocker.Mock(
            id=msg_b_id, role="assistant", content="b", message_metadata=None
        )
        select_conv_result = mocker.Mock()
        select_conv_result.scalar_one_or_none.return_value = existing_conv
        select_msg_ids_result = mocker.Mock()
        select_msg_ids_result.all.return_value = [
            (msg_a_id,),
            (msg_b_id,),
            (msg_removed_id,),
        ]
        select_rows_result = mocker.Mock()
        select_rows_result.scalars.return_value.all.return_value = [row_a, row_b]
        delete_result = mocker.Mock()
        mock_db.execute.side_effect = [
            select_conv_result,
            select_msg_ids_result,
            delete_result,
            select_rows_result,
        ]

        messages = [
            {"id": msg_a_id, "role": "user", "content": "a", "metadata": None},
            {"id": msg_b_id, "role": "assistant", "content": "b", "metadata": None},
        ]

        await service.create_or_update_conversation(
            user_id=user_id,
            session_id="session-delete",
            stage="done",
            plan_data=None,
            execution_log=None,
            charts=None,
            messages=messages,
            db=mock_db,
        )

        assert mock_db.execute.call_count == 4
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_sets_project_id_on_new_conversation(self, mocker):
        """New conversation is created with project_id when provided."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        project_id = uuid4()
        session_id = "session-new-project"

        select_result = mocker.Mock()
        select_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [select_result]

        conv = await service.create_or_update_conversation(
            user_id=user_id,
            session_id=session_id,
            stage="done",
            plan_data=None,
            execution_log=None,
            charts=None,
            messages=[],
            db=mock_db,
            project_id=project_id,
        )

        mock_db.add.assert_called_once()
        (added,) = mock_db.add.call_args[0]
        assert added.project_id == project_id
        assert conv is added

    @pytest.mark.asyncio
    async def test_sets_project_id_on_existing_conversation(self, mocker):
        """Existing conversation is updated with project_id when provided."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        project_id = uuid4()
        conversation_id = uuid4()

        existing = mocker.Mock()
        existing.id = conversation_id
        existing.is_deleted = False
        existing.deleted_at = None
        existing.stage = None
        existing.plan_data = None
        existing.execution_log = None
        existing.project_id = None

        select_result = mocker.Mock()
        select_result.scalar_one_or_none.return_value = existing
        message_ids_result = mocker.Mock()
        message_ids_result.all.return_value = []
        mock_db.execute.side_effect = [select_result, message_ids_result]

        await service.create_or_update_conversation(
            user_id=user_id,
            session_id="session-update-project",
            stage="done",
            plan_data=None,
            execution_log=None,
            charts=None,
            messages=[],
            db=mock_db,
            project_id=project_id,
        )

        assert existing.project_id == project_id
        mock_db.commit.assert_called_once()


class TestConversationServiceListConversations:
    """Test list_conversations with project_id and has_charts/has_report."""

    @pytest.mark.asyncio
    async def test_returns_has_charts_and_has_report_from_rows(self, mocker):
        """Returned list items have has_charts and has_report derived from row data."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        conv_id = uuid4()
        row_with_both = mocker.Mock(
            id=conv_id,
            title="Chat",
            stage="done",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            message_count=2,
            project_id=None,
            charts=[{"id": "c1", "title": "Chart", "chart_type": "bar", "data": []}],
            report="Executive summary here.",
        )
        result_mock = mocker.Mock()
        result_mock.all.return_value = [row_with_both]
        mock_db.execute.return_value = result_mock

        rows = await service.list_conversations(user_id, mock_db, project_id=None)

        assert len(rows) == 1
        assert rows[0]["id"] == conv_id
        assert rows[0]["has_charts"] is True
        assert rows[0]["has_report"] is True
        assert rows[0]["project_id"] is None

    @pytest.mark.asyncio
    async def test_returns_has_charts_false_has_report_false_when_empty(self, mocker):
        """Returned list items have has_charts and has_report False when empty."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        conv_id = uuid4()
        row_empty = mocker.Mock(
            id=conv_id,
            title="Chat",
            stage="done",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            message_count=0,
            project_id=None,
            charts=None,
            report=None,
        )
        result_mock = mocker.Mock()
        result_mock.all.return_value = [row_empty]
        mock_db.execute.return_value = result_mock

        rows = await service.list_conversations(user_id, mock_db, project_id=None)

        assert len(rows) == 1
        assert rows[0]["has_charts"] is False
        assert rows[0]["has_report"] is False

    @pytest.mark.asyncio
    async def test_has_report_false_when_whitespace_only(self, mocker):
        """has_report is False when report is only whitespace."""
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        conv_id = uuid4()
        row_whitespace = mocker.Mock(
            id=conv_id,
            title="Chat",
            stage="done",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            message_count=0,
            project_id=None,
            charts=[],
            report="   \n  ",
        )
        result_mock = mocker.Mock()
        result_mock.all.return_value = [row_whitespace]
        mock_db.execute.return_value = result_mock

        rows = await service.list_conversations(user_id, mock_db, project_id=None)

        assert len(rows) == 1
        assert rows[0]["has_report"] is False


class TestConversationServiceGenerateAndSaveReport:
    """Test generate_and_save_report behavior."""

    @pytest.mark.asyncio
    async def test_sets_and_persists_report_without_requirements(self, mocker):
        """When conversation exists, report is set from LLM and get_conversation is returned."""
        mock_copilot_version = mocker.Mock()
        mock_copilot_version.get_prompt = mocker.Mock(return_value="Generate report")
        mocker.patch(
            "services.conversation_service.get_copilot_version",
            return_value=mock_copilot_version,
        )
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        session_id = "session-report-1"
        conv = mocker.Mock()
        conv.id = uuid4()
        conv.messages = [mocker.Mock(), mocker.Mock()]  # 2 messages

        mocker.patch.object(
            service,
            "get_conversation_by_session_id",
            new=mocker.AsyncMock(return_value=conv),
        )
        mocker.patch.object(
            service,
            "get_conversation",
            new=mocker.AsyncMock(return_value=conv),
        )
        mock_response = mocker.Mock(content="Report for session-report-1. 2 messages.")
        mock_llm = mocker.Mock()
        mock_llm.chat = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "services.conversation_service.get_llm_service",
            return_value=mock_llm,
        )

        result = await service.generate_and_save_report(
            session_id=session_id,
            user_id=user_id,
            db=mock_db,
        )

        assert result is conv
        assert conv.report == "Report for session-report-1. 2 messages."
        mock_db.commit.assert_called_once()
        service.get_conversation.assert_called_once_with(conv.id, user_id, mock_db)

    @pytest.mark.asyncio
    async def test_includes_requirements_in_report_when_provided(self, mocker):
        """When requirements is provided, LLM output is stored; mock returns report including them."""
        mock_copilot_version = mocker.Mock()
        mock_copilot_version.get_prompt = mocker.Mock(return_value="Generate report")
        mocker.patch(
            "services.conversation_service.get_copilot_version",
            return_value=mock_copilot_version,
        )
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        session_id = "session-report-2"
        conv = mocker.Mock()
        conv.id = uuid4()
        conv.messages = []

        mocker.patch.object(
            service,
            "get_conversation_by_session_id",
            new=mocker.AsyncMock(return_value=conv),
        )
        mocker.patch.object(
            service,
            "get_conversation",
            new=mocker.AsyncMock(return_value=conv),
        )
        mock_response = mocker.Mock(
            content="Summary. Modification requirements: Focus on Q4 metrics. Done."
        )
        mock_llm = mocker.Mock()
        mock_llm.chat = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "services.conversation_service.get_llm_service",
            return_value=mock_llm,
        )

        await service.generate_and_save_report(
            session_id=session_id,
            user_id=user_id,
            db=mock_db,
            requirements="Focus on Q4 metrics",
        )

        assert "Modification requirements: Focus on Q4 metrics" in conv.report
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_not_found_when_session_missing(self, mocker):
        """When no conversation exists for session_id, NotFoundError is raised."""
        mock_copilot_version = mocker.Mock()
        mocker.patch(
            "services.conversation_service.get_copilot_version",
            return_value=mock_copilot_version,
        )
        service = ConversationService()
        mock_db = mocker.AsyncMock()
        user_id = uuid4()
        session_id = "nonexistent-session"

        mocker.patch.object(
            service,
            "get_conversation_by_session_id",
            new=mocker.AsyncMock(side_effect=NotFoundError("Conversation", session_id)),
        )

        with pytest.raises(NotFoundError) as exc_info:
            await service.generate_and_save_report(
                session_id=session_id,
                user_id=user_id,
                db=mock_db,
            )

        assert session_id in str(exc_info.value)
        mock_db.commit.assert_not_called()
