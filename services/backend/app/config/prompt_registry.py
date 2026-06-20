"""Prompt registry abstraction: resolve prompt refs from local files or Langfuse.

Used by ResolvedVersion to get prompt content by key or prompt_id. Two implementations:
- LocalPromptRegistry: Jinja .j2 files under a prompts directory.
- LangfusePromptRegistry: fetch by name + label from Langfuse, compile variables.
"""

from pathlib import Path
import re
from typing import Protocol

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from core.exceptions import AppConfigError
from packages.langfuse.client import get_langfuse_client
from core.logging import get_logger

logger = get_logger(__name__)


class PromptRegistry(Protocol):
    """Protocol for resolving prompt content by key or prompt_id."""

    def get_prompt(
        self,
        name: str,
        version: str,
        context: dict | None = None,
    ) -> str:
        """Return resolved prompt content. Exactly one of key or prompt_id must be set."""
        ...

    def register_prompt(
        self, name: str, prompt: str, version: str | None = None
    ) -> str:
        """Register a new prompt"""
        ...

    def prompt_versions(self, name: str) -> list[str] | None:
        """Return the versions of a prompt"""
        ...

    def get_prompt_raw(self, name: str, version: str) -> str:
        """Return raw template content for key (for editing). Used by prompt optimizer."""
        ...


class LocalPromptRegistry:
    """Resolve prompts from local .j2 files under a prompts directory."""

    def __init__(
        self,
        prompts_dir_root: Path,
    ):
        self._prompts_dir_root = Path(prompts_dir_root)
        if self._prompts_dir_root.is_dir():
            self._env = Environment(
                loader=FileSystemLoader(str(self._prompts_dir_root)),
                autoescape=False,
            )
        else:
            raise AppConfigError(
                f"Prompts directory not found or not readable: {self._prompts_dir_root}"
            )

    def register_prompt(
        self, name: str, prompt: str, version: str | None = None
    ) -> str:
        """Register a new prompt and return the version."""

        prompt_dir = self._prompts_dir_root / name

        if not prompt_dir.exists():
            prompt_dir.mkdir(parents=True, exist_ok=True)
            version = version or "v1"
        elif version is None:
            version_int = (
                max(int(p.stem.replace("v", "")) for p in prompt_dir.glob("*.j2")) + 1
            )
            version = f"v{version_int}"
        prompt_path = prompt_dir / f"{version}.j2"

        prompt_path.write_text(prompt, encoding="utf-8")
        return version

    def get_prompt(
        self,
        name: str,
        version: str,
        context: dict | None = None,
    ) -> str:
        """Load template from disk and render with context."""
        template_path = f"{name}/{version}.j2"
        try:
            prompt_template = self._env.get_template(template_path)
        except TemplateNotFound as e:
            raise AppConfigError(f"Prompt template not found: {template_path}") from e
        return (
            prompt_template.render(**context) if context else prompt_template.render()
        )

    def prompt_versions(self, name: str) -> list[str] | None:
        """Return the versions of a prompt"""
        prompt_dir = self._prompts_dir_root / name
        if not prompt_dir.exists():
            return None
        return [p.stem for p in prompt_dir.glob("*.j2")]

    def get_prompt_raw(self, name: str, version: str) -> str:
        """Return raw template file content for name and version."""
        template_path = f"{name}/{version}.j2"
        path = self._prompts_dir_root / template_path
        if not path.is_file():
            raise AppConfigError(f"Prompt file not found: {template_path}")
        return path.read_text(encoding="utf-8")


class LangfusePromptRegistry:
    """Resolve prompts from Langfuse by name + label; compile variables at runtime."""

    def __init__(self):
        langfuse = self._get_client()
        if langfuse is None:
            raise AppConfigError(
                "prompt_registry=langfuse requires Langfuse to be configured "
                "(LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)."
            )
        self._client = langfuse

    def _get_client(self):

        return get_langfuse_client()

    @staticmethod
    def _version_str_to_int(label: str) -> int:
        """Convert a Langfuse label to a version integer (e.g. v1 -> 1)."""
        version_regex = r"^v(\d+)$"
        matches = re.match(version_regex, label)
        if not matches:
            raise AppConfigError(f"Invalid version label: {label}")
        return int(matches.group(1))

    def register_prompt(
        self, name: str, prompt: str, version: str | None = None
    ) -> str:
        """Register a new prompt"""
        if version:
            logger.warning(
                "Cannot register a new prompt with a version for Langfuse prompt registry. Ignoring version."
            )
        registered_prompt = self._client.create_prompt(
            name=name,
            type="text",
            prompt=prompt,
        )
        return f"v{registered_prompt.version}"

    def prompt_versions(self, name: str) -> list[str] | None:
        """Return the versions of a prompt"""
        try:
            prompt_obj = self._client.get_prompt(name=name, label="latest")
        except Exception as e:
            # TODO: Handle this better later
            logger.warning(f"Failed to get prompt versions for {name}: {e}")

            return None
        return [f"v{p + 1}" for p in range(prompt_obj.version)]

    def get_prompt(
        self,
        name: str,
        version: str,
        context: dict | None = None,
    ) -> str:
        """Fetch prompt from Langfuse by name + label and compile with context."""
        prompt_obj = self._client.get_prompt(
            name, version=self._version_str_to_int(version)
        )
        # Langfuse uses {{variable}}; our context keys match (e.g. tool_list).
        # compile() accepts kwargs; pass context or empty dict.
        if context:
            return prompt_obj.compile(**context)
        return prompt_obj.compile()

    def get_prompt_raw(self, name: str, version: str) -> str:
        """Return raw content from Langfuse for key. Fetches by ref and returns prompt string."""
        prompt_obj = self._client.get_prompt(
            name, version=self._version_str_to_int(version)
        )
        # Text prompt: prompt_obj.prompt is the string
        return prompt_obj.prompt
