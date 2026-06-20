"""Orchestrator-related schemas."""

from uuid import UUID
from typing import Literal

from pydantic import BaseModel, Field

from models.skai_api.autogen import FilterOptions
from models.copilot.base import ChatEvent


class OrchestratorVersionResponse(BaseModel):
    """Orchestrator version response."""

    versions: list[str] = Field(..., description="Available copilot version ids")


class OrchestratorChatRequest(BaseModel):
    """Orchestrator chat request."""

    messages: list[ChatEvent] = Field(..., description="Conversation messages")
    stream: bool = Field(default=True, description="Stream the response")
    request_id: str | None = Field(
        default=None,
        description="Optional request ID (UUID) for tracing; generated if omitted",
    )
    session_id: str | None = Field(
        default=None, description="Session ID for conversation persistence"
    )
    skai_version: str | None = Field(
        default=None,
        description="Optional copilot version id (e.g. v1); when provided, orchestrator uses this instead of backend default",
    )
    filter_options: FilterOptions | None = Field(
        default=None,
        description="User-selected filter options applied to new queries. Must conform to FilterOptions (camelCase keys in JSON).",
    )


class OrchestratorEvent(BaseModel):
    """Event streamed from the orchestrator."""

    type: Literal[
        "stage_change", "content", "plan", "request_info", "handoff", "done", "error"
    ]
    stage: str | None = Field(default=None, description="Current orchestrator stage")
    content: str | None = Field(default=None, description="Text content")
    plan: dict | None = Field(default=None, description="Generated plan")
    request: str | None = Field(
        default=None, description="Information request from orchestrator"
    )
    actions: list[str] | None = Field(
        default=None, description="Clickable action options for request_info"
    )
    allow_other: bool | None = Field(
        default=None, description="Whether to allow free-text response"
    )
    error: str | None = Field(default=None, description="Error message")


class OrchestratorCompletionResponse(BaseModel):
    """Orchestrator completion response (non-streaming)."""

    content: str = Field(..., description="Generated content")
    stage: str = Field(..., description="Final stage reached")
    session_id: str = Field(..., description="Session ID for conversation persistence")
    response_id: UUID = Field(
        ..., description="Unique ID for this response (use for feedback)"
    )
    plan: dict | None = Field(default=None, description="Generated plan if any")
    usage: dict | None = Field(default=None, description="Token usage stats")
