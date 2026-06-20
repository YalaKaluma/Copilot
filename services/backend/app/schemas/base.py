"""Base schemas for common patterns."""

from datetime import datetime
from uuid import UUID

from humps import camelize
from pydantic import BaseModel, ConfigDict, Field, field_serializer


def to_camel(snake_str: str) -> str:
    """Convert snake_case to camelCase."""
    return camelize(snake_str)


class CamelCaseModel(BaseModel):
    """Base model that converts snake_case fields to camelCase in JSON."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,  # Accept both snake_case and camelCase input
        from_attributes=True,  # Allow creation from ORM models
        use_enum_values=True,
    )

    @field_serializer("*", mode="wrap")
    def serialize_datetime_and_uuid(self, value, handler):
        """Custom serializer for datetime and UUID fields."""
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, UUID):
            return str(value)
        return handler(value)


class BaseResponse(CamelCaseModel):
    """Base response model with common fields."""

    success: bool = Field(
        default=True, description="Whether the request was successful"
    )
    message: str | None = Field(default=None, description="Optional message")


class TimestampedResponse(CamelCaseModel):
    """Base model with timestamp fields."""

    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
