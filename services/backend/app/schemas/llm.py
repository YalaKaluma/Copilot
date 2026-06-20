"""LLM API schemas.

Request and response schemas for the multi-provider LLM endpoints.
"""

from pydantic import BaseModel, Field

from .base import CamelCaseModel


class ChatMessage(BaseModel):
    """Chat message format."""

    role: str = Field(..., description="Message role (system, user, assistant)")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Chat completion request."""

    messages: list[ChatMessage] = Field(..., description="Conversation messages")
    model: str | None = Field(
        default=None, description="Model to use (provider-specific)"
    )
    provider: str | None = Field(
        default=None,
        description="LLM provider (openai, anthropic, gemini). Uses default if not specified.",
    )
    stream: bool = Field(default=False, description="Stream the response")
    temperature: float | None = Field(
        default=None, ge=0, le=2, description="Sampling temperature"
    )
    max_tokens: int | None = Field(default=None, description="Max tokens to generate")
    system_prompt_key: str | None = Field(
        default="default", description="System prompt key from config"
    )


class GenerateRequest(BaseModel):
    """Simple text generation request."""

    prompt: str = Field(..., description="Input prompt")
    model: str | None = Field(default=None, description="Model to use")
    provider: str | None = Field(default=None, description="LLM provider")
    stream: bool = Field(default=False, description="Stream the response")
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None)


class CompletionResponse(CamelCaseModel):
    """Standard completion response."""

    content: str = Field(..., description="Generated content")
    model: str = Field(..., description="Model used")
    provider: str = Field(..., description="Provider used")
    usage: dict | None = Field(default=None, description="Token usage stats")


class ProviderInfoResponse(CamelCaseModel):
    """Provider information."""

    provider: str
    name: str
    available: bool
    models: list[str]
    default_model: str


class ProvidersResponse(CamelCaseModel):
    """List of all providers."""

    providers: list[ProviderInfoResponse]
    default_provider: str | None = None
