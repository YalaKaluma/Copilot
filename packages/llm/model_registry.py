"""Model registry for managing OpenAI model configurations.

Loads model definitions from Python config and provides validation/normalization.
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from packages.llm.config.openai_models import (
    DEFAULT_MODEL,
    GLOBAL_ALLOWED_PARAMS,
    MODELS,
    PARAM_MAPPINGS,
)

logger = logging.getLogger(__name__)


class ModelConfig(BaseModel):
    """Configuration for a single OpenAI model."""

    id: str
    name: str
    purpose: str
    aliases: list[str] = Field(default_factory=list)
    supports: dict[str, bool] = Field(default_factory=dict)
    allowed_params: list[str] = Field(default_factory=list)
    defaults: dict[str, Any] = Field(default_factory=dict)


class ModelsConfig(BaseModel):
    """Complete OpenAI models configuration."""

    default_model: str
    param_mappings: dict[str, str] = Field(default_factory=dict)
    global_allowed_params: list[str] = Field(default_factory=list)
    models: list[ModelConfig]


class ModelRegistry:
    """Registry for managing OpenAI model configurations and validating parameters."""

    def __init__(self):
        """Initialize the model registry from Python config."""
        self._load_config()

    def _load_config(self):
        """Load and parse the Python configuration."""
        # Parse with Pydantic for validation
        self.config = ModelsConfig(
            default_model=DEFAULT_MODEL,
            param_mappings=PARAM_MAPPINGS,
            global_allowed_params=GLOBAL_ALLOWED_PARAMS,
            models=[ModelConfig(**m) for m in MODELS],
        )

        # Build lookup maps including aliases
        self.models_by_id: dict[str, ModelConfig] = {}
        for model in self.config.models:
            # Add the main ID
            self.models_by_id[model.id] = model
            # Add all aliases
            for alias in model.aliases:
                self.models_by_id[alias] = model

        logger.info(f"Loaded {len(self.config.models)} model configurations")

    def get_model(self, model_id: str) -> ModelConfig | None:
        """Get a model configuration by ID or alias."""
        return self.models_by_id.get(model_id)

    def is_valid_model(self, model_id: str) -> bool:
        """Check if a model ID is valid."""
        return model_id in self.models_by_id

    def get_allowed_models(self) -> list[str]:
        """Get list of all allowed model IDs (including aliases)."""
        return list(self.models_by_id.keys())

    def get_model_ids(self) -> list[str]:
        """Get list of primary model IDs (excluding aliases)."""
        return [m.id for m in self.config.models]

    def get_model_info(self) -> list[dict[str, str]]:
        """Get simplified model information for frontend."""
        return [
            {"id": model.id, "name": model.name, "purpose": model.purpose}
            for model in self.config.models
        ]

    def validate_and_normalize_params(
        self, model_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate and normalize parameters for a specific model.

        Args:
            model_id: The model identifier
            params: Raw parameters from the request

        Returns:
            Normalized parameters ready for the API

        Raises:
            ValueError: If model is not found or parameters are invalid
        """
        model = self.get_model(model_id)
        if not model:
            raise ValueError(f"Model '{model_id}' is not supported")

        # Start with model defaults
        normalized = dict(model.defaults)

        # Combine model-specific and global allowed params
        all_allowed_params = set(model.allowed_params) | set(
            self.config.global_allowed_params
        )

        # Map and validate each parameter
        for key, value in params.items():
            if value is None:
                continue

            # Apply parameter name mappings
            mapped_key = self.config.param_mappings.get(key, key)

            # Check if parameter is allowed (model-specific or global)
            if mapped_key not in all_allowed_params:
                logger.debug(
                    f"Skipping parameter '{mapped_key}' not allowed for model '{model_id}'"
                )
                continue

            # Special handling for response_format
            if mapped_key == "response_format" and isinstance(value, dict):
                # Ensure strict mode for JSON schema if supported
                if value.get("type") == "json_schema" and model.supports.get(
                    "json_schema_strict"
                ):
                    value = dict(value)
                    value["strict"] = True

            normalized[mapped_key] = value

        return normalized

    def get_default_model(self) -> str:
        """Get the default model ID."""
        return self.config.default_model


# Singleton instance
_model_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    """Get the model registry singleton instance."""
    global _model_registry

    if _model_registry is None:
        _model_registry = ModelRegistry()

    return _model_registry
