"""Unit tests for config.prompt_registry."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.exceptions import AppConfigError
from config.prompt_registry import (
    LocalPromptRegistry,
    LangfusePromptRegistry,
)


class TestLocalPromptRegistry:
    """Tests for LocalPromptRegistry."""

    def test_get_prompt_loads_and_renders(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Hello {{ name }}")
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        out = registry.get_prompt("base", "v1", context={"name": "World"})
        assert out == "Hello World"

    def test_get_prompt_without_context(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Plain text")
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        out = registry.get_prompt("base", "v1")
        assert out == "Plain text"

    def test_get_prompt_raises_when_template_not_found(self, tmp_path):
        (tmp_path / "base").mkdir()
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        with pytest.raises(AppConfigError, match="Prompt template not found"):
            registry.get_prompt("base", "v99")

    def test_get_prompt_raises_when_no_prompts_dir(self):
        with pytest.raises(AppConfigError, match="Prompts directory not found"):
            LocalPromptRegistry(prompts_dir_root=Path("/nonexistent"))

    def test_get_prompt_raw_returns_file_content(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Raw content")
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        assert registry.get_prompt_raw("base", "v1") == "Raw content"

    def test_get_prompt_raw_raises_when_file_missing(self, tmp_path):
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        with pytest.raises(AppConfigError, match="Prompt file not found"):
            registry.get_prompt_raw("base", "v1")

    def test_register_prompt_new_dir_uses_v1(self, tmp_path):
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        version = registry.register_prompt("new_prompt", "Content here")
        assert version == "v1"
        assert (tmp_path / "new_prompt" / "v1.j2").read_text() == "Content here"

    def test_register_prompt_new_dir_with_version(self, tmp_path):
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        version = registry.register_prompt("new_prompt", "Content", version="v2")
        assert version == "v2"
        assert (tmp_path / "new_prompt" / "v2.j2").read_text() == "Content"

    def test_register_prompt_increments_version_when_no_version_given(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("Old")
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        version = registry.register_prompt("base", "New content")
        assert version == "v2"
        assert (tmp_path / "base" / "v2.j2").read_text() == "New content"

    def test_prompt_versions_returns_stems(self, tmp_path):
        (tmp_path / "base").mkdir()
        (tmp_path / "base" / "v1.j2").write_text("")
        (tmp_path / "base" / "v2.j2").write_text("")
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        versions = registry.prompt_versions("base")
        assert versions is not None
        assert set(versions) == {"v1", "v2"}

    def test_prompt_versions_returns_none_when_dir_missing(self, tmp_path):
        registry = LocalPromptRegistry(prompts_dir_root=tmp_path)
        assert registry.prompt_versions("nonexistent") is None


class TestLangfusePromptRegistry:
    """Tests for LangfusePromptRegistry with mocked client."""

    def test_raises_when_langfuse_not_configured(self):
        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=None,
        ):
            with pytest.raises(
                AppConfigError,
                match="prompt_registry=langfuse requires Langfuse",
            ):
                LangfusePromptRegistry()

    def test_get_prompt_fetches_and_compiles(self):
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "Compiled: expert, Dune 2"
        mock_client = MagicMock()
        mock_client.get_prompt.return_value = mock_prompt

        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            out = registry.get_prompt(
                "base",
                "v1",
                context={"criticlevel": "expert", "movie": "Dune 2"},
            )

        mock_client.get_prompt.assert_called_once_with("base", version=1)
        mock_prompt.compile.assert_called_once_with(
            criticlevel="expert", movie="Dune 2"
        )
        assert out == "Compiled: expert, Dune 2"

    def test_get_prompt_without_context(self):
        mock_prompt = MagicMock()
        mock_prompt.compile.return_value = "Plain content"
        mock_client = MagicMock()
        mock_client.get_prompt.return_value = mock_prompt

        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            out = registry.get_prompt("orchestrator", "v1")

        mock_client.get_prompt.assert_called_once_with("orchestrator", version=1)
        mock_prompt.compile.assert_called_once_with()
        assert out == "Plain content"

    def test_get_prompt_raw_returns_text_prompt(self):
        mock_prompt = MagicMock()
        mock_prompt.prompt = "Raw template string"
        mock_client = MagicMock()
        mock_client.get_prompt.return_value = mock_prompt

        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            out = registry.get_prompt_raw("base", "v1")

        mock_client.get_prompt.assert_called_once_with("base", version=1)
        assert out == "Raw template string"

    def test_version_str_to_int_invalid_label_raises(self):
        mock_client = MagicMock()
        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            with pytest.raises(AppConfigError, match="Invalid version label"):
                registry.get_prompt("base", "invalid")

    def test_register_prompt_with_version_ignores_version(self):
        """When version is passed, Langfuse registry ignores it and still creates a new prompt."""
        mock_client = MagicMock()
        mock_client.create_prompt.return_value = MagicMock(version=1)
        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            result = registry.register_prompt("base", "content", version="v1")
        assert result == "v1"
        mock_client.create_prompt.assert_called_once_with(
            name="base", type="text", prompt="content"
        )

    def test_register_prompt_returns_version(self):
        mock_client = MagicMock()
        mock_client.create_prompt.return_value = MagicMock(version=2)
        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            version = registry.register_prompt("base", "content")
        assert version == "v2"
        mock_client.create_prompt.assert_called_once_with(
            name="base", type="text", prompt="content"
        )

    def test_prompt_versions_returns_list(self):
        mock_client = MagicMock()
        mock_client.get_prompt.return_value = MagicMock(version=3)
        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            versions = registry.prompt_versions("base")
        assert versions == ["v1", "v2", "v3"]

    def test_prompt_versions_returns_none_on_error(self):
        mock_client = MagicMock()
        mock_client.get_prompt.side_effect = Exception("Not found")
        with patch(
            "config.prompt_registry.LangfusePromptRegistry._get_client",
            return_value=mock_client,
        ):
            registry = LangfusePromptRegistry()
            versions = registry.prompt_versions("base")
        assert versions is None
