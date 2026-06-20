from uuid import UUID

from fastapi import APIRouter, status
from core.logging import get_logger
from core.dependencies import AuthTokenDep, DatabaseDep
from routers.orchestrator import FeedbackServiceDep
from schemas.feedback import FeedbackCreateRequest, FeedbackUpdateRequest

logger = get_logger(__name__)

router = APIRouter(tags=["Orchestrator"])


@router.post(
    "/feedback",
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback for a copilot response",
)
async def submit_feedback(
    body: FeedbackCreateRequest,
    auth: AuthTokenDep,
    feedback_service: FeedbackServiceDep,
    db: DatabaseDep,
) -> None:
    """
    Submit user feedback (positive or negative) for a copilot response.

    Requires the assistant_message_id returned from the chat endpoint (streaming or non-streaming).
    One feedback per response; duplicate submissions return 409.
    When Langfuse is enabled, the feedback is attached as a score to the trace.
    """
    user = auth["user"]
    await feedback_service.submit_feedback(
        assistant_message_id=body.assistant_message_id,
        user_id=user.id,
        category=body.category,
        reason=body.reason,
        db=db,
    )


@router.delete(
    "/feedback/{assistant_message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove feedback for a copilot response",
)
async def delete_feedback(
    assistant_message_id: UUID,
    auth: AuthTokenDep,
    feedback_service: FeedbackServiceDep,
    db: DatabaseDep,
) -> None:
    """
    Remove feedback for a copilot response. User must own the conversation.
    Returns 404 if message not found or no feedback exists for that message.
    """
    user = auth["user"]
    await feedback_service.delete_feedback(
        assistant_message_id=assistant_message_id,
        user_id=user.id,
        db=db,
    )


@router.patch(
    "/feedback/{assistant_message_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Update feedback for a copilot response",
)
async def update_feedback(
    assistant_message_id: UUID,
    body: FeedbackUpdateRequest,
    auth: AuthTokenDep,
    feedback_service: FeedbackServiceDep,
    db: DatabaseDep,
) -> None:
    """
    Update existing feedback (category and/or reason). User must own the conversation.
    Returns 404 if message or feedback not found.
    """
    user = auth["user"]
    await feedback_service.update_feedback(
        assistant_message_id=assistant_message_id,
        user_id=user.id,
        category=body.category,
        reason=body.reason,
        db=db,
    )
