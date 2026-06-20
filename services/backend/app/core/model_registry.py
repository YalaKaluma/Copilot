"""Model registry for managing OpenAI model configurations.

Re-exports from shared package for backward compatibility.
"""

from packages.llm import (
    ModelRegistry,
    ModelConfig,
    ModelsConfig,
    get_model_registry,
)

__all__ = [
    "ModelRegistry",
    "ModelConfig",
    "ModelsConfig",
    "get_model_registry",
]
