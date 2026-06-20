"""Langfuse helper functions for span and trace updates.

These helpers are designed to work within functions decorated with @observe()
(which wraps the Langfuse SDK's decorator). They use the Langfuse SDK's
context-aware client to update the current span/trace.

NOTE: These do NOT work with @observe_llm() decorated functions, which manage
their own spans directly. For @observe_llm, the span updates are handled
automatically by the decorator.
"""

from typing import Any
from packages.langfuse.client import is_langfuse_enabled


def update_current_span(
    output: Any | None = None,
    model: str | None = None,
    usage: dict | None = None,
    metadata: dict | None = None,
) -> None:
    """Update the current span with additional details.

    Call this inside an @observe decorated function to add context.

    NOTE: This uses the Langfuse SDK's context-aware client (langfuse.get_client())
    to access the current trace context. It only works within functions decorated
    with @observe(), not with @observe_llm().

    Args:
        output: The output value
        model: Model name/ID
        usage: Token usage dict with prompt_tokens, completion_tokens, total_tokens
        metadata: Additional metadata
    """
    if not is_langfuse_enabled():
        return

    try:
        from langfuse import get_client

        client = get_client()

        update_kwargs = {}
        if output is not None:
            update_kwargs["output"] = output
        if model:
            update_kwargs["model"] = model
        if usage:
            update_kwargs["usage_details"] = {
                "input": usage.get("prompt_tokens", 0),
                "output": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0),
            }
        if metadata:
            update_kwargs["metadata"] = metadata

        if update_kwargs:
            client.update_current_span(**update_kwargs)
    except Exception:
        pass


def update_current_trace(
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict | None = None,
) -> None:
    """Update the current trace with user/session info.

    Call this inside an @observe decorated function to add context.

    NOTE: This uses the Langfuse SDK's context-aware client (langfuse.get_client())
    to access the current trace context. It only works within functions decorated
    with @observe(), not with @observe_llm().

    Args:
        user_id: User identifier
        session_id: Session identifier
        tags: List of tags
        metadata: Additional metadata
    """
    if not is_langfuse_enabled():
        return

    try:
        from langfuse import get_client

        client = get_client()

        update_kwargs = {}
        if user_id:
            update_kwargs["user_id"] = user_id
        if session_id:
            update_kwargs["session_id"] = session_id
        if tags:
            update_kwargs["tags"] = tags
        if metadata:
            update_kwargs["metadata"] = metadata

        if update_kwargs:
            client.update_current_trace(**update_kwargs)
    except Exception:
        pass
