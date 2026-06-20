from contextlib import contextmanager, nullcontext
from typing import Any, ContextManager, Literal, overload

from langfuse import (
    LangfuseAgent,
    LangfuseChain,
    LangfuseEmbedding,
    LangfuseEvaluator,
    LangfuseEvent,
    LangfuseGeneration,
    LangfuseGuardrail,
    LangfuseRetriever,
    LangfuseSpan,
    LangfuseTool,
)

from packages.langfuse.client import get_langfuse_client
from models.copilot.base import ChatEvent, ToolInput
from uuid import UUID


def to_trace_id(assistant_message_id: UUID) -> str:
    """Convert a UUID to a 32-character lowercase hex string (OTEL format)."""
    return assistant_message_id.hex.lower()[:32]


@overload
def observation_context(
    name: str,
    as_type: Literal["span"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseSpan | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["tool"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseTool | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["generation"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseGeneration | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["agent"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseAgent | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["chain"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseChain | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["retriever"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseRetriever | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["embedding"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseEmbedding | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["event"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseEvent | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["evaluator"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseEvaluator | None]: ...


@overload
def observation_context(
    name: str,
    as_type: Literal["guardrail"],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[LangfuseGuardrail | None]: ...


def observation_context(
    name: str,
    as_type: Literal[
        "span",
        "tool",
        "generation",
        "agent",
        "chain",
        "retriever",
        "embedding",
        "event",
        "evaluator",
        "guardrail",
    ],
    input: dict[str, Any] | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
    input_messages: list[ChatEvent] | None = None,
    model: str | None = None,
    tools: list[ToolInput] | None = None,
    trace_id: str | None = None,
) -> ContextManager[Any | None]:
    """Return a context manager for a Langfuse observation, or nullcontext when disabled."""
    langfuse_client = get_langfuse_client()
    if not langfuse_client:
        return nullcontext()

    input_dict = input or {}
    if input_messages:
        input_dict["messages"] = [
            {"role": message.role, "content": message.content}
            for message in input_messages
        ]

    model = model or input_dict.get("model")

    if tools:
        input_dict["tools"] = [tool.model_dump(mode="json") for tool in tools]

    inner = langfuse_client.start_as_current_observation(
        name=name,
        as_type=as_type,
        input=input_dict,
        model=model,
        trace_context={"trace_id": trace_id} if trace_id else None,
    )

    update_trace_dict = {}
    if session_id:
        update_trace_dict["session_id"] = session_id
    if user_id:
        update_trace_dict["user_id"] = user_id

    @contextmanager
    def with_session_on_trace() -> Any:
        with inner as span:
            if span and update_trace_dict:
                span.update_trace(**update_trace_dict)
            yield span

    return with_session_on_trace()
