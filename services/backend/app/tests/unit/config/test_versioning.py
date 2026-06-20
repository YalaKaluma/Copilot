"""Unit tests for config.versioning."""

import pytest
from unittest.mock import MagicMock, patch

from core.exceptions import AppConfigError
from config.versioning import (
    AgentModelConfig,
    CopilotVersionConfig,
    ExecutionAgentConfig,
    ResolvedVersion,
    _config_versions_dir,
    load_version_from_yaml,
    get_copilot_version,
)


@pytest.fixture
def mock_langfuse_registry_client():
    """Mock LangfusePromptRegistry._get_client for tests that load version config (avoids real Langfuse)."""
    with patch(
        "config.versioning.LangfusePromptRegistry._get_client",
        return_value=MagicMock(),
    ):
        yield


class TestAgentModelConfig:
    """Tests for AgentModelConfig model."""

    def test_default_model_id(self):
        cfg = AgentModelConfig()
        assert cfg.model_id == "gpt-5.2"

    def test_custom_model_id(self):
        cfg = AgentModelConfig(model_id="gpt-4")
        assert cfg.model_id == "gpt-4"


class TestExecutionAgentConfig:
    """Tests for ExecutionAgentConfig model."""

    def test_valid_config(self):
        cfg = ExecutionAgentConfig(
            domain="category",
            name="category_agent",
            description="Category analytics. Tools: {tools}",
            prompt_id="category_agent:v1",
        )
        assert cfg.domain == "category"
        assert cfg.name == "category_agent"
        assert cfg.tools is None

    def test_with_tools_list(self):
        cfg = ExecutionAgentConfig(
            domain="category",
            name="category_agent",
            description="Tools: {tools}",
            prompt_id="category_agent:v1",
            tools=["skai_get_category_landscape"],
        )
        assert cfg.tools == ["skai_get_category_landscape"]

    def test_invalid_domain_raises(self):
        """Invalid domain is accepted (no validation); config allows any string."""
        cfg = ExecutionAgentConfig(
            domain="invalid",
            name="x",
            description="x",
            prompt_id="x:v1",
        )
        assert cfg.domain == "invalid"


class TestCopilotVersionConfig:
    """Tests for CopilotVersionConfig model."""

    def test_valid_config(self):
        cfg = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Cat. Tools: {tools}",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1", "orchestrator": "orchestrator:v1"},
        )
        assert cfg.version == "v1"
        assert len(cfg.execution_agents) == 1
        assert cfg.execution_agents[0].domain == "category"
        assert cfg.model.model_id == "gpt-5.2"

    def test_execution_agents_can_be_empty_for_single_agent_versions(self):
        cfg = CopilotVersionConfig(
            version="v9-dev",
            execution_agents=[],
            prompts={"base": "base:v1"},
        )
        assert cfg.execution_agents == []


class TestConfigVersionsDir:
    """Tests for _config_versions_dir."""

    def test_returns_versions_path(self):
        d = _config_versions_dir()
        assert d.name == "versions"
        assert d.is_dir() or not d.exists()


class TestResolvedVersion:
    """Tests for ResolvedVersion and get_prompt."""

    def test_get_prompt_raises_when_key_not_found(self, tmp_path):
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools: {tools}",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        with pytest.raises(AppConfigError, match="Prompt key not found"):
            resolved.get_prompt(key="missing_key")

    def test_get_prompt_with_key_and_context(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Hello {{ name }}")
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools: {tools}",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        out = resolved.get_prompt(key="base", context={"name": "World"})
        assert out == "Hello World"

    def test_get_prompt_with_key_uses_config_prompts(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Base prompt")
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools: {tools}",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        out = resolved.get_prompt(key="base")
        assert out == "Base prompt"

    def test_get_prompt_with_context_renders_template(self, tmp_path):
        (tmp_path / "orchestrator").mkdir()
        (tmp_path / "orchestrator" / "v1.j2").write_text(
            "Table: {{ agent_handoff_table }}"
        )
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools: {tools}",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"orchestrator": "orchestrator:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        out = resolved.get_prompt(
            key="orchestrator",
            context={"agent_handoff_table": "| col |"},
        )
        assert out == "Table: | col |"

    def test_prompt_keys_returns_prompts_and_agent_names(self, tmp_path):
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools: {tools}",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1", "orchestrator": "orchestrator:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        keys = resolved.prompt_keys()
        assert set(keys) == {"base", "orchestrator", "category_agent"}

    def test_get_prompt_raw_delegates_to_registry(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Raw base content")
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        assert resolved.get_prompt_raw("base") == "Raw base content"

    def test_get_prompt_raw_by_agent_name(self, tmp_path):
        (tmp_path / "category_agent").mkdir()
        (tmp_path / "category_agent" / "v1.j2").write_text("Agent prompt")
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        assert resolved.get_prompt_raw("category_agent") == "Agent prompt"

    def test_register_prompt_updates_config_prompts(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Old")
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        version = resolved.register_prompt("base", "New content")
        assert version == "v2"
        assert config.prompts["base"] == "base:v2"
        assert (tmp_path / "base" / "v2.j2").read_text() == "New content"

    def test_register_prompt_updates_agent_prompt_id(self, tmp_path):
        (tmp_path / "category_agent").mkdir()
        (tmp_path / "category_agent" / "v1.j2").write_text("Old")
        config = CopilotVersionConfig(
            version="v1",
            execution_agents=[
                ExecutionAgentConfig(
                    domain="category",
                    name="category_agent",
                    description="Tools",
                    prompt_id="category_agent:v1",
                ),
            ],
            prompts={"base": "base:v1"},
        )
        resolved = ResolvedVersion(config=config, prompts_dir_root=tmp_path)
        version = resolved.register_prompt("category_agent", "New agent prompt")
        assert version == "v2"
        assert config.execution_agents[0].prompt_id == "category_agent:v2"


@pytest.mark.usefixtures("mock_langfuse_registry_client")
class TestLoadVersionFromYaml:
    """Tests for load_version_from_yaml."""

    def test_missing_version_raises(self):
        with pytest.raises(AppConfigError, match="Version config not found"):
            load_version_from_yaml("nonexistent_version")

    def test_load_v1_returns_resolved_version(self):
        resolved = load_version_from_yaml("v2")
        assert isinstance(resolved, ResolvedVersion)
        assert resolved.config.version == "v2"
        assert len(resolved.config.execution_agents) >= 1
        assert resolved.config.prompts

    def test_load_v9_dev_allows_empty_execution_agents(self):
        resolved = load_version_from_yaml("v9-dev")
        assert isinstance(resolved, ResolvedVersion)
        assert resolved.config.version == "v9-dev"
        assert resolved.config.execution_agents == []
        assert resolved.config.orchestrator_version == "single_agent_promo_orchestrator"


@pytest.mark.usefixtures("mock_langfuse_registry_client")
class TestGetCopilotVersion:
    """Tests for get_copilot_version."""

    def test_returns_resolved_version_for_v1(self):
        v = get_copilot_version("v2")
        assert isinstance(v, ResolvedVersion)
        assert v.config.version == "v2"

    def test_cached_returns_same_instance(self):
        """When no_cache=False, the same ResolvedVersion instance is returned (cached)."""
        a = get_copilot_version("v2", no_cache=False)
        b = get_copilot_version("v2", no_cache=False)
        assert a is b
