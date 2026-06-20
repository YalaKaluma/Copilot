"""Feedback schemas for copilot response feedback."""

from uuid import UUID

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .base import CamelCaseModel


def _non_empty_stripped(v: str | None) -> str | None:
    """Return stripped string or None if empty/whitespace."""
    if v is None:
        return None
    s = v.strip()
    return s if s else None


class FeedbackCreateRequest(CamelCaseModel):
    """Request body for submitting feedback on a copilot response.

    Accepts camelCase from frontend (responseId, category, reason).
    Reason is required (non-empty after strip).
    """

    assistant_message_id: UUID = Field(
        ..., description="ID of the assistant message being rated"
    )
    category: Literal["positive", "negative"] = Field(
        ..., description="Feedback category"
    )
    reason: str = Field(
        ..., min_length=1, description="Reason (what they liked or didn't like)"
    )

    @field_validator("reason", mode="before")
    @classmethod
    def reason_stripped(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("Reason is required")
        s = (v or "").strip()
        if not s:
            raise ValueError("Reason cannot be empty")
        return s


class FeedbackUpdateRequest(CamelCaseModel):
    """Request body for updating existing feedback. At least one field required.

    When category is provided, reason is required (non-empty after strip).
    """

    category: Literal["positive", "negative"] | None = Field(
        default=None, description="Feedback category"
    )
    reason: str | None = Field(
        default=None, description="Reason (required when changing category)"
    )

    @field_validator("reason", mode="before")
    @classmethod
    def reason_stripped(cls, v: str | None) -> str | None:
        return _non_empty_stripped(v)

    @model_validator(mode="after")
    def at_least_one_field_and_reason_with_category(self) -> "FeedbackUpdateRequest":
        if self.category is None and self.reason is None:
            raise ValueError("At least one of category or reason must be provided")
        if self.category is not None and self.reason is None:
            raise ValueError("Reason is required when updating category")
        return self
