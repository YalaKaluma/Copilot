"""User-related schemas."""

from uuid import UUID

from pydantic import Field, field_validator

from .base import CamelCaseModel, TimestampedResponse


class UserResponse(TimestampedResponse):
    """User response model."""

    id: UUID = Field(..., description="User's unique ID")
    clerk_user_id: str = Field(..., description="Clerk authentication system ID")
    preferred_name: str | None = Field(
        None, description="User's preferred display name"
    )
    initials: str | None = Field(
        None, description="User initials (max 2 characters)", max_length=2
    )
    role: str = Field(
        ..., description="User role for access control", examples=["user", "admin"]
    )

    @classmethod
    def from_orm(cls, user) -> "UserResponse":
        """Create from ORM model."""
        return cls(
            id=user.id,
            clerk_user_id=user.clerk_user_id,
            preferred_name=user.preferred_name,
            initials=user.initials,
            role=user.role or "user",
            created_at=user.created_at,
            updated_at=user.updated_at,
        )


class UserCreateRequest(CamelCaseModel):
    """User creation request (typically from webhooks)."""

    clerk_user_id: str = Field(..., description="Clerk user ID", min_length=1)
    preferred_name: str | None = Field(
        None, description="User's preferred display name", max_length=255
    )
    initials: str | None = Field(None, description="User initials", max_length=2)
    role: str | None = Field(
        "user", description="User role", examples=["user", "admin"]
    )

    @field_validator("initials")
    @classmethod
    def validate_initials(cls, v: str | None) -> str | None:
        """Ensure initials are uppercase and max 2 characters."""
        if v:
            return v.upper()[:2]
        return v


class UserUpdateRequest(CamelCaseModel):
    """User update request."""

    preferred_name: str | None = Field(
        None, description="User's preferred display name", max_length=255
    )
    initials: str | None = Field(None, description="User initials", max_length=2)
    role: str | None = Field(None, description="User role", examples=["user", "admin"])

    @field_validator("initials")
    @classmethod
    def validate_initials(cls, v: str | None) -> str | None:
        """Ensure initials are uppercase and max 2 characters."""
        if v:
            return v.upper()[:2]
        return v
