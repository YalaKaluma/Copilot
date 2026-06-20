"""Centralized exception classes for the application.

Usage:
    from core.exceptions import NotFoundError, ValidationError, ServiceError

    # In services - raise domain exceptions
    if not resource:
        raise NotFoundError("User", user_id)

    if not valid:
        raise ValidationError("Email format is invalid")

    # In routers - exceptions are automatically handled by global handlers
    # No try/except needed for these exception types
"""

from typing import Any
from uuid import UUID


class AppError(Exception):
    """Base exception for all application errors.

    All custom exceptions inherit from this class.
    Global exception handlers catch these and convert to appropriate HTTP responses.
    """

    def __init__(
        self,
        message: str,
        detail: Any | None = None,
        status_code: int = 500,
    ):
        self.message = message
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    """Resource not found.

    Raises HTTP 404 Not Found.

    Usage:
        raise NotFoundError("User", user_id)
        raise NotFoundError("File", file_id, "File may have been deleted")
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: (str | UUID) | None = None,
        detail: str | None = None,
    ):
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} with ID {resource_id} not found"
        super().__init__(message=message, detail=detail, status_code=404)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ValidationError(AppError):
    """Request validation failed.

    Raises HTTP 400 Bad Request.
    Use for domain validation that Pydantic can't catch.

    Usage:
        raise ValidationError("Email already registered")
        raise ValidationError("Invalid date range", {"start": start, "end": end})
    """

    def __init__(self, message: str, detail: Any | None = None):
        super().__init__(message=message, detail=detail, status_code=400)


class ConflictError(AppError):
    """Resource conflict (duplicate, already exists).

    Raises HTTP 409 Conflict.

    Usage:
        raise ConflictError("User with this email already exists")
        raise ConflictError("Bucket name already taken", {"name": bucket_name})
    """

    def __init__(self, message: str, detail: Any | None = None):
        super().__init__(message=message, detail=detail, status_code=409)


class ForbiddenError(AppError):
    """Action not allowed for current user.

    Raises HTTP 403 Forbidden.
    Use when user is authenticated but lacks permission.

    Usage:
        raise ForbiddenError("Cannot delete another user's bucket")
        raise ForbiddenError("Admin access required")
    """

    def __init__(self, message: str = "Access denied", detail: Any | None = None):
        super().__init__(message=message, detail=detail, status_code=403)


class UnauthorizedError(AppError):
    """Authentication required or failed.

    Raises HTTP 401 Unauthorized.

    Usage:
        raise UnauthorizedError("Invalid token")
        raise UnauthorizedError("Token expired")
    """

    def __init__(
        self, message: str = "Authentication required", detail: Any | None = None
    ):
        super().__init__(message=message, detail=detail, status_code=401)


class ServiceError(AppError):
    """External service or internal operation failed.

    Raises HTTP 500 Internal Server Error by default.
    Can be configured for 502 Bad Gateway or 503 Service Unavailable.

    Usage:
        raise ServiceError("Database connection failed")
        raise ServiceError("Storage service unavailable", status_code=503)
        raise ServiceError("LLM API error", detail={"provider": "openai"})
    """

    def __init__(
        self,
        message: str,
        detail: Any | None = None,
        status_code: int = 500,
    ):
        super().__init__(message=message, detail=detail, status_code=status_code)


class ServiceUnavailableError(AppError):
    """Service is not configured or temporarily unavailable.

    Raises HTTP 503 Service Unavailable.

    Usage:
        raise ServiceUnavailableError("LLM")
        raise ServiceUnavailableError("Storage", "Configure GCS credentials")
    """

    def __init__(self, service_name: str, detail: str | None = None):
        message = f"{service_name} service not configured"
        super().__init__(message=message, detail=detail, status_code=503)
        self.service_name = service_name


class RateLimitError(AppError):
    """Rate limit exceeded.

    Raises HTTP 429 Too Many Requests.

    Usage:
        raise RateLimitError("API rate limit exceeded", retry_after=60)
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        detail: Any | None = None,
        retry_after: int | None = None,
    ):
        super().__init__(message=message, detail=detail, status_code=429)
        self.retry_after = retry_after


class ExternalAPIError(AppError):
    """External API call failed.

    Raises HTTP 502 Bad Gateway.

    Usage:
        raise ExternalAPIError("OpenAI", "Request timeout")
        raise ExternalAPIError("Clerk", "Invalid response", {"status": 500})
    """

    def __init__(
        self,
        service_name: str,
        message: str | None = None,
        detail: Any | None = None,
    ):
        full_message = f"{service_name} API error"
        if message:
            full_message = f"{service_name}: {message}"
        super().__init__(message=full_message, detail=detail, status_code=502)
        self.service_name = service_name


class AppConfigError(AppError):
    """Application configuration error.

    Raises HTTP 500 Internal Server Error.

    Usage:
        raise AppConfigError("Prompt registry not found")
    """

    def __init__(self, message: str, detail: Any | None = None):
        super().__init__(message=message, detail=detail, status_code=500)


class ToolExecutionError(Exception):
    """Tool execution failed.

    Raises HTTP 500 Internal Server Error.

    Usage:
        raise ToolExecutionError("Tool execution failed", detail={"tool": "tool_name"})
    """

    def __init__(self, tool_name: str, error: Exception):
        super().__init__(f"Tool {tool_name} execution failed: {error}")
        self.tool_name = tool_name
