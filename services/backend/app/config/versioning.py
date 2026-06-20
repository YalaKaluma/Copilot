"""Copilot version configuration: Pydantic models, YAML loader, and prompt I/O.

- Core: Load version config from config/versions/{version_id}.yaml; resolve
  prompts via PromptRegistry (local .j2 files or Langfuse).
- Prompt optimizer: Helpers to save a single prompt under a named version and
  to create a new Skai version YAML reusing base refs for unsaved prompts.
"""

import re
from pathlib import Path
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_yaml import parse_yaml_file_as, to_yaml_file

from core.exceptions import AppConfigError
from config.prompt_registry import (
    LangfusePromptRegistry,
    LocalPromptRegistry,
    PromptRegistry,
)
from core.logging import get_logger

logger = get_logger(__name__)


# -----------------------------------------------------------------------------
# Core: models and version loading (read)
# -----------------------------------------------------------------------------


class AgentModelConfig(BaseModel):
    """Model configuration for orchestrator and execution agents."""

    model_id: str = "gpt-5.2"


class ExecutionAgentConfig(BaseModel):
    """Configuration for execution agents."""

    domain: str = Field(..., description="Domain of the execution agent")
    name: str = Field(..., description="Name of the execution agent")
    tools: list[str] | None = Field(
        None, description="Tools available to the execution agent"
    )
    description: str = Field(..., description="Description of the execution agent")
    prompt_id: str = Field(..., description="Prompt id for the execution agent")
    code_interpreter_mode: Literal["local", "openai"] | None = Field(
        default=None, description="Whether to include the code interpreter tool"
    )


class ArchetypeConfig(BaseModel):
    """Configuration for archetypes."""

    scoping_framework: str = Field(
        ..., description="Scoping framework for the archetype"
    )
    planning_framework: str = Field(
        ..., description="Planning framework for the archetype"
    )
    response_format: str = Field(..., description="Response format for the archetype")
    promo_analysis_framework: str = Field(
        ..., description="Promo analysis framework for the archetype"
    )


class CopilotVersionConfig(BaseModel):
    """Compound copilot version configuration (validated from YAML)."""

    version: str = Field(..., description="Version id, e.g. v1, v2")
    execution_agents: list[ExecutionAgentConfig] = Field(
        default_factory=list,
        description=(
            "Enabled execution agent domains for handoff-based orchestrators. "
            "May be empty for single-agent orchestrator modes."
        ),
    )
    tools: dict[str, list[str]] | None = Field(
        default=None,
        description="Optional: tool names from registry to add per execution agent (agent_id -> list of tool names)",
    )
    model: AgentModelConfig = Field(
        default=AgentModelConfig(),
        description="Optional model config; if absent, use app default",
    )
    prompts: dict[str, str] = Field(
        ...,
        description="Prompt refs by key; value is 'name:version' (e.g. base:v1) -> prompts/name/version.j2",
    )
    orchestrator_version: str = Field(
        default="v1",
        description="Orchestrator version",
    )
    archetype_config: dict[
        Literal["A1", "A2", "A3", "A4", "A5", "A6"], ArchetypeConfig
    ] = Field(
        default_factory=dict,
        description="Configuration for archetypes",
    )


class ResolvedVersion:
    """Version config with resolved prompt content (from registry: local or Langfuse).

    get_prompt() delegates to the configured PromptRegistry. get_prompt_raw() always
    reads from local prompts dir so the prompt optimizer UI stays file-based.
    """

    def __init__(
        self,
        config: CopilotVersionConfig,
        prompts_dir_root: Path | None = None,
        prompt_registry: "PromptRegistry | None" = None,
    ):
        self.config = config
        self._prompts_dir_root = prompts_dir_root or (
            Path(__file__).resolve().parents[1] / "prompts"
        )
        if prompt_registry is not None:
            self._registry = prompt_registry
        else:
            logger.warning(
                f"Prompts directory not found or is not a directory: {self._prompts_dir_root}"
            )
            self._registry = LocalPromptRegistry(
                prompts_dir_root=self._prompts_dir_root,
            )

    def _find_name_and_version_for_key(self, key: str) -> tuple[str, str]:
        """Find the name and version for a key."""
        prompt_id = None
        if key in self.config.prompts:
            prompt_id = self.config.prompts[key]
        for agent in self.config.execution_agents:
            if agent.name == key:
                prompt_id = agent.prompt_id
        if prompt_id is None:
            raise AppConfigError(f"Prompt key not found: {key!r}")
        if ":" not in prompt_id:
            raise AppConfigError(f"Prompt ID is not valid: {prompt_id!r}")
        name, version = prompt_id.split(":", 1)
        return name, version

    def prompt_keys(self) -> list[str]:
        """Return all prompt keys for this version (for dropdown)."""
        keys = list(self.config.prompts.keys())
        for agent in self.config.execution_agents:
            keys.append(agent.name)
        return keys

    def get_prompt(self, key: str, context: dict | None = None) -> str:
        """Get a prompt by key."""
        name, version = self._find_name_and_version_for_key(key)
        return self._registry.get_prompt(name, version, context)

    def get_prompt_raw(self, key: str) -> str:
        """Get a prompt by key."""
        name, version = self._find_name_and_version_for_key(key)
        return self._registry.get_prompt_raw(name, version)

    def register_prompt(
        self, key: str, content: str, version: str | None = None
    ) -> str:
        """Register a new prompt by key."""
        name, _ = self._find_name_and_version_for_key(key)
        new_version = self._registry.register_prompt(name, content, version=version)

        if key in self.config.prompts:
            self.config.prompts[key] = f"{name}:{new_version}"
        else:
            for agent in self.config.execution_agents:
                if agent.name == key:
                    agent.prompt_id = f"{name}:{new_version}"
                    break
            else:
                raise AppConfigError(f"Execution agent not found: {key!r}")

        return new_version


