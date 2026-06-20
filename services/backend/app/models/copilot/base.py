from dataclasses import dataclass
from collections.abc import Callable

from pydantic import BaseModel, field_serializer, model_validator
from typing import Literal, Any, Union


class ChatEvent(BaseModel):
    role: Literal["user", "system", "tool", "assistant"]
    content: str
    tool_call_id: str | None = None


class ToolPropertyItem(BaseModel):
    type: str
    enum: list[str] | None = None

    @model_validator(mode="after")
    def validate_enum(self):
        if self.enum is not None and self.type != "string":
            raise ValueError("enum can only be used with string type")
        return self


class ToolProperty(BaseModel):
    type: str
    description: str
    items: ToolPropertyItem | None = (
        None  # Required for array types (e.g., {"type": "string"})
    )
    enum: list[str] | None = None
    nullable: bool = False

    @model_validator(mode="after")
    def validate_enum(self):
        if self.enum is not None and self.type != "string":
            raise ValueError("enum can only be used with string type")
        return self

    @field_serializer("type", when_used="always")
    def serialize_type(self, value: str) -> str | list[str]:
        """Emit type as [base_type, 'null'] for JSON Schema when nullable."""
        if self.nullable:
            return [value, "null"]
        return value


class ToolParameter(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, ToolProperty]
    required: list[str]

    @model_validator(mode="after")
    def required_in_keys(self):
        missing = set(self.required) - self.properties.keys()
        if missing:
            raise ValueError(
                f"Required fields not present in properties: {sorted(missing)}"
            )
        return self


def with_thinking(params: ToolParameter | None) -> ToolParameter:
    """Add a 'thinking' parameter to tool parameters for LLM reasoning.

    The thinking parameter allows the LLM to explain why it chose this tool,
    which can be shown transiently to users for transparency.
    """
    thinking_prop = ToolProperty(
        type="string",
        description="Brief explanation of why you're using this tool (1-2 sentences). This helps users understand your reasoning.",
    )

    if params is None:
        return ToolParameter(
            properties={"thinking": thinking_prop}, required=["thinking"]
        )

    # Add thinking to existing properties
    new_props = {"thinking": thinking_prop, **params.properties}
    new_required = ["thinking"] + params.required

    return ToolParameter(properties=new_props, required=new_required)


def with_instructions(params: ToolParameter | None) -> ToolParameter:
    """Add a 'instructions' parameter to tool parameters so that the LLM can follow instructions with the tool."""
    instructions_prop = ToolProperty(
        type="string",
        description="Instructions for the tool to follow with task, objective, desired output, etc.",
    )

    if params is None:
        return ToolParameter(
            properties={"instructions": instructions_prop}, required=["instructions"]
        )

    # Add instructions to existing properties
    new_props = {"instructions": instructions_prop, **params.properties}
    new_required = ["instructions"] + params.required

    return ToolParameter(properties=new_props, required=new_required)


class ToolInput(BaseModel):
    type: Literal["function"] = "function"
    name: str
    description: str
    parameters: ToolParameter | None = None

    def with_thinking(self) -> "ToolInput":
        """Return a copy of this tool with a 'thinking' parameter added.

        This allows the LLM to explain its reasoning when calling the tool.
        """
        return ToolInput(
            type=self.type,
            name=self.name,
            description=self.description,
            parameters=with_thinking(self.parameters),
        )

    def with_instructions(self) -> "ToolInput":
        """Return a copy of this tool with a 'instructions' parameter added.

        This allows the LLM to follow instructions with the tool.
        """
        return ToolInput(
            type=self.type,
            name=self.name,
            description=self.description,
            parameters=with_instructions(self.parameters),
        )


class BuiltinToolInput(BaseModel):
    type: Literal["code_interpreter"] = "code_interpreter"
    container: dict[str, Any] | str


ToolDefinition = Union[ToolInput, BuiltinToolInput]


# Type alias for executor functions
ExecutorFunc = Callable[..., Any]


@dataclass
class Tool:
    """A tool combining its definition (schema) with its executor function."""

    definition: ToolInput
    executor: ExecutorFunc

    @property
    def name(self) -> str:
        """Get the tool name."""
        return self.definition.name
