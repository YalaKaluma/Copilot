"""Backend LLM Service.

Wraps the shared LLM primitives with backend-specific features:
- Settings-based API key configuration
- System prompts from config
- Model registry integration
- Dependency injection
- Optional Langfuse tracing (automatic when configured)

Usage:
    from services.llm import LLMService, LLMProvider

    llm = LLMService()

    # Use default provider (first available)
    response = await llm.chat(messages=[...])

    # Use specific provider
    response = await llm.chat(messages=[...], provider=LLMProvider.ANTHROPIC)

    # Stream responses
    async for chunk in await llm.chat(messages=[...], stream=True):
        print(chunk)
"""

from functools import lru_cache
from typing import AsyncGenerator, Literal, overload

from core.config import get_settings
from core.logging import get_logger
from config.prompts import get_system_prompt
from core.model_registry import get_model_registry

# Import from shared package
from packages.llm import (
    LLMProvider,
    LLMMessage,
    LLMConfig,
    LLMResponse,
    ProviderInfo,
    BaseLLMProvider,
    LLMProviderFactory,
)

# Import Langfuse decorator for LLM calls
from packages.langfuse import observe_llm

logger = get_logger(__name__)

# Re-export types for convenience
__all__ = [
    "LLMService",
    "LLMProvider",
    "LLMMessage",
    "LLMConfig",
    "LLMResponse",
    "ProviderInfo",
    "get_llm_service",
]


@lru_cache(maxsize=1)
def _get_factory() -> LLMProviderFactory:
    """Get singleton factory configured with API keys from settings."""
    settings = get_settings()
    return LLMProviderFactory(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=getattr(settings, "anthropic_api_key", None),
        gemini_api_key=getattr(settings, "gemini_api_key", None),
    )


class LLMService:
    """Backend LLM service with settings integration.

    Provides a consistent interface for chat completions across
    OpenAI, Anthropic, and Gemini with backend-specific features.

    All LLM calls are automatically traced via Langfuse when configured.
    """

    def __init__(self, factory: LLMProviderFactory | None = None):
        """Initialize the LLM service.

        Args:
            factory: Optional provider factory. Uses singleton if not provided.
        """
        self._factory = factory or _get_factory()

    @property
    def is_configured(self) -> bool:
        """Check if at least one provider is configured."""
        return self._factory.get_default_provider() is not None

    def get_provider(self, provider: LLMProvider | None = None) -> BaseLLMProvider:
        """Get a specific provider or the default one.

        Args:
            provider: Optional provider type. Uses default if not specified.

        Returns:
            Provider instance

        Raises:
            ValueError: If no provider is configured
        """
        if provider:
            return self._factory.get_provider(provider)

        default = self._factory.get_default_provider()
        if not default:
            raise ValueError(
                "No LLM provider configured. Please set at least one of: "
                "OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY"
            )
        return default

    def get_available_providers(self) -> list[ProviderInfo]:
        """Get information about all providers and their availability."""
        providers = self._factory.get_available_providers()

        # Enhance OpenAI with model registry info
        for info in providers:
            if info.provider == LLMProvider.OPENAI and info.available:
                try:
                    registry = get_model_registry()
                    info.models = [m["id"] for m in registry.get_model_info()]
                    info.default_model = registry.get_default_model()
                except Exception:
                    pass

        return providers

    @overload
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        provider: LLMProvider | None = None,
        *,
        stream: Literal[True],
        system_prompt_key: str = "default",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]: ...

    @overload
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        provider: LLMProvider | None = None,
        *,
        stream: Literal[False] = False,
        system_prompt_key: str = "default",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse: ...

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        provider: LLMProvider | None = None,
        stream: bool = False,
        system_prompt_key: str = "default",
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """Chat with an LLM provider.

        All calls are automatically traced via Langfuse when configured.
        Works for both streaming and non-streaming calls.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (provider-specific). Uses provider default if not specified.
            provider: Which provider to use. Uses default if not specified.
            stream: Whether to stream the response
            system_prompt_key: Key for system prompt from config (default: "default")
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse or async generator if streaming
        """
        llm_provider = self.get_provider(provider)

        # Convert dict messages to LLMMessage objects
        llm_messages = [
            LLMMessage(role=m["role"], content=m["content"]) for m in messages
        ]

        # Get system prompt from backend config
        system_prompt = get_system_prompt(system_prompt_key)

        # Use model registry default for OpenAI if not specified
        if model is None and llm_provider.provider == LLMProvider.OPENAI:
            try:
                registry = get_model_registry()
                model = registry.get_default_model()
            except Exception:
                model = llm_provider.get_default_model()
        elif model is None:
            model = llm_provider.get_default_model()

        # Build config
        config = LLMConfig(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            system_prompt=system_prompt,
            extra_params=kwargs,
        )

        # Use the traced method - handles both streaming and non-streaming
        return await self._execute_chat(
            llm_provider=llm_provider,
            llm_messages=llm_messages,
            config=config,
            model=model,
            stream=stream,
        )

    @observe_llm(name="chat")
    async def _execute_chat(
        self,
        llm_provider: BaseLLMProvider,
        llm_messages: list[LLMMessage],
        config: LLMConfig,
        model: str,
        stream: bool,
    ) -> LLMResponse | AsyncGenerator[str, None]:
        """Execute chat with automatic Langfuse tracing.

        The @observe_llm decorator handles:
        - Creating trace and generation spans
        - Capturing input messages
        - For streaming: wrapping the generator to accumulate output
        - For non-streaming: capturing the response
        - Flushing to Langfuse
        """
        if stream:
            return llm_provider.stream_chat(llm_messages, config)
        return await llm_provider.chat(llm_messages, config)

    async def generate_text(
        self,
        prompt: str,
        model: str | None = None,
        provider: LLMProvider | None = None,
        **kwargs,
    ) -> str:
        """Generate text from a simple prompt.

        Args:
            prompt: The input prompt
            model: Model to use
            provider: Which provider to use
            **kwargs: Additional parameters

        Returns:
            Generated text
        """
        response = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            provider=provider,
            stream=False,
            **kwargs,
        )

        content = response.content
        if not content:
            raise ValueError("No content returned from LLM")
        return content

    async def stream_text(
        self,
        prompt: str,
        model: str | None = None,
        provider: LLMProvider | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Stream text generation.

        Args:
            prompt: The input prompt
            model: Model to use
            provider: Which provider to use
            **kwargs: Additional parameters

        Yields:
            SSE-formatted chunks
        """
        stream = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            provider=provider,
            stream=True,
            **kwargs,
        )
        async for chunk in stream:
            yield chunk


def get_llm_service() -> LLMService:
    """Get LLM service instance for dependency injection."""
    return LLMService()
