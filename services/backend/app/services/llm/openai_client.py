from openai import AsyncClient, Omit, omit
from openai.types.responses import (
    EasyInputMessageParam,
    ResponseFunctionToolCall,
    ResponseCodeInterpreterToolCall,
)
from openai.types.responses.response import Response
from openai.types.responses.response_stream_event import ResponseStreamEvent
from openai.types.shared.reasoning import Reasoning
from openai.types.shared.reasoning_effort import ReasoningEffort
from models.copilot.base import ChatEvent, ToolDefinition
from typing import AsyncGenerator, Any, Literal, Sequence, TypeVar
from pydantic import BaseModel

from core.logging import get_logger

T = TypeVar("T", bound=BaseModel)


logger = get_logger(__name__)


class ToolRequestResponse(BaseModel):
    tools: list[ResponseFunctionToolCall | ResponseCodeInterpreterToolCall]
    text: str | None = None


def _make_schema_strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a JSON schema compliant with OpenAI's strict mode.

    OpenAI requires:
    - additionalProperties: false on all object types
    - All properties must be required (or have defaults)
    """
    if not isinstance(schema, dict):
        return schema

    # If this is an object type, add additionalProperties: false
    if schema.get("type") == "object":
        schema["additionalProperties"] = False

        # Make all properties required if not already specified
        if "properties" in schema and "required" not in schema:
            schema["required"] = list(schema["properties"].keys())

    # Recursively process nested schemas
    if "properties" in schema:
        for prop_name, prop_schema in schema["properties"].items():
            schema["properties"][prop_name] = _make_schema_strict(prop_schema)

    if "items" in schema:
        schema["items"] = _make_schema_strict(schema["items"])

    if "$defs" in schema:
        for def_name, def_schema in schema["$defs"].items():
            schema["$defs"][def_name] = _make_schema_strict(def_schema)

    # Handle anyOf, oneOf, allOf
    for key in ("anyOf", "oneOf", "allOf"):
        if key in schema:
            schema[key] = [_make_schema_strict(s) for s in schema[key]]

    return schema


def _convert_chat_events_for_api(
    chat_history: list[ChatEvent],
) -> list[EasyInputMessageParam]:
    """Convert chat events to format compatible with OpenAI Responses API.

    The Responses API only supports: 'assistant', 'system', 'developer', 'user'
    Tool responses need to be converted to user messages.
    """
    result = []
    for event in chat_history:
        if event.role == "tool":
            result.append(
                EasyInputMessageParam(
                    role="user",
                    content=f"[Tool response for tool call ID {event.tool_call_id}]: {event.content}",
                    type="message",
                )
            )
        else:
            result.append(
                EasyInputMessageParam(
                    role=event.role,
                    content=event.content,
                    type="message",
                )
            )
    return result


class AsyncOpenaiClient:
    def __init__(self):
        self.client = AsyncClient()

    async def download_file(self, file_id: str) -> bytes:
        response = await self.client.files.content(file_id)
        return await response.aread()

    async def create_or_get_container(
        self,
        name: str,
        memory_limit: Literal["1g", "2g", "4g", "8g", "16g"] = "1g",
        container_id: str | None = None,
    ) -> str:
        """Create a container and return the container ID."""
        try:
            if container_id:
                response = await self.client.containers.retrieve(container_id)
                return response.id
        except Exception as e:
            logger.error(f"Error retrieving container: {e} recreating container")
        response = await self.client.containers.create(
            name=name,
            memory_limit=memory_limit,
        )
        return response.id

    async def create_container_file(
        self, container_id: str, file_name: str, file_content: bytes
    ) -> str:
        """Create a file in a container and return the path to the file."""
        response = await self.client.containers.files.create(
            container_id=container_id,
            file=file_content,
        )
        return response.path

    async def request(self, chat_history: list[ChatEvent], model: str) -> Response:
        response = await self.client.responses.create(
            model=model,
            input=_convert_chat_events_for_api(chat_history),
        )

        return response

    async def request_streamed(
        self, chat_history: list[ChatEvent], model: str
    ) -> AsyncGenerator[Response, None]:
        response = await self.client.responses.create(
            model=model,
            input=_convert_chat_events_for_api(chat_history),
        )

        yield response

    def _get_reasoning_effort(
        self,
        reasoning_effort: ReasoningEffort = None,
        summary: Literal["auto", "concise", "detailed"] = "auto",
    ) -> Reasoning | Omit:
        # todo: handle reasoning_effort for different models later
        if reasoning_effort is None:
            return omit
        return Reasoning(effort=reasoning_effort, summary=summary)

    async def request_tools(
        self,
        chat_history: list[ChatEvent],
        model: str,
        tools: Sequence[ToolDefinition],
        reasoning_effort: Literal["low", "medium", "high"] | None = "low",
    ) -> ToolRequestResponse:
        response = await self.client.responses.create(
            model=model,
            input=_convert_chat_events_for_api(chat_history),
            tools=[i.model_dump(exclude_none=True) for i in tools],
            reasoning=self._get_reasoning_effort(reasoning_effort),
        )
        # Find the function_call in the output (may have reasoning items first)
        for item in response.output:
            if isinstance(item, ResponseFunctionToolCall) or isinstance(
                item, ResponseCodeInterpreterToolCall
            ):
                return ToolRequestResponse(tools=[item], text=response.output_text)

        # If no function call found, return the first item (may be reasoning)
        return ToolRequestResponse(tools=[], text=response.output_text)

    async def request_tools_batch(
        self,
        chat_history: list[ChatEvent],
        model: str,
        tools: Sequence[ToolDefinition],
        reasoning_effort: Literal["none", "low", "medium", "high"] | None = "low",
    ) -> ToolRequestResponse:
        """Request tool calls from the model, returning ALL function_calls.

        Unlike request_tools() which returns only the first function_call,
        this method returns all function_calls from a single response,
        enabling parallel tool execution by the caller.

        If no function_calls are found, returns a list with the first output
        item (e.g. a message or reasoning item) so the caller can handle it.
        """
        response = await self.client.responses.create(
            model=model,
            input=_convert_chat_events_for_api(chat_history),
            tools=[i.model_dump(exclude_none=True) for i in tools],
            reasoning=self._get_reasoning_effort(reasoning_effort),
        )

        function_calls = [
            item
            for item in response.output
            if isinstance(
                item, (ResponseFunctionToolCall, ResponseCodeInterpreterToolCall)
            )
        ]

        if function_calls:
            return ToolRequestResponse(tools=function_calls, text=response.output_text)

        # No function calls — return non-function items for the caller to handle
        return ToolRequestResponse(tools=[], text=response.output_text)

    async def request_tools_stream(
        self,
        chat_history: list[ChatEvent],
        model: str,
        tools: Sequence[ToolDefinition],
        reasoning_effort: Literal["none", "low", "medium", "high"] | None = "low",
    ) -> AsyncGenerator[ResponseStreamEvent, None]:
        stream = await self.client.responses.create(
            model=model,
            input=_convert_chat_events_for_api(chat_history),
            tools=[i.model_dump(exclude_none=True) for i in tools],
            reasoning=self._get_reasoning_effort(reasoning_effort),
            stream=True,
        )
        async for event in stream:
            yield event

    async def request_structured(
        self,
        chat_history: list[ChatEvent],
        model: str,
        structured_output: type[T],
        reasoning_effort: Literal["none", "low", "medium", "high"] | None = "low",
    ) -> T:
        # Get schema and ensure it's compliant with OpenAI's strict mode
        schema = structured_output.model_json_schema()
        schema = _make_schema_strict(schema)

        # TODO: handle reasoning_effort for different models later
        response = await self.client.responses.create(
            model=model,
            input=_convert_chat_events_for_api(chat_history),
            text={
                "format": {
                    "type": "json_schema",
                    "name": structured_output.__name__,
                    "schema": schema,
                    "strict": True,
                }
            },
            reasoning=self._get_reasoning_effort(reasoning_effort),
        )

        # Parse the JSON response into the Pydantic model
        output_text = response.output_text
        return structured_output.model_validate_json(output_text)
