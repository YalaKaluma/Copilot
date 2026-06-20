"""Google Gemini LLM Provider.

Thin wrapper around google-genai that implements the BaseLLMProvider interface.
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

# Available Gemini models (December 2025)
GEMINI_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]

DEFAULT_MODEL = "gemini-3-flash-preview"


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider implementation."""

    provider = LLMProvider.GEMINI

    def __init__(self, api_key: str | None = None):
        """Initialize Gemini provider.

        Args:
            api_key: Google API key
        """
        self._api_key = api_key
        self._client = None

        if self._api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=self._api_key)
                logger.info("Gemini provider initialized")
            except ImportError:
                logger.warning("google-genai package not installed")
        else:
            logger.debug("Gemini API key not provided")

    @property
    def is_configured(self) -> bool:
        """Check if Gemini is properly configured."""
        return self._client is not None

    def get_available_models(self) -> list[str]:
        """Get list of available Gemini models."""
        return GEMINI_MODELS.copy()

    def get_default_model(self) -> str:
        """Get the default Gemini model."""
        return DEFAULT_MODEL

    async def chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> LLMResponse:
        """Send chat messages and get a response from Gemini."""
        if not self.is_configured:
            raise ValueError("Gemini is not configured. Please provide an API key.")

        from google.genai import types

        model = config.model or DEFAULT_MODEL
        system_instruction, contents = self._format_messages(
            messages, config.system_prompt
        )

        generation_config = {}
        if config.temperature is not None:
            generation_config["temperature"] = config.temperature
        if config.max_tokens is not None:
            generation_config["max_output_tokens"] = config.max_tokens

        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=(
                    types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        **generation_config,
                    )
                    if system_instruction or generation_config
                    else None
                ),
            )

            content = ""
            if response.candidates and response.candidates[0].content.parts:
                content = response.candidates[0].content.parts[0].text

            usage = None
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "input_tokens": response.usage_metadata.prompt_token_count or 0,
                    "output_tokens": response.usage_metadata.candidates_token_count
                    or 0,
                    "total_tokens": response.usage_metadata.total_token_count or 0,
                }

            return LLMResponse(
                content=content,
                model=model,
                provider=self.provider,
                usage=usage,
                raw_response=response,
            )
        except Exception as e:
            logger.error(f"Gemini chat error: {str(e)}")
            raise

    async def stream_chat(
        self,
        messages: list[LLMMessage],
        config: LLMConfig,
    ) -> AsyncGenerator[str, None]:
        """Stream chat responses as SSE-formatted chunks."""
        if not self.is_configured:
            raise ValueError("Gemini is not configured. Please provide an API key.")

        from google.genai import types

        model = config.model or DEFAULT_MODEL
        system_instruction, contents = self._format_messages(
            messages, config.system_prompt
        )

        generation_config = {}
        if config.temperature is not None:
            generation_config["temperature"] = config.temperature
        if config.max_tokens is not None:
            generation_config["max_output_tokens"] = config.max_tokens

        try:
            yield f"data: {json.dumps({'type': 'start', 'model': model, 'provider': 'gemini'})}\n\n"

            async for chunk in self._client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=(
                    types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        **generation_config,
                    )
                    if system_instruction or generation_config
                    else None
                ),
            ):
                if chunk.candidates and chunk.candidates[0].content.parts:
                    text = chunk.candidates[0].content.parts[0].text
                    if text:
                        sse = {"choices": [{"delta": {"content": text}, "index": 0}]}
                        yield f"data: {json.dumps(sse)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Gemini streaming error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    def _format_messages(
        self, messages: list[LLMMessage], system_prompt: str | None
    ) -> tuple[str | None, list]:
        """Format messages for Gemini API.

        Returns:
            Tuple of (system_instruction, contents)
        """
        from google.genai import types

        system = system_prompt
        contents = []

        for msg in messages:
            if msg.role == "system":
                if system:
                    system = f"{system}\n\n{msg.content}"
                else:
                    system = msg.content
            else:
                role = "model" if msg.role == "assistant" else "user"
                contents.append(
                    types.Content(role=role, parts=[types.Part(text=msg.content)])
                )

        return system, contents
