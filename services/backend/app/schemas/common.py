"""Common schemas used across multiple domains."""

from typing import Any

from pydantic import Field

from .base import BaseResponse


class ErrorResponse(BaseResponse):
    """Standard error response for all API endpoints."""

    success: bool = Field(default=False, description="Always false for errors")
    error: str = Field(..., description="Human-readable error message")
    detail: Any | None = Field(default=None, description="Additional error details")
    status_code: int | None = Field(default=None, description="HTTP status code")


class SuccessResponse(BaseResponse):
    """Generic success response wrapper."""

    success: bool = Field(default=True, description="Always true for success")
    data: Any | None = Field(default=None, description="Response data")


class PaginatedResponse(BaseResponse):
    """Paginated list response."""

    items: list[Any] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
