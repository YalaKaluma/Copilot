"""Shared LLM primitives for multi-provider support.

This package provides the core building blocks for LLM integration:
- Base types (LLMMessage, LLMResponse, LLMConfig)
- Provider protocol (BaseLLMProvider)
- Provider implementations (OpenAI, Anthropic, Gemini)
- Provider factory

Usage:
    from packages.llm import (
        LLMProvider,
        LLMMessage,
        LLMConfig,
        LLMResponse,
        LLMProviderFactory,
    )

    # Create factory with API keys
    factory = LLMProviderFactory(
        openai_api_key="sk-...",
        anthropic_api_key="sk-ant-...",
    )

    # Get a provider
    provider = factory.get_provider(LLMProvider.OPENAI)

    # Use it
    response = await provider.chat(messages, config)
"""

from packages.llm.base import (
    LLMProvider,
    LLMMessage,
    LLMConfig,
    LLMResponse,
    ProviderInfo,
    BaseLLMProvider,
)
from packages.llm.factory import LLMProviderFactory
from packages.llm.model_registry import (
    ModelRegistry,
    ModelConfig,
    ModelsConfig,
    get_model_registry,
)

__all__ = [
    # Enums
    "LLMProvider",
    # Data types
    "LLMMessage",
    "LLMConfig",
    "LLMResponse",
    "ProviderInfo",
    # Protocol
    "BaseLLMProvider",
    # Factory
    "LLMProviderFactory",
    # Model Registry
    "ModelRegistry",
    "ModelConfig",
    "ModelsConfig",
    "get_model_registry",
]
