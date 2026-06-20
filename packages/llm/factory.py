"""LLM Provider Factory.

Handles lazy initialization and availability checking for all LLM providers.
"""

import logging

from packages.llm.base import BaseLLMProvider, LLMProvider, ProviderInfo

logger = logging.getLogger(__name__)


class LLMProviderFactory:
    """Factory for creating and managing LLM provider instances.

    Uses lazy initialization - providers are only created when first requested.
    """

    def __init__(
        self,
        openai_api_key: str | None = None,
        anthropic_api_key: str | None = None,
        gemini_api_key: str | None = None,
    ):
        """Initialize factory with API keys.

        Args:
            openai_api_key: OpenAI API key
            anthropic_api_key: Anthropic API key
            gemini_api_key: Google Gemini API key
        """
        self._api_keys = {
            LLMProvider.OPENAI: openai_api_key,
            LLMProvider.ANTHROPIC: anthropic_api_key,
            LLMProvider.GEMINI: gemini_api_key,
        }
        self._providers: dict[LLMProvider, BaseLLMProvider] = {}

    def get_provider(self, provider: LLMProvider) -> BaseLLMProvider:
        """Get or create a provider instance.

        Args:
            provider: The provider type to get

        Returns:
            Provider instance

        Raises:
            ValueError: If provider type is unknown
        """
        if provider not in self._providers:
            self._providers[provider] = self._create_provider(provider)
        return self._providers[provider]

    def _create_provider(self, provider: LLMProvider) -> BaseLLMProvider:
        """Create a new provider instance.

        Args:
            provider: The provider type to create

        Returns:
            New provider instance
        """
        api_key = self._api_keys.get(provider)

        if provider == LLMProvider.OPENAI:
            from packages.llm.providers.openai import OpenAIProvider

            return OpenAIProvider(api_key=api_key)

        elif provider == LLMProvider.ANTHROPIC:
            from packages.llm.providers.anthropic import AnthropicProvider

            return AnthropicProvider(api_key=api_key)

        elif provider == LLMProvider.GEMINI:
            from packages.llm.providers.gemini import GeminiProvider

            return GeminiProvider(api_key=api_key)

        else:
            raise ValueError(f"Unknown provider: {provider}")

    def get_available_providers(self) -> list[ProviderInfo]:
        """Get information about all providers and their availability.

        Returns:
            List of ProviderInfo for all supported providers
        """
        providers_info = []

        for provider_type in LLMProvider:
            try:
                provider = self.get_provider(provider_type)
                providers_info.append(provider.get_provider_info())
            except Exception as e:
                logger.warning(f"Error getting provider {provider_type}: {e}")
                providers_info.append(
                    ProviderInfo(
                        provider=provider_type,
                        name=provider_type.value.title(),
                        available=False,
                        models=[],
                        default_model="",
                    )
                )

        return providers_info

    def get_configured_providers(self) -> list[BaseLLMProvider]:
        """Get list of all configured (available) providers.

        Returns:
            List of configured provider instances
        """
        configured = []
        for provider_type in LLMProvider:
            try:
                provider = self.get_provider(provider_type)
                if provider.is_configured:
                    configured.append(provider)
            except Exception:
                continue
        return configured

    def get_default_provider(self) -> BaseLLMProvider | None:
        """Get the default provider (first configured one).

        Priority: OpenAI > Anthropic > Gemini

        Returns:
            Default provider or None if none configured
        """
        priority = [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GEMINI]

        for provider_type in priority:
            try:
                provider = self.get_provider(provider_type)
                if provider.is_configured:
                    return provider
            except Exception:
                continue

        return None
