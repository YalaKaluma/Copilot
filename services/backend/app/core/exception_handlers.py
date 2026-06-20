"""Global exception handlers for FastAPI.

These handlers catch exceptions and convert them to consistent JSON responses.
Register with app using setup_exception_handlers(app).

Usage in main.py:
    from core.exception_handlers import setup_exception_handlers

    app = FastAPI(...)
    setup_exception_handlers(app)
"""

import json
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.exceptions import AppError, RateLimitError
from core.logging import get_logger

logger = get_logger(__name__)


def _safe_serialize_detail(detail: Any) -> Any:
    """Safely serialize detail for JSON response.

    Prevents cascade failures when detail contains non-serializable objects
    like datetime, UUID, database models, etc.
    """
    if detail is None:
        return None
    try:
        # Test if it's JSON serializable
        json.dumps(detail)
        return detail
    except (TypeError, ValueError):
        # Fall back to string representation
        return str(detail)


def _create_error_response(
    status_code: int,
    error: str,
    detail: Any = None,
    headers: dict | None = None,
) -> JSONResponse:
    """Create a standardized error response.

    Matches the ErrorResponse schema in schemas/common.py.
    """
    content = {
        "success": False,
        "error": error,
        "detail": _safe_serialize_detail(detail),
        "status_code": status_code,
    }
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=headers,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle all AppError exceptions (custom domain errors).

    Converts AppError and its subclasses to appropriate HTTP responses.
    """
    # Log server errors at error level, client errors at warning
    if exc.status_code >= 500:
        logger.error(
            f"Server error: {exc.message}",
            extra={"detail": exc.detail, "path": request.url.path},
        )
    else:
        logger.warning(
            f"Client error: {exc.message}",
            extra={"detail": exc.detail, "path": request.url.path},
        )

    # Add Retry-After header for rate limit errors
    headers = None
    if isinstance(exc, RateLimitError) and exc.retry_after:
        headers = {"Retry-After": str(exc.retry_after)}

    return _create_error_response(
        status_code=exc.status_code,
        error=exc.message,
        detail=exc.detail,
        headers=headers,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Handle FastAPI/Starlette HTTPException.

    Converts standard HTTPException to our error response format.
    """
    logger.warning(
        f"HTTP exception: {exc.detail}",
        extra={"status_code": exc.status_code, "path": request.url.path},
    )

    return _create_error_response(
        status_code=exc.status_code,
        error=str(exc.detail) if exc.detail else "Request failed",
        detail=None,
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors.

    Formats validation errors in a user-friendly way.
    """
    # Extract field errors into a readable format
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(x) for x in error["loc"])
        errors.append({"field": loc, "message": error["msg"]})

    logger.warning(
        f"Validation error: {len(errors)} field(s) invalid",
        extra={"errors": errors, "path": request.url.path},
    )

    return _create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error="Validation failed",
        detail=errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions.

    Catches any unhandled exception and returns a generic 500 error.
    Logs the full exception for debugging.
    """
    logger.exception(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={"path": request.url.path},
    )

    return _create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="Internal server error",
        detail=None,  # Don't expose internal error details
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app.

    Call this after creating the app in main.py:

        app = FastAPI(...)
        setup_exception_handlers(app)
    """
    # Custom application errors (most specific)
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]

    # FastAPI/Starlette HTTP exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]

    # Pydantic validation errors
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

    # Catch-all for unhandled exceptions (least specific)
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]

    logger.info("✅ Exception handlers registered")
