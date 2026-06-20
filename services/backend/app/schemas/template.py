"""Template schemas for instruction templates."""

from uuid import UUID

from pydantic import Field, model_validator

from .base import CamelCaseModel, TimestampedResponse


class TemplateListItem(TimestampedResponse):
    """Summary item for template list."""

    id: UUID
    name: str
    description: str | None = None
    is_default: bool = False


class TemplateDetail(TimestampedResponse):
    """Full template detail with content."""

    id: UUID
    name: str
    description: str | None = None
    content: str
    is_default: bool = False


class CreateTemplateRequest(CamelCaseModel):
    """Request to create a new template."""

    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=255)
    content: str
    is_default: bool = False


class UpdateTemplateRequest(CamelCaseModel):
    """Request to update an existing template."""

    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=255)
    content: str | None = None
    is_default: bool | None = None

    @model_validator(mode="after")
    def validate_nullable_patch_fields(self) -> "UpdateTemplateRequest":
        """Reject explicit null for non-nullable persisted fields."""
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name cannot be null")
        if "content" in self.model_fields_set and self.content is None:
            raise ValueError("content cannot be null")
        return self
