"""Unit tests for scripts.sync_prompt_registries."""

from pathlib import Path

from scripts.sync_prompt_registries import (
    collect_prompt_maps,
    sync_prompt_versions,
)


class FakeRegistry:
    def __init__(self, prompts: dict[str, dict[str, str]]):
        self._prompts = {k: dict(v) for k, v in prompts.items()}
        self.register_calls: list[tuple[str, str]] = []

    def prompt_versions(self, name: str) -> list[str] | None:
        versions = sorted(self._prompts.get(name, {}).keys())
        return versions or None

    def get_prompt_raw(self, name: str, version: str) -> str:
        return self._prompts[name][version]

    def register_prompt(
        self,
        name: str,
        prompt: str,
        version: str | None = None,
    ) -> str:
        if version is None:
            raise AssertionError("Tests expect explicit version registration")
        self._prompts.setdefault(name, {})[version] = prompt
        self.register_calls.append((name, version))
        return version


class FakeLangfuseRegistry(FakeRegistry):
    """Mimics sequential Langfuse version creation."""

    def register_prompt(
        self,
        name: str,
        prompt: str,
        version: str | None = None,
    ) -> str:
        existing = self.prompt_versions(name) or []
        next_version = f"v{len(existing) + 1}"
        self._prompts.setdefault(name, {})[next_version] = prompt
        self.register_calls.append((name, next_version))
        return next_version


def test_collect_prompt_maps_reads_prompts_and_execution_agents(tmp_path: Path):
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()
    (versions_dir / "v1.yaml").write_text(
        """
version: "v1"
prompts:
  base: base:v2
execution_agents:
  - name: category_agent
    prompt_id: category_agent:v1
""",
        encoding="utf-8",
    )
    (versions_dir / "v2.yaml").write_text(
        """
version: "v2"
prompts:
  base: base:v3
""",
        encoding="utf-8",
    )

    result = collect_prompt_maps(versions_dir)

    assert result.errors == []
    assert result.key_to_versions["base"] == {"v2", "v3"}
    assert result.key_to_versions["category_agent"] == {"v1"}
    assert result.name_to_versions["base"] == {"v2", "v3"}
    assert result.name_to_versions["category_agent"] == {"v1"}


def test_sync_prompt_versions_copies_missing_from_local_to_langfuse():
    local = FakeRegistry({"base": {"v1": "local v1", "v2": "local v2"}})
    langfuse = FakeLangfuseRegistry({"base": {"v1": "remote v1"}})

    report = sync_prompt_versions(
        required_name_versions={"base": {"v1", "v2"}},
        local_registry=local,  # type: ignore[arg-type]
        langfuse_registry=langfuse,  # type: ignore[arg-type]
        dry_run=False,
    )

    assert report.unresolved == []
    assert ("base", "v2") in langfuse.register_calls
    assert langfuse.get_prompt_raw("base", "v2") == "local v2"


def test_sync_prompt_versions_copies_missing_from_langfuse_to_local():
    local = FakeRegistry({"base": {"v1": "local v1"}})
    langfuse = FakeLangfuseRegistry({"base": {"v1": "remote v1", "v2": "remote v2"}})

    report = sync_prompt_versions(
        required_name_versions={"base": {"v1", "v2"}},
        local_registry=local,  # type: ignore[arg-type]
        langfuse_registry=langfuse,  # type: ignore[arg-type]
        dry_run=False,
    )

    assert report.unresolved == []
    assert ("base", "v2") in local.register_calls
    assert local.get_prompt_raw("base", "v2") == "remote v2"


def test_sync_prompt_versions_reports_missing_in_both():
    local = FakeRegistry({"base": {"v1": "local v1"}})
    langfuse = FakeLangfuseRegistry({"base": {"v1": "remote v1"}})

    report = sync_prompt_versions(
        required_name_versions={"base": {"v1", "v2"}},
        local_registry=local,  # type: ignore[arg-type]
        langfuse_registry=langfuse,  # type: ignore[arg-type]
        dry_run=False,
    )

    assert len(report.unresolved) == 1
    unresolved = report.unresolved[0]
    assert unresolved.prompt_name == "base"
    assert unresolved.version == "v2"
    assert unresolved.missing_in == "both"
