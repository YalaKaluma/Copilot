"""Conversation service for chat history persistence."""

import re
from datetime import datetime, UTC
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import NotFoundError
from core.logging import get_logger
from packages.db.models.conversation import Conversation
from packages.db.models.conversation_message import ConversationMessage
from core.config import get_settings
from config.versioning import get_copilot_version
from services.llm import LLMProvider, get_llm_service

logger = get_logger(__name__)


class ConversationService:
    """Service for managing chat conversations."""

    def __init__(self):
        settings = get_settings()
        self._copilot_version_id = settings.skai_copilot_version

    async def create_or_update_conversation(
        self,
        user_id: UUID,
        session_id: str | None,
        stage: str | None,
        plan_data: dict | None,
        execution_log: list | None,
        charts: list | None,
        messages: list[dict],
        db: AsyncSession,
        project_id: UUID | None = None,
    ) -> Conversation:
        """Create or update a conversation and merge its messages by id.

        When updating an existing conversation:
        - Existing message rows whose id is in the request are updated (content, role, metadata).
        - Message rows whose id is not in the request are deleted (feedback CASCADE-deleted).
        - Messages in the request whose id is not in the DB are inserted.

        This preserves feedback on messages that remain in the conversation.

        Returns the conversation (messages are merged by id; no message_ids returned).
        """
        session_id = session_id or str(uuid4())
        stmt = select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.user_id == user_id,
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()

        if conversation:
            # If the conversation was soft-deleted by the user, refuse to
            # update it.  Background streams may still try to persist after
            # deletion; silently return the stale row so the caller doesn't
            # crash, but don't un-delete or modify anything.
            if conversation.is_deleted:
                return conversation

            conversation.stage = stage
            conversation.plan_data = plan_data
            conversation.execution_log = execution_log
            if charts:
                conversation.charts = charts
            if project_id:
                conversation.project_id = project_id

            # Merge messages by id: update existing, delete removed, insert new
            stmt = select(ConversationMessage.id).where(
                ConversationMessage.conversation_id == conversation.id
            )
            result = await db.execute(stmt)
            existing_ids = {row[0] for row in result.all()}
            request_ids = {msg_data["id"] for msg_data in messages}
            to_delete_ids = existing_ids - request_ids
            to_insert_ids = request_ids - existing_ids

            if to_delete_ids:
                await db.execute(
                    delete(ConversationMessage).where(
                        ConversationMessage.conversation_id == conversation.id,
                        ConversationMessage.id.in_(to_delete_ids),
                    )
                )

            # Update existing messages (content, role, metadata) to preserve rows and feedback
            to_update_ids = existing_ids & request_ids
            if to_update_ids:
                stmt = select(ConversationMessage).where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.id.in_(to_update_ids),
                )
                result = await db.execute(stmt)
                existing_rows = result.scalars().all()
                msg_by_id = {msg_data["id"]: msg_data for msg_data in messages}
                for row in existing_rows:
                    data = msg_by_id.get(row.id)
                    if data:
                        row.role = data["role"]
                        row.content = data["content"]
                        row.message_metadata = data.get("metadata")

            # Insert new messages
            for msg_data in messages:
                if msg_data["id"] in to_insert_ids:
                    msg = ConversationMessage(
                        id=msg_data["id"],
                        conversation_id=conversation.id,
                        role=msg_data["role"],
                        content=msg_data["content"],
                        message_metadata=msg_data.get("metadata"),
                    )
                    db.add(msg)
        else:
            conversation = Conversation(
                user_id=user_id,
                session_id=session_id,
                stage=stage,
                plan_data=plan_data,
                execution_log=execution_log,
                charts=charts,
                project_id=project_id,
            )
            db.add(conversation)
            await db.flush()

            for msg_data in messages:
                msg = ConversationMessage(
                    id=msg_data["id"],
                    conversation_id=conversation.id,
                    role=msg_data["role"],
                    content=msg_data["content"],
                    message_metadata=msg_data.get("metadata"),
                )
                db.add(msg)

        await db.flush()

        await db.commit()
        await db.refresh(conversation)
        return conversation

    async def list_conversations(
        self,
        user_id: UUID,
        db: AsyncSession,
        project_id: UUID | None = None,
    ) -> list[dict]:
        """List conversations for a user.

        When project_id is None: only conversations with no project (unscoped).
        When project_id is set: only conversations in that project.
        """
        conditions = [
            Conversation.user_id == user_id,
            Conversation.is_deleted.is_(False),
        ]
        if project_id is not None:
            conditions.append(Conversation.project_id == project_id)
        else:
            conditions.append(Conversation.project_id.is_(None))
        stmt = (
            select(
                Conversation.id,
                Conversation.session_id,
                Conversation.title,
                Conversation.stage,
                Conversation.created_at,
                Conversation.updated_at,
                Conversation.project_id,
                Conversation.charts,
                Conversation.report,
                func.count(ConversationMessage.id).label("message_count"),
            )
            .outerjoin(ConversationMessage)
            .where(*conditions)
            .group_by(
                Conversation.id,
                Conversation.session_id,
                Conversation.title,
                Conversation.stage,
                Conversation.created_at,
                Conversation.updated_at,
                Conversation.project_id,
                Conversation.charts,
                Conversation.report,
            )
            .order_by(Conversation.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": row.id,
                "session_id": row.session_id,
                "title": row.title,
                "stage": row.stage,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "message_count": row.message_count,
                "project_id": row.project_id,
                "has_charts": bool(row.charts and len(row.charts) > 0),
                "has_report": bool(row.report and (row.report or "").strip() != ""),
            }
            for row in rows
        ]

    async def get_conversation(
        self, conversation_id: UUID, user_id: UUID, db: AsyncSession
    ) -> Conversation:
        """Get a conversation with all its messages and feedback."""
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.messages).selectinload(
                    ConversationMessage.feedback
                )
            )
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
                Conversation.is_deleted.is_(False),
            )
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise NotFoundError("Conversation", conversation_id)
        return conversation

    async def get_conversation_by_session_id(
        self, session_id: str, user_id: UUID, db: AsyncSession
    ) -> Conversation:
        """Get a conversation by session id with all its messages and feedback."""
        stmt = (
            select(Conversation)
            .options(
                selectinload(Conversation.messages).selectinload(
                    ConversationMessage.feedback
                )
            )
            .where(
                Conversation.session_id == session_id,
                Conversation.user_id == user_id,
                Conversation.is_deleted.is_(False),
            )
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise NotFoundError("Conversation", session_id)
        return conversation

    async def delete_conversation(
        self, conversation_id: UUID, user_id: UUID, db: AsyncSession
    ) -> bool:
        """Soft delete a conversation."""
        stmt = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
            Conversation.is_deleted.is_(False),
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise NotFoundError("Conversation", conversation_id)

        conversation.is_deleted = True
        conversation.deleted_at = datetime.now(UTC)
        await db.commit()
        return True

    async def generate_title(
        self, conversation_id: UUID, user_id: UUID, db: AsyncSession
    ) -> str:
        """Generate a title for a conversation using LLM."""
        conversation = await self.get_conversation(conversation_id, user_id, db)

        # Build a condensed version of messages for title generation
        condensed: list[dict] = []
        user_messages = [m for m in conversation.messages if m.role == "user"]
        assistant_messages = [m for m in conversation.messages if m.role == "assistant"]

        if user_messages:
            condensed.append(
                {"role": "user", "content": user_messages[0].content[:500]}
            )
        if assistant_messages:
            condensed.append(
                {"role": "assistant", "content": assistant_messages[-1].content[:500]}
            )

        if not condensed:
            title = "Untitled chat"
        else:
            try:
                llm = get_llm_service()
                title_prompt = [
                    {
                        "role": "system",
                        "content": (
                            "Output a short title (max 8 words) for the conversation below. "
                            "Output ONLY the plain title text. No quotes, no markdown, "
                            "no preamble, no explanation."
                        ),
                    },
                    *condensed,
                ]
                response = await llm.chat(
                    messages=title_prompt,
                    model="gpt-4.1-nano",
                    provider=LLMProvider.OPENAI,
                    system_prompt_key="__none__",
                    temperature=0.3,
                    max_tokens=30,
                )
                # Strip any conversational fluff the LLM may have added
                raw = response.content.strip()
                # Remove markdown bold markers
                raw = raw.replace("**", "")
                # Remove wrapping quotes
                raw = raw.strip('"').strip("'")
                # Remove common preamble patterns
                raw = re.sub(
                    r"^(?:(?:Sure|Here(?:'s| is))[^:]*:\s*)",
                    "",
                    raw,
                    flags=re.IGNORECASE,
                )
                title = raw.strip()[:100]
                if not title:
                    title = "Untitled chat"
            except Exception as e:
                logger.warning(f"Failed to generate title: {e}")
                title = "Untitled chat"

        conversation.title = title
        await db.commit()
        return title

    async def generate_and_save_report(
        self,
        session_id: str,
        user_id: UUID,
        db: AsyncSession,
        requirements: str | None = None,
    ) -> Conversation:
        """Load conversation by session_id, generate a placeholder report, persist and return it."""
        conversation = await self.get_conversation_by_session_id(
            session_id, user_id, db
        )

        all_messages = []

        for message in conversation.messages:
            all_messages.append(
                {
                    "role": message.role,
                    "content": message.content,
                }
            )

        plan = conversation.plan_data or {}
        execution_log = conversation.execution_log or []
        copilot_version = get_copilot_version(self._copilot_version_id)
        report_generator_prompt = copilot_version.get_prompt(
            "report_generation",
            context={
                "transcript": all_messages,
                "plan_data": plan,
                "execution_logs": execution_log,
                "report_requirements": requirements or "No requirements provided.",
            },
        )

        llm = get_llm_service()
        response = await llm.chat(
            messages=[{"role": "user", "content": report_generator_prompt}],
            model="gpt-4.1-nano",
            provider=LLMProvider.OPENAI,
            system_prompt_key="__none__",
            temperature=0.1,
            max_tokens=4096,
        )

        response_text = response.content
        conversation.report = response_text
        await db.commit()
        # Re-fetch with eager loading so to_conversation_detail does not trigger
        # lazy loads (async SQLAlchemy forbids lazy load -> MissingGreenlet).
        return await self.get_conversation(conversation.id, user_id, db)


def get_conversation_service() -> ConversationService:
    """Create conversation service instance."""
    return ConversationService()
