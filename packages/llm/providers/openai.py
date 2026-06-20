"""OpenAI LLM Provider.

Thin wrapper around AsyncOpenAI that implements the BaseLLMProvider interface.
Supports both the Responses API (default) and Chat Completions API (fallback).
"""

import json
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

from packages.llm.base import (
    BaseLLMProvider,
    LLMConfig,
    LLMMessage,
    LLMProvider,
    LLMResponse,
)

logger = logging.getLogger(__name__)


def _get_models_from_registry() -> tuple[list[str], str]:
    """Load models from YAML registry if available."""
    try:
        from packages.llm.model_registry import get_model_registry

        registry = get_model_registry()
        return registry.get_model_ids(), registry.get_default_model()
    except Exception as e:
        logger.debug(f"Could not load model registry: {e}")
        # Fallback defaults
        return ["gpt-5-mini", "gpt-5", "gpt-4o"], "gpt-5-mini"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider implementation using the Responses API."""

    provider = LLMProvider.OPENAI

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        available_models: list[str] | None = None,
    ):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            default_model: Override default model
            available_models: Override available models list
        """
        self._api_key = api_key

        # Load from registry if not explicitly provided
        if available_models is None or default_model is None:
            registry_models, registry_default = _get_models_from_registry()
            self._available_models = available_models or registry_models
            self._default_model = default_model or registry_default
        else:
            self._available_models = available_models
            self._default_model = default_model

        if self._api_key:
            self._client = AsyncOpenAI(api_key=self._api_key)
            logger.info("OpenAI provider initialized")
        else:
            self._client = None
            logger.debug("OpenAI API key not provided")

    @property
    def is_configured(self) -> bool:
        """Check if OpenAI is properly configured."""
        return self._client is not None

    def get_available_models(self) -> list[str]:
        """Get list of available OpenAI models."""
        return self._available_models.copy()

    def get_default_model(self) -> str:
        """Get the default OpenAI model."""
        return self._default_model

    async def chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Send chat messages and get a response from OpenAI."""
        if not self.is_configured:
            raise ValueError("OpenAI is not configured. Please provide an API key.")

        model = config.model or self._default_model
        formatted_messages = self._format_messages(messages, config.system_prompt)

        params = {
            "model": model,
            "input": formatted_messages,
        }

        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_output_tokens"] = config.max_tokens
        if config.extra_params:
            params.update(config.extra_params)

        try:
            response = await self._client.responses.create(**params)

            return LLMResponse(
                content=response.output_text,
                model=model,
                provider=self.provider,
                usage=self._extract_usage(response),
                raw_response=response,
            )
        except Exception as e:
            if "responses" in str(e).lower() or "not found" in str(e).lower():
                logger.warning(
                    f"Responses API failed, falling back to Chat Completions: {e}"
                )
                return await self._chat_completions_fallback(
                    formatted_messages, config, model
                )
            raise

    async def _chat_completions_fallback(
        self,
        messages: list[dict],
        config: LLMConfig,
        model: str,
    ) -> LLMResponse:
        """Fallback to Chat Completions API."""
        params = {
            "model": model,
            "messages": messages,
        }

        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens

        response = await self._client.chat.completions.create(**params)

        return LLMResponse(
            content=response.choices[0].message.content,
            model=model,
            provider=self.provider,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": (
                    response.usage.completion_tokens if response.usage else 0
                ),
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
            raw_response=response,
        )

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses as SSE-formatted chunks."""
        if not self.is_configured:
            raise ValueError("OpenAI is not configured. Please provide an API key.")

        model = config.model or self._default_model
        formatted_messages = self._format_messages(messages, config.system_prompt)

        params = {
            "model": model,
            "input": formatted_messages,
            "stream": True,
        }

        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_output_tokens"] = config.max_tokens
        if config.extra_params:
            params.update(config.extra_params)

        try:
            yield f"data: {json.dumps({'type': 'start', 'model': model, 'provider': 'openai'})}\n\n"

            try:
                stream = await self._client.responses.create(**params)
            except Exception as e:
                if "responses" in str(e).lower() or "not found" in str(e).lower():
                    logger.warning(f"Falling back to Chat Completions API: {e}")
                    params["messages"] = params.pop("input")
                    params.pop("stream")
                    params["stream"] = True
                    if "max_output_tokens" in params:
                        params["max_tokens"] = params.pop("max_output_tokens")
                    async for chunk in self._stream_chat_completions(params):
                        yield chunk
                    return
                raise

            async for event in stream:
                etype = getattr(event, "type", None)

                if etype == "response.output_text.delta":
                    delta = getattr(event, "delta", None)
                    if delta:
                        sse = {"choices": [{"delta": {"content": delta}, "index": 0}]}
                        yield f"data: {json.dumps(sse)}\n\n"

                elif etype in ("response.error", "response.failed"):
                    message = getattr(
                        getattr(event, "error", None),
                        "message",
                        "Unknown streaming error",
                    )
                    yield f"data: {json.dumps({'type': 'error', 'error': message})}\n\n"

                elif etype in ("response.completed", "response.done"):
                    yield "data: [DONE]\n\n"
                    return

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    async def _stream_chat_completions(self, params: dict) -> AsyncGenerator[str, None]:
        """Stream using Chat Completions API."""
        stream = await self._client.chat.completions.create(**params)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                sse = {
                    "choices": [
                        {
                            "delta": {"content": chunk.choices[0].delta.content},
                            "index": 0,
                        }
                    ]
                }
                yield f"data: {json.dumps(sse)}\n\n"

        yield "data: [DONE]\n\n"

    def _format_messages(
        self, messages: list[LLMMessage], system_prompt: str | None
    ) -> list[dict]:
        """Format messages for OpenAI API."""
        formatted = []

        if system_prompt and (not messages or messages[0].role != "system"):
            formatted.append({"role": "system", "content": system_prompt})

        for msg in messages:
            formatted.append({"role": msg.role, "content": msg.content})

        return formatted

    def _extract_usage(self, response) -> dict[str, int] | None:
        """Extract usage stats from response."""
        if hasattr(response, "usage") and response.usage:
            return {
                "input_tokens": getattr(response.usage, "input_tokens", 0),
                "output_tokens": getattr(response.usage, "output_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }
        return None
