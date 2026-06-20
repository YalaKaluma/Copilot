"""Project schemas for API."""

from uuid import UUID

from pydantic import Field

from .base import CamelCaseModel, TimestampedResponse


class ProjectCreateRequest(CamelCaseModel):
    """Request to create a project."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ProjectUpdateRequest(CamelCaseModel):
    """Request to update a project."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ProjectListItem(TimestampedResponse):
    """Summary item for project list."""

    id: UUID
    name: str
    description: str | None = None


class ProjectResponse(ProjectListItem):
    """Full project response (same as list item for now)."""

    pass
