"""Application-specific constants.

Only includes constants not provided by FastAPI, Pydantic, or other libraries.
"""

from typing import Final


class WebhookEvents:
    """Clerk webhook event types we handle."""

    USER_CREATED: Final[str] = "user.created"
    USER_UPDATED: Final[str] = "user.updated"
    USER_DELETED: Final[str] = "user.deleted"


class UserRoles:
    """Application-specific user roles."""

    ADMIN: Final[str] = "admin"
    USER: Final[str] = "user"


class ResponseStatus:
    """Common response status constants."""

    OK: Final[str] = "ok"
    ERROR: Final[str] = "error"


class ErrorMessages:
    """Common error message templates."""

    INVALID_WEBHOOK_SIGNATURE: Final[str] = "Invalid webhook signature"
    MISSING_WEBHOOK_HEADERS: Final[str] = "Missing required webhook headers"
    INVALID_JSON_PAYLOAD: Final[str] = "Invalid JSON payload"
    MISSING_USER_ID: Final[str] = "Missing user ID in webhook payload"


class StreamingHeaders:
    """Headers for Server-Sent Events streaming."""

    SSE_HEADERS: Final[dict] = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # Prevents nginx/proxy buffering
    }
