"""Langfuse decorators for function and LLM tracing.

Provides:
- @observe(): General-purpose function tracing
- @observe_llm(): LLM-specific tracing with streaming support
"""

import inspect
import json
from functools import wraps
from typing import Any, AsyncGenerator, Callable

from .client import get_langfuse_client, get_observe_decorator, is_langfuse_enabled


def observe(*args, **kwargs):
    """Conditional @observe decorator - no-op if Langfuse not configured.

    Wraps Langfuse's built-in @observe decorator. Use this for general function
    tracing, NOT for LLM calls (use @observe_llm instead).

    Usage:
        @observe()  # Basic trace
        def my_function(): ...

        @observe(name="custom-name")  # Named trace
        def process(): ...

        @observe(as_type="tool")  # Typed trace
        def my_tool(): ...

    Supported as_type values:
        - "span" (default)
        - "generation" (use @observe_llm instead for LLM calls)
        - "agent", "tool", "chain", "retriever", "embedding"
    """
    lf_observe = get_observe_decorator()

    def decorator(func: Callable) -> Callable:
        if lf_observe is None:
            return func  # No-op when not configured
        return lf_observe(*args, **kwargs)(func)

    # Handle both @observe and @observe()
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return decorator(args[0])
    return decorator


def observe_llm(
    name: str | None = None,
    extract_model: Callable[..., str] | None = None,
    extract_input: Callable[..., Any] | None = None,
):
    """Decorator for async LLM calls that handles both streaming and non-streaming.

    IMPORTANT: This decorator only works with async functions. For sync functions,
    use the @observe() decorator instead.

    This decorator is purpose-built for LLM service methods and automatically:
    - Creates a trace span with the function name
    - Captures input messages
    - For streaming: wraps the async generator to accumulate and capture output
    - For non-streaming: captures the response content and usage
    - Flushes traces to Langfuse

    Works with all LLM providers (OpenAI, Anthropic, Gemini) that use the
    standardized SSE format: {"choices": [{"delta": {"content": "..."}}]}

    Usage:
        @observe_llm(name="chat")
        async def _execute_chat(self, llm_provider, llm_messages, config, model, stream):
            if stream:
                return llm_provider.stream_chat(llm_messages, config)
            return await llm_provider.chat(llm_messages, config)

    Args:
        name: Name for the trace span (defaults to function name)
        extract_model: Optional callable to extract model from args/kwargs
        extract_input: Optional callable to extract input from args/kwargs

    Raises:
        TypeError: If applied to a non-async function (when Langfuse is enabled)
    """

    def decorator(func: Callable) -> Callable:
        if not is_langfuse_enabled():
            return func

        # Validate that the function is async
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"@observe_llm can only be applied to async functions. "
                f"'{func.__name__}' is not async. Use @observe() for sync functions."
            )

        @wraps(func)
        async def wrapper(*args, **kwargs):
            langfuse = get_langfuse_client()
            if not langfuse:
                return await func(*args, **kwargs)

            span_name = name or func.__name__

            # Extract model from kwargs or config
            model = None
            if extract_model:
                try:
                    model = extract_model(*args, **kwargs)
                except Exception:
                    pass
            else:
                model = kwargs.get("model")
                if not model and kwargs.get("config"):
                    model = getattr(kwargs["config"], "model", None)

            # Extract input messages
            input_data = None
            if extract_input:
                try:
                    input_data = extract_input(*args, **kwargs)
                except Exception:
                    pass
            else:
                input_data = kwargs.get("messages") or kwargs.get("llm_messages")
                if (
                    input_data
                    and len(input_data) > 0
                    and hasattr(input_data[0], "role")
                ):
                    input_data = [
                        {"role": m.role, "content": m.content} for m in input_data
                    ]

            # Create span using Langfuse 3.x API
            span = langfuse.start_span(name=span_name, input=input_data)

            try:
                result = await func(*args, **kwargs)

                # Check if result is an async generator (streaming)
                if inspect.isasyncgen(result):
                    return _wrap_async_generator(result, span, langfuse, model)

                # Non-streaming: capture output directly
                output = getattr(result, "content", None)
                usage_details = None
                if hasattr(result, "usage") and result.usage:
                    usage_details = {
                        "input": result.usage.get("prompt_tokens", 0),
                        "output": result.usage.get("completion_tokens", 0),
                        "total": result.usage.get("total_tokens", 0),
                    }

                span.update(output=output, model=model, usage_details=usage_details)
                span.end()
                langfuse.flush()
                return result

            except Exception as e:
                span.update(level="ERROR", status_message=str(e))
                span.end()
                langfuse.flush()
                raise

        return wrapper

    return decorator


async def _wrap_async_generator(
    gen: AsyncGenerator,
    span: Any,
    langfuse: Any,
    model: str | None = None,
) -> AsyncGenerator[str, None]:
    """Wrap an async generator to capture accumulated output for Langfuse.

    Extracts content from SSE-formatted chunks in the standard format used by
    all providers: {"choices": [{"delta": {"content": "..."}}]}

    Properly handles errors during streaming by marking the span as an error.
    """
    accumulated = []
    error_occurred = None

    try:
        async for chunk in gen:
            yield chunk
            # Extract content from SSE data format
            if isinstance(chunk, str) and chunk.startswith("data: "):
                payload = chunk[6:].strip()
                if payload == "[DONE]":
                    continue
                try:
                    data = json.loads(payload)
                    # Handle OpenAI-style format (used by all providers)
                    if "choices" in data and data["choices"]:
                        delta = data["choices"][0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            accumulated.append(content)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        error_occurred = e
        raise
    finally:
        full_output = "".join(accumulated) if accumulated else None
        if error_occurred:
            span.update(
                output=full_output,
                model=model,
                level="ERROR",
                status_message=str(error_occurred),
            )
        else:
            span.update(output=full_output, model=model)
        span.end()
        langfuse.flush()
