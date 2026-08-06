"""Conversations API router for chat history."""

from uuid import UUID

from fastapi import APIRouter, Body
from fastapi.responses import StreamingResponse
from io import BytesIO

from core.dependencies import AuthTokenDep, DatabaseDep, ConversationServiceDep
from core.logging import get_logger
from packages.db.models.conversation import Conversation
from schemas.conversation import (
    ChartItemOut,
    ConversationDetail,
    ConversationListItem,
    ConversationMessageOut,
    ConversationResponse,
    GenerateReportRequest,
    GenerateTitleResponse,
    MessageFeedbackOut,
    SaveConversationRequest,
)
from services.feedback_workbook import build_feedback_workbook

logger = get_logger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def to_conversation_detail(conversation: Conversation) -> ConversationDetail:
    """Map a conversation ORM row to the API detail schema."""
    charts_out = None
    if conversation.charts:
        charts_out = [ChartItemOut(**c) for c in conversation.charts]
    return ConversationDetail(
        id=conversation.id,
        session_id=conversation.session_id,
        title=conversation.title,
        stage=conversation.stage,
        plan_data=conversation.plan_data,
        execution_log=conversation.execution_log,
        charts=charts_out,
        report=conversation.report,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        project_id=conversation.project_id,
        messages=[
            ConversationMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                message_metadata=m.message_metadata,
                feedback=(
                    MessageFeedbackOut(
                        category=m.feedback.category,
                        reason=m.feedback.reason,
                    )
                    if m.feedback
                    else None
                ),
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in conversation.messages
        ],
    )


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
    project_id: UUID | None = None,
):
    """List conversations for the authenticated user, optionally filtered by project."""
    user = auth["user"]
    rows = await conversation_service.list_conversations(
        user.id, db, project_id=project_id
    )
    return [ConversationListItem(**row) for row in rows]


@router.get("/session/{session_id}", response_model=ConversationDetail)
async def get_conversation_by_session(
    session_id: str,
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
):
    """Get a conversation by session id with all messages."""
    user = auth["user"]
    conversation = await conversation_service.get_conversation_by_session_id(
        session_id, user.id, db
    )
    return to_conversation_detail(conversation)


@router.get("/session/{session_id}/feedback-workbook")
async def download_feedback_workbook(
    session_id: str,
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
):
    """Download the authenticated user's conversation as an Excel review file."""
    conversation = await conversation_service.get_conversation_by_session_id(
        session_id, auth["user"].id, db
    )
    payload = build_feedback_workbook(conversation)
    headers = {
        "Content-Disposition": (
            f'attachment; filename="growth-copilot-feedback-{session_id}.xlsx"'
        )
    }
    return StreamingResponse(
        BytesIO(payload),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers=headers,
    )


@router.post(
    "/session/{session_id}/generate-report",
    response_model=ConversationDetail,
)
async def generate_report(
    session_id: str,
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
    body: GenerateReportRequest | None = Body(None),
):
    """Generate and persist a report for the conversation identified by session_id."""
    user = auth["user"]
    requirements = body.requirements if body else None
    conversation = await conversation_service.generate_and_save_report(
        session_id, user.id, db, requirements=requirements
    )
    return to_conversation_detail(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
):
    """Get a conversation with all messages."""
    user = auth["user"]
    conversation = await conversation_service.get_conversation(
        conversation_id, user.id, db
    )
    return to_conversation_detail(conversation)


@router.post("", response_model=ConversationResponse)
async def save_conversation(
    request: SaveConversationRequest,
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
):
    """Create or update a conversation with messages."""
    user = auth["user"]
    charts_payload = (
        [c.model_dump(mode="json") for c in request.charts] if request.charts else None
    )
    conversation = await conversation_service.create_or_update_conversation(
        user_id=user.id,
        session_id=request.session_id,
        stage=request.stage,
        plan_data=request.plan_data,
        execution_log=request.execution_log,
        charts=charts_payload,
        messages=[
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "metadata": m.metadata,
            }
            for m in request.messages
        ],
        db=db,
        project_id=request.project_id,
    )
    return ConversationResponse(
        id=conversation.id,
        session_id=conversation.session_id,
        title=conversation.title,
        stage=conversation.stage,
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
):
    """Soft delete a conversation."""
    user = auth["user"]
    await conversation_service.delete_conversation(conversation_id, user.id, db)
    return {"success": True}


@router.post("/{conversation_id}/generate-title", response_model=GenerateTitleResponse)
async def generate_title(
    conversation_id: UUID,
    auth: AuthTokenDep,
    conversation_service: ConversationServiceDep,
    db: DatabaseDep,
):
    """Generate a title for a conversation using LLM."""
    user = auth["user"]
    title = await conversation_service.generate_title(conversation_id, user.id, db)
    return GenerateTitleResponse(id=conversation_id, title=title)
