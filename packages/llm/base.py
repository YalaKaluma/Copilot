"""LLM Base Types and Protocol.

Defines the common interface for all LLM providers.
No external dependencies - pure Python types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncGenerator


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


@dataclass
class LLMMessage:
    """Standard message format across all providers."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMConfig:
    """Configuration for LLM requests."""

    model: str
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    system_prompt: str | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Standard response format across all providers."""

    content: str
    model: str
    provider: LLMProvider
    usage: dict[str, int] | None = None  # input_tokens, output_tokens, total_tokens
    finish_reason: str | None = None
    raw_response: Any | None = None


@dataclass
class ProviderInfo:
    """Information about a provider and its available models."""

    provider: LLMProvider
    name: str
    available: bool
    models: list[str]
    default_model: str


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement these methods to ensure consistent behavior.
    """

    provider: LLMProvider

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured with API keys."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Send chat messages and get a response.

        Args:
            messages: List of conversation messages
            config: LLM configuration options

        Returns:
            LLMResponse with generated content
        """
        ...

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses as SSE-formatted chunks.

        Args:
            messages: List of conversation messages
            config: LLM configuration options

        Yields:
            SSE-formatted string chunks
        """
        ...

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """Get list of available models for this provider."""
        ...

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        ...

    def get_provider_info(self) -> ProviderInfo:
        """Get information about this provider."""
        return ProviderInfo(
            provider=self.provider,
            name=self.provider.value.title(),
            available=self.is_configured,
            models=self.get_available_models() if self.is_configured else [],
            default_model=self.get_default_model(),
        )
