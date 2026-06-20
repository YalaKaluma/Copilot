"""Anthropic Claude LLM Provider.

Thin wrapper around AsyncAnthropic that implements the BaseLLMProvider interface.
"""

import json
import logging
from typing import AsyncGenerator

from packages.llm.base import (
    BaseLLMProvider,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
)

logger = logging.getLogger(__name__)

# Available Anthropic Claude models (2025)
ANTHROPIC_MODELS = [
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-5-20251124",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-3-5-haiku-20241022",
]

# Model aliases for convenience
MODEL_ALIASES = {
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
    "claude-opus-4-5": "claude-opus-4-5-20251124",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
    "claude-opus-4": "claude-opus-4-20250514",
    "claude-3-5-haiku": "claude-3-5-haiku-20241022",
}

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider implementation."""

    provider = LLMProvider.ANTHROPIC

    def __init__(self, api_key: str | None = None):
        """Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
        """
        self._api_key = api_key
        self._client = None

        if self._api_key:
            try:
                from anthropic import AsyncAnthropic

                self._client = AsyncAnthropic(api_key=self._api_key)
                logger.info("Anthropic provider initialized")
            except ImportError:
                logger.warning("anthropic package not installed")
        else:
            logger.debug("Anthropic API key not provided")

    @property
    def is_configured(self) -> bool:
        """Check if Anthropic is properly configured."""
        return self._client is not None

    def get_available_models(self) -> list[str]:
        """Get list of available Anthropic models."""
        return ANTHROPIC_MODELS.copy()

    def get_default_model(self) -> str:
        """Get the default Anthropic model."""
        return DEFAULT_MODEL

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return MODEL_ALIASES.get(model, model)

    async def chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Send chat messages and get a response from Anthropic."""
        if not self.is_configured:
            raise ValueError("Anthropic is not configured. Please provide an API key.")

        model = self._resolve_model(config.model or DEFAULT_MODEL)
        system_prompt, formatted_messages = self._format_messages(
            messages, config.system_prompt
        )

        params = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": config.max_tokens or DEFAULT_MAX_TOKENS,
        }

        if system_prompt:
            params["system"] = system_prompt
        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.extra_params:
            params.update(config.extra_params)

        try:
            response = await self._client.messages.create(**params)

            return LLMResponse(
                content=response.content[0].text if response.content else "",
                model=model,
                provider=self.provider,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens
                    + response.usage.output_tokens,
                },
                finish_reason=response.stop_reason,
                raw_response=response,
            )
        except Exception as e:
            logger.error(f"Anthropic chat error: {str(e)}")
            raise

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses as SSE-formatted chunks."""
        if not self.is_configured:
            raise ValueError("Anthropic is not configured. Please provide an API key.")

        model = self._resolve_model(config.model or DEFAULT_MODEL)
        system_prompt, formatted_messages = self._format_messages(
            messages, config.system_prompt
        )

        params = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": config.max_tokens or DEFAULT_MAX_TOKENS,
        }

        if system_prompt:
            params["system"] = system_prompt
        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.extra_params:
            params.update(config.extra_params)

        try:
            yield f"data: {json.dumps({'type': 'start', 'model': model, 'provider': 'anthropic'})}\n\n"

            async with self._client.messages.stream(**params) as stream:
                async for text in stream.text_stream:
                    sse = {"choices": [{"delta": {"content": text}, "index": 0}]}
                    yield f"data: {json.dumps(sse)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Anthropic streaming error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    def _format_messages(
        self, messages: list[LLMMessage], system_prompt: str | None
    ) -> tuple[str | None, list[dict]]:
        """Format messages for Anthropic API.

        Anthropic requires system prompt to be separate from messages.

        Returns:
            Tuple of (system_prompt, formatted_messages)
        """
        system = system_prompt
        formatted = []

        for msg in messages:
            if msg.role == "system":
                if system:
                    system = f"{system}\n\n{msg.content}"
                else:
                    system = msg.content
            else:
                role = "assistant" if msg.role == "assistant" else "user"
                formatted.append({"role": role, "content": msg.content})

        return system, formatted
