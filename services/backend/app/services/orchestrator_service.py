"""Orchestrator Service

Service for managing orchestrator sessions that handle multi-stage workflows:
scoping -> planning -> execution -> done

"""

import asyncio
import json
from datetime import date, datetime
from typing import Any, AsyncGenerator, Dict, Optional
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel

from core.config import Settings, get_settings
from core.logging import get_logger
from config.versioning import get_copilot_version
from copilot_agents.orchestrator import (
    OrchestratorSession,
    get_orchestrator_session,
)
from models.copilot.orchestrators import (
    OrchestratorEventType,
    OrchestratorStages,
)
from packages.langfuse import flush as langfuse_flush, is_langfuse_enabled
from schemas.orchestrator import OrchestratorChatRequest
from services.tracing import to_trace_id
from services.llm.openai_client import AsyncOpenaiClient
from services.skai_api import SKAIApi
from services.skai_api_v2.client import SkaiApiV2Client

logger = get_logger(__name__)
SkaiService = SKAIApi | SkaiApiV2Client


class DateAwareJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles date, datetime, and Pydantic models."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        return super().default(obj)


class OrchestratorService:
    """Service to manage orchestrator sessions."""

    def __init__(self, settings: Settings):
        """Initialize the Orchestrator service."""
        self._settings = settings
        self._llm_client: Optional[AsyncOpenaiClient] = None
        self._sessions: Dict[str, OrchestratorSession] = {}

        # Initialize LLM client if configured
        if settings.openai_api_key:
            self._llm_client = AsyncOpenaiClient()
            logger.info("Orchestrator service initialized with OpenAI client")
        else:
            logger.warning("OpenAI API key not configured for orchestrator service")

    @property
    def is_configured(self) -> bool:
        """Check if the service is properly configured."""
        return self._llm_client is not None

    @staticmethod
    def _session_key(session_id: str, user_id: str) -> str:
        """Build a composite key that scopes sessions by user."""
        return f"{user_id}:{session_id}"

    def _get_or_create_session(
        self,
        session_id: str,
        user_id: str,
        request: OrchestratorChatRequest,
        skai_service: SkaiService,
    ) -> OrchestratorSession:
        """Get existing session or create a new one."""
        if self._llm_client is None:
            raise RuntimeError("Orchestrator service is not configured")
        key = self._session_key(session_id, user_id)
        skai_version = request.skai_version
        chat_history = request.messages
        filter_options = request.filter_options
        version_id = (
            skai_version
            if skai_version is not None
            else self._settings.skai_copilot_version
        )
        version_config = None
        try:
            version_config = get_copilot_version(version_id)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Error getting copilot version: {e}")
            raise

        if key not in self._sessions:
            self._sessions[key] = get_orchestrator_session(
                version_config,
                session_id,
                chat_history,
                skai_service,
                self._llm_client,
                filter_options=filter_options,
            )
            logger.info(f"Created new orchestrator session: {session_id}")
        else:
            session = self._sessions[key]
            # Recreate session when selected version changes.
            if session.version_id != version_id:
                self._sessions[key] = get_orchestrator_session(
                    version_config,
                    session_id,
                    chat_history,
                    skai_service,
                    self._llm_client,
                    filter_options=filter_options,
                )
                logger.info(
                    f"Recreated orchestrator session with new version: session_id={session_id}, version={version_id}"
                )
            else:
                session.user_selected_filter_options = filter_options
                # if continuing answering previous question, retain old chat history
                if session.waiting_for_info:
                    current_user_message = next(
                        chat_item
                        for chat_item in reversed(chat_history)
                        if chat_item.role == "user"
                    )
                    session.chat_history.append(current_user_message)
                else:

                    session.chat_history = chat_history
                logger.debug(f"Updated existing orchestrator session: {session_id}")

        return self._sessions[key]

    async def invoke(
        self,
        request: OrchestratorChatRequest,
        session_id: str,
        assistant_message_id: UUID,
        user_id: str,
        skai_service: SkaiService,
        user_email_id: str | None = None,
        stream: bool = True,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Invoke the orchestrator with messages.

        Args:
            messages: List of message dicts with 'role' and 'content'
            session_id: Session ID for conversation persistence
            user_id: Authenticated user ID (used to scope sessions)
            user_email_id: Optional user email ID for trace
            stream: Whether to stream the response
            skai_service: Required SKAI API service instance
            skai_version: Optional copilot version id; when provided, use instead of backend default
            filter_options: Optional user-selected filter options for the session
            **kwargs: Additional parameters
        """
        if stream:
            async for chunk in self._invoke_stream(
                request=request,
                session_id=session_id,
                assistant_message_id=assistant_message_id,
                user_id=user_id,
                skai_service=skai_service,
                user_email_id=user_email_id,
                **kwargs,
            ):
                yield chunk
        else:
            result = await self._invoke_text(
                request=request,
                session_id=session_id,
                assistant_message_id=assistant_message_id,
                user_id=user_id,
                skai_service=skai_service,
                user_email_id=user_email_id,
                **kwargs,
            )
            yield result

    async def _invoke_stream(
        self,
        request: OrchestratorChatRequest,
        session_id: str,
        assistant_message_id: UUID,
        user_id: str,
        skai_service: SkaiService,
        user_email_id: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Invoke orchestrator with streaming."""
        try:
            # Get or create session
            session = self._get_or_create_session(
                session_id,
                user_id,
                request,
                skai_service,
            )
            session.stream_final_answer = True

            # Execute the orchestrator workflow - now yields OrchestratorEvent objects
            waiting_for_user_info = False
            waiting_stage: Optional[str] = None
            last_stage = None

            trace_id = to_trace_id(assistant_message_id)
            async for event in session.execute(
                trace_id=trace_id, user_email_id=user_email_id
            ):
                # Single completion event: only the service's "done" event signals completion.
                # Skip forwarding the agent's stage_complete (stage=done) so the frontend
                # receives exactly one completion signal.
                if (
                    event.event_type == OrchestratorEventType.stage_complete
                    and event.stage == OrchestratorStages.done
                ):
                    continue

                # Convert to SSE dict format
                sse_data = event.to_sse_dict()
                # Use custom encoder as safety net for any date objects that slip through
                yield f"data: {json.dumps(sse_data, cls=DateAwareJSONEncoder)}\n\n"

                # Track if we're waiting for user info
                if event.event_type == OrchestratorEventType.request_info:
                    waiting_for_user_info = True
                    waiting_stage = event.stage.value if event.stage else None

                # Send stage_change event when stage changes
                if event.stage != last_stage:
                    last_stage = event.stage
                    stage_event = {
                        "type": "stage_change",
                        "stage": event.stage.value,
                    }
                    yield f"data: {json.dumps(stage_event)}\n\n"

            # Send completion event - different if waiting for user info
            if waiting_for_user_info:
                # Signal that we're waiting for more info but stream is done
                waiting_event = {
                    "type": "waiting_for_info",
                    "stage": waiting_stage
                    or (last_stage.value if last_stage else "scoping"),
                    "content": "Please provide the requested information to continue.",
                }
                waiting_event["message_id"] = str(assistant_message_id)
                yield f"data: {json.dumps(waiting_event)}\n\n"
            else:
                session_complete = session.is_complete
                done_event = {
                    "type": "done",
                    "stage": "done",
                    "content": "Orchestrator session completed",
                    "completed": session_complete,
                }
                if session.final_answer:
                    done_event["final_answer"] = session.final_answer

                # Include done-stage metadata from agent (confidence, assumptions_and_risks)
                done_meta: Dict[str, Any] = {}
                conf = getattr(session, "_done_confidence", None)
                if isinstance(conf, str):
                    done_meta["confidence"] = conf
                ar = getattr(session, "_done_assumptions_and_risks", None)
                if isinstance(ar, str):
                    done_meta["assumptions_and_risks"] = ar
                if done_meta:
                    done_event["metadata"] = done_meta

                done_event["message_id"] = str(assistant_message_id)
                yield f"data: {json.dumps(done_event)}\n\n"

                # Run online evals in background when session completed and Langfuse enabled
                if session_complete and is_langfuse_enabled():

                    def _on_online_evals_done(task: asyncio.Task[None]) -> None:
                        try:
                            task.result()
                            langfuse_flush()
                        except Exception as e:
                            logger.warning(
                                "Online evaluation failed (non-blocking): %s",
                                e,
                                exc_info=True,
                            )

                    task = asyncio.create_task(session.run_online_evals(trace_id))
                    task.add_done_callback(_on_online_evals_done)

        except Exception as e:
            logger.error(f"Orchestrator streaming error: {str(e)}")
            error_event = {"type": "error", "error": str(e)}
            yield f"data: {json.dumps(error_event)}\n\n"

    async def _invoke_text(
        self,
        request: OrchestratorChatRequest,
        session_id: str,
        assistant_message_id: UUID,
        user_id: str,
        skai_service: SkaiService,
        user_email_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Invoke orchestrator without streaming."""
        try:
            # Get or create session
            session = self._get_or_create_session(
                session_id,
                user_id,
                request,
                skai_service,
            )
            session.stream_final_answer = False

            # Execute and collect all output (skip transient events)
            result_parts = []

            trace_id = to_trace_id(assistant_message_id)
            async for event in session.execute(
                trace_id=trace_id, user_email_id=user_email_id
            ):
                # Skip transient events in non-streaming mode
                if event.transient:
                    continue
                # Format event as readable text
                prefix = f"[{event.stage.value}] " if event.stage else ""
                if event.step_number is not None and event.total_steps:
                    prefix += f"({event.step_number}/{event.total_steps}) "
                result_parts.append(f"{prefix}{event.content}")

            # Run online evals in background when session completed and Langfuse enabled
            if session.is_complete and is_langfuse_enabled():

                def _on_online_evals_done(task: asyncio.Task[None]) -> None:
                    try:
                        task.result()
                        langfuse_flush()
                    except Exception as e:
                        logger.warning(
                            "Online evaluation failed (non-blocking): %s",
                            e,
                            exc_info=True,
                        )

                task = asyncio.create_task(session.run_online_evals(trace_id))
                task.add_done_callback(_on_online_evals_done)

            return "\n".join(result_parts) if result_parts else "Orchestrator completed"

        except Exception as e:
            error_msg = f"Error invoking orchestrator: {str(e)}"
            logger.error(error_msg)
            return error_msg

    async def send_user_reply(
        self, session_id: str, reply: str, *, user_id: str, trace: str
    ) -> bool:
        """Send a user reply to a waiting orchestrator session.

        Used when the orchestrator requests more information during scoping.

        Args:
            session_id: The session ID
            reply: The user's reply text
            user_id: Authenticated user ID (used to scope sessions)
            trace_id: Trace ID for the new message
        Returns:
            True if reply was sent successfully, False if no pending request
        """
        key = self._session_key(session_id, user_id)
        if key not in self._sessions:
            logger.warning(f"No session found for ID: {session_id}")
            return False

        session = self._sessions[key]

        if session._pending_user_reply is not None:
            session._pending_user_reply.set_result(reply)
            logger.info(f"User reply sent to session: {session_id}")
            return True
        else:
            logger.warning(f"No pending reply request for session: {session_id}")
            return False

    def clear_session(self, session_id: str, *, user_id: str) -> bool:
        """Clear a session from memory.

        Args:
            session_id: The session ID to clear
            user_id: Authenticated user ID (used to scope sessions)

        Returns:
            True if session was cleared, False if not found
        """
        key = self._session_key(session_id, user_id)
        if key in self._sessions:
            del self._sessions[key]
            logger.info(f"Cleared orchestrator session: {session_id}")
            return True
        return False


# Singleton instance
_orchestrator_service: Optional[OrchestratorService] = None


def get_orchestrator_service(
    settings: Settings = Depends(get_settings),
) -> OrchestratorService:
    """Get Orchestrator service instance with dependency injection.

    Args:
        settings: Application settings injected by FastAPI

    Returns:
        OrchestratorService instance
    """
    global _orchestrator_service
    if _orchestrator_service is None:
        _orchestrator_service = OrchestratorService(settings)
    return _orchestrator_service
