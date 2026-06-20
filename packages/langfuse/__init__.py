"""Optional Langfuse LLM observability package.

This package provides Langfuse integration for tracing LLM calls and functions.
It is OPTIONAL - the application works without it if langfuse is not installed
or not configured (missing LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY).

The package gracefully handles the case where langfuse is not installed.

Usage:
    from packages.langfuse import (
        is_langfuse_enabled,
        observe,
        observe_llm,
        update_current_span,
        update_current_trace,
        flush,
        log_status,
    )

    # Check if Langfuse is available
    if is_langfuse_enabled():
        @observe_llm(name="chat")
        async def chat_completion(...):
            ...

    # Decorators are no-ops when not configured
    @observe()
    def my_workflow():
        return process()

Configuration:
    Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY to enable.
    Optionally set LANGFUSE_HOST (default: https://cloud.langfuse.com).
"""

import logging

from packages.langfuse.client import (
    LANGFUSE_HOST_DEFAULT,
    LANGFUSE_HOST_ENV,
    LANGFUSE_PUBLIC_KEY_ENV,
    LANGFUSE_SECRET_KEY_ENV,
    flush,
    get_langfuse_client,
    get_langfuse_host,
    is_langfuse_enabled,
    log_status,
)
from packages.langfuse.decorators import observe, observe_llm
from packages.langfuse.helpers import update_current_span, update_current_trace

logger = logging.getLogger(__name__)

# Check if langfuse is installed
try:
    from langfuse import Langfuse  # noqa: F401

    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    logger.debug("langfuse not installed - Langfuse features disabled")

# Always export these - they handle the not-installed case gracefully


__all__ = [
    # Feature checks
    "is_langfuse_enabled",
    "LANGFUSE_AVAILABLE",
    # Client
    "get_langfuse_client",
    "get_langfuse_host",
    "flush",
    "log_status",
    # Constants
    "LANGFUSE_PUBLIC_KEY_ENV",
    "LANGFUSE_SECRET_KEY_ENV",
    "LANGFUSE_HOST_ENV",
    "LANGFUSE_HOST_DEFAULT",
    # Decorators
    "observe",
    "observe_llm",
    # Helpers
    "update_current_span",
    "update_current_trace",
]