def _config_versions_dir() -> Path:
    """Directory containing version YAML files and version subdirs."""
    return Path(__file__).resolve().parent / "versions"


def load_version_from_yaml(version_id: str) -> ResolvedVersion:
    """Load version config from config/versions/{version_id}.yaml and resolve prompts.

    Uses prompt_registry setting: local (Jinja .j2 files) or langfuse (Langfuse API).
    Raises RuntimeError if prompt_registry=langfuse but Langfuse is not configured.

    Raises:
        FileNotFoundError: If version YAML or a referenced prompt file is missing.
        ValueError: If YAML is invalid or validation fails.
    """
    versions_dir = _config_versions_dir()
    yaml_path = versions_dir / f"{version_id}.yaml"
    if not yaml_path.is_file():
        raise AppConfigError(f"Version config not found: {yaml_path}")

    config = parse_yaml_file_as(CopilotVersionConfig, yaml_path)
    prompts_root = _prompts_dir_root()

    registry = LangfusePromptRegistry()

    return ResolvedVersion(
        config=config,
        prompts_dir_root=prompts_root,
        prompt_registry=registry,
    )


# Reserved id for temp working copy (excluded from base version list).
TEMP_VERSION_ID = "temp"


def _prompts_dir_root() -> Path:
    """Root directory for prompt template files (e.g. app/prompts)."""
    return Path(__file__).resolve().parents[1] / "prompts"


# -----------------------------------------------------------------------------
# Prompt optimizer: write helpers (named prompt version + new Skai version)
# -----------------------------------------------------------------------------


def _validate_version_id(version_id: str, allow_temp: bool = False) -> None:
    if not re.match(r"^[a-zA-Z0-9_.-]+$", version_id):
        raise ValueError(
            f"version_id must be alphanumeric with optional . _ - got: {version_id!r}"
        )
    if not allow_temp and version_id == TEMP_VERSION_ID:
        raise ValueError("version_id cannot be 'temp'")


def save_prompt_to_version(
    base_version_id: str, key: str, content: str, prompt_version: str
) -> None:
    """Save a single prompt under a named prompt version (writes name/{prompt_version}.j2 only).

    Does not create or update any Skai version YAML. Use create_new_version_from_prompt_version
    to create a new Skai version that reuses base refs for unsaved prompts and this version for saved ones.
    """
    _validate_version_id(prompt_version, allow_temp=False)
    base_resolved = get_copilot_version(base_version_id, no_cache=False)

    base_resolved.register_prompt(key, content, version=prompt_version)


def create_new_version_based_on_modified_prompts(
    base_version_id: str,
    new_version_id: str,
) -> None:
    """Create a new Skai version YAML only; reuse base prompt refs for non-modified prompts.

    For each prompt key: if name/{prompt_version}.j2 exists (saved by the user), use ref
    name:prompt_version; otherwise reuse the base version's ref (e.g. name:v1).
    Writes only config/versions/{new_version_id}.yaml. Does not create or copy any prompt files.
    """
    _validate_version_id(new_version_id, allow_temp=False)

    base_resolved = get_copilot_version(base_version_id, no_cache=False)

    # Build prompts dict: new ref where prompt_version file exists, else base ref
    to_yaml_file(
        _config_versions_dir() / f"{new_version_id}.yaml", base_resolved.config
    )

    clear_copilot_version_cache()


# -----------------------------------------------------------------------------
# Version listing and cache
# -----------------------------------------------------------------------------


def list_base_version_ids() -> list[str]:
    """Return version ids from config/versions/*.yaml, excluding temp (for optimizer dropdown)."""
    versions_dir = _config_versions_dir()
    if not versions_dir.is_dir():
        return []
    return sorted(
        p.stem for p in versions_dir.glob("*.yaml") if p.stem != TEMP_VERSION_ID
    )


@lru_cache(maxsize=8)
def _get_copilot_version_cached(version_id: str) -> ResolvedVersion:
    """Cached loader for non-temp versions."""
    return load_version_from_yaml(version_id)


def get_copilot_version(version_id: str, no_cache: bool = True) -> ResolvedVersion:
    """Get resolved copilot version config by id.

    Temp is not cached so saves are visible immediately.
    Other versions are cached. Use settings.skai_copilot_version for the active version id.
    """
    if version_id == TEMP_VERSION_ID or no_cache:
        return load_version_from_yaml(version_id)
    return _get_copilot_version_cached(version_id)


def clear_copilot_version_cache() -> None:
    """Clear the copilot version cache (e.g. after saving temp)."""
    _get_copilot_version_cached.cache_clear()
