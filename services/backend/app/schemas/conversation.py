"""Conversation schemas for chat history."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from .base import CamelCaseModel, TimestampedResponse


class ChartDataPointOut(CamelCaseModel):
    """Single data point for a chart."""

    label: str
    value: float


class ChartItemOut(CamelCaseModel):
    """Chart item for persistence and API (id, title, chartType, data)."""

    id: str
    title: str
    chart_type: Literal["bar", "line", "pie"] = "bar"
    data: list[ChartDataPointOut] = []


class MessageFeedbackOut(CamelCaseModel):
    """Feedback on a single message (returned with conversation detail)."""

    category: Literal["positive", "negative"]
    reason: str | None = None


class ConversationMessageOut(TimestampedResponse):
    """Response model for a single conversation message."""

    id: UUID
    role: str
    content: str
    message_metadata: dict | None = None
    feedback: MessageFeedbackOut | None = None


class ConversationListItem(TimestampedResponse):
    """Summary item for conversation list."""

    id: UUID
    session_id: str
    title: str | None = None
    stage: str | None = None
    message_count: int = 0
    project_id: UUID | None = None
    has_charts: bool = False
    has_report: bool = False


class ConversationDetail(TimestampedResponse):
    """Full conversation detail with messages."""

    id: UUID
    session_id: str
    title: str | None = None
    stage: str | None = None
    plan_data: dict | None = None
    execution_log: list | None = None
    charts: list[ChartItemOut] | None = None
    report: str | None = None
    messages: list[ConversationMessageOut] = []
    project_id: UUID | None = None


class SaveMessageInput(CamelCaseModel):
    """Input schema for a single message in the save request."""

    id: UUID = Field(
        ..., description="Message ID; use same ID for feedback on this response"
    )
    role: str
    content: str
    metadata: dict | None = None


class SaveConversationRequest(CamelCaseModel):
    """Request to create/update a conversation with messages."""

    session_id: str | None = None
    stage: str | None = None
    plan_data: dict | None = None
    execution_log: list | None = None
    charts: list[ChartItemOut] | None = None
    messages: list[SaveMessageInput] = []
    project_id: UUID | None = None


class ConversationResponse(CamelCaseModel):
    """Response after saving a conversation."""

    id: UUID
    session_id: str
    title: str | None = None
    stage: str | None = None


class GenerateTitleResponse(CamelCaseModel):
    """Response after generating a title."""

    id: UUID
    title: str


class GenerateReportRequest(CamelCaseModel):
    """Optional body for generate-report (e.g. modification requirements)."""

    requirements: str | None = None
