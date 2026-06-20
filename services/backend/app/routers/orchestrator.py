"""Orchestrator endpoints for multi-stage workflow management."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from packages.langfuse import flush as langfuse_flush

from core.dependencies import (
    AuthTokenDep,
    DatabaseDep,
    SkaiAuthServiceDep,
    get_skai_api_for_user,
    get_skai_api_v2_for_user,
)
from core.config import Settings, get_settings
from core.logging import get_logger
from core.constants import StreamingHeaders
from schemas.orchestrator import (
    OrchestratorChatRequest,
    OrchestratorCompletionResponse,
    OrchestratorVersionResponse,
)
from config.versioning import get_copilot_version, list_base_version_ids
from services.orchestrator_service import OrchestratorService, get_orchestrator_service
from utils import check_service_configured
from typing import Annotated

from services.feedback_service import FeedbackService, get_feedback_service
from services.skai_api import SKAIApi
from services.skai_api_v2.client import SkaiApiV2Client

logger = get_logger(__name__)

router = APIRouter(tags=["Orchestrator"])

# Dependency types
OrchestratorServiceDep = Annotated[
    OrchestratorService, Depends(get_orchestrator_service)
]
FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _resolved_session_id(session_id: str | None) -> str:
    """Session ID for this request (from request or new UUID)."""
    return session_id or str(uuid4())


def _resolved_version_id(
    request: OrchestratorChatRequest,
    settings: Settings,
) -> str:
    return request.skai_version or settings.skai_copilot_version


def _requires_skai_v2(version_id: str) -> bool:
    version_config = get_copilot_version(version_id)
    return (
        version_config.config.orchestrator_version == "single_agent_promo_orchestrator"
    )


@router.get(
    "/versions",
    response_model=OrchestratorVersionResponse,
    summary="List Copilot Versions",
)
async def list_versions(_: AuthTokenDep) -> OrchestratorVersionResponse:
    """
    Return available copilot version ids (for version selector in dev/staging).
    In production the UI should disable the selector and use backend default.
    """
    versions = list_base_version_ids()
    return OrchestratorVersionResponse(versions=versions)


@router.post(
    "/chat",
    response_model=OrchestratorCompletionResponse,
    summary="Orchestrator Chat",
)
async def orchestrator_chat(
    request: OrchestratorChatRequest,
    service: OrchestratorServiceDep,
    auth: AuthTokenDep,
    db: DatabaseDep,
    skai_auth_service: SkaiAuthServiceDep,
    settings: SettingsDep,
) -> OrchestratorCompletionResponse | StreamingResponse:
    """
    Chat with the orchestrator for multi-stage workflow execution.

    The orchestrator handles:
    - **Scoping**: Gathering requirements, may request additional information
    - **Planning**: Creating a structured execution plan
    - **Execution**: Running tools and coordinating handoffs
    - **Done**: Completing the workflow

    Supports:
    - Streaming responses via SSE (recommended)
    - Non-streaming responses for simple cases

    Returns response_id (and trace_id when Langfuse is enabled) for feedback.
    """
    try:
        check_service_configured(
            service_name="Orchestrator", is_configured=service.is_configured
        )

        user = auth["user"]
        user_id = str(user.id)
        resolved_session_id = _resolved_session_id(request.session_id)
        version_id = _resolved_version_id(request, settings)

        skai_creds = await skai_auth_service.get_credentials(user_id, db)

        user_email_id = skai_creds.skai_username if skai_creds else None
        skai_service: SKAIApi | SkaiApiV2Client
        if _requires_skai_v2(version_id):
            skai_service = await get_skai_api_v2_for_user(auth, db, skai_auth_service)
        else:
            skai_service = await get_skai_api_for_user(auth, db, skai_auth_service)

        # Backend-generated id for the new assistant message (trace + feedback).
        # Single source of truth: same id used for Langfuse trace and for message when frontend saves.
        assistant_message_id = uuid4()

        logger.info(
            f"Orchestrator chat request received for session: assistant_message_id={assistant_message_id}"
        )
        if request.stream:

            async def generate():
                async for chunk in service.invoke(
                    request=request,
                    session_id=resolved_session_id,
                    assistant_message_id=assistant_message_id,
                    user_id=user_id,
                    user_email_id=user_email_id,
                    stream=True,
                    skai_service=skai_service,
                ):
                    yield chunk

            return StreamingResponse(
                generate(),
                media_type="text/event-stream",
                headers=StreamingHeaders.SSE_HEADERS,
            )
        else:
            result = ""
            async for chunk in service.invoke(
                request=request,
                session_id=resolved_session_id,
                assistant_message_id=assistant_message_id,
                user_id=user_id,
                user_email_id=user_email_id,
                stream=False,
                skai_service=skai_service,
            ):
                result = chunk  # Non-streaming returns single result

            return OrchestratorCompletionResponse(
                content=result,
                stage="done",
                session_id=resolved_session_id,
                response_id=assistant_message_id,
            )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Orchestrator chat error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    finally:
        langfuse_flush()


# TODO: This is not used anymore


# @router.post(
#     "/reply",
#     summary="Send User Reply to Orchestrator",
# )
# async def send_reply(
#     session_id: str,
#     reply: str,
#     service: OrchestratorServiceDep,
#     auth: AuthTokenDep,
# ) -> dict:
#     """
#     Send a user reply to an orchestrator session waiting for input.

#     This is used when the orchestrator requests more information during
#     the scoping phase.

#     Args:
#         session_id: The session ID
#         reply: The user's reply text

#     Returns:
#         Success status
#     """
#     try:
#         check_service_configured(
#             service_name="Orchestrator", is_configured=service.is_configured
#         )

#         user = auth["user"]
#         user_id = str(user.id)
#         success = await service.send_user_reply(session_id, reply, user_id=user_id)

#         if not success:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"No pending reply request for session: {session_id}",
#             )

#         return {"status": "success", "message": "Reply sent"}

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.error(f"Send reply error: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
#         )
#     finally:
#         langfuse_flush()


@router.delete(
    "/session/{session_id}",
    summary="Clear Orchestrator Session",
)
async def clear_session(
    session_id: str,
    service: OrchestratorServiceDep,
    auth: AuthTokenDep,
) -> dict:
    """
    Clear an orchestrator session from memory.

    Args:
        session_id: The session ID to clear

    Returns:
        Success status
    """
    try:
        check_service_configured(
            service_name="Orchestrator", is_configured=service.is_configured
        )

        user = auth["user"]
        user_id = str(user.id)
        success = service.clear_session(session_id, user_id=user_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session not found: {session_id}",
            )

        return {"status": "success", "message": "Session cleared"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Clear session error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    finally:
        langfuse_flush()
