"""Synchronize prompt versions between local files and Langfuse.

Workflow:
1. Read all `config/versions/*.yaml` files.
2. Build prompt key -> versions map and prompt name -> versions map.
3. For each required prompt version, ensure it exists in both registries:
   - LocalPromptRegistry (app/prompts/<name>/<version>.j2)
   - LangfusePromptRegistry
4. Copy the missing side from the side that has content.
5. Report any versions still not present in both registries.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable


from config.prompt_registry import (
    LangfusePromptRegistry,
    LocalPromptRegistry,
)
from config.versioning import load_version_from_yaml

APP_ROOT = Path(__file__).resolve().parents[1]


VERSION_LABEL_RE = re.compile(r"^v(\d+)$")


def _version_sort_key(version: str) -> int:
    match = VERSION_LABEL_RE.match(version)
    if match:
        return int(match.group(1))
    return 10**9


def _prompt_id_to_name_and_version(prompt_id: str) -> tuple[str, str] | None:
    if ":" not in prompt_id:
        return None
    name, version = prompt_id.split(":", 1)
    if not name or not version:
        return None
    return name, version


def _next_numeric_version(versions: set[str]) -> int:
    numeric_versions = [
        int(match.group(1))
        for version in versions
        if (match := VERSION_LABEL_RE.match(version)) is not None
    ]
    return (max(numeric_versions) + 1) if numeric_versions else 1


@dataclass
class PromptMaps:
    key_to_versions: dict[str, set[str]]
    errors: list[str]


def collect_prompt_maps(versions_dir: Path) -> PromptMaps:
    key_to_versions: dict[str, set[str]] = defaultdict(set)
    errors: list[str] = []

    for yaml_file in sorted(versions_dir.glob("*.yaml")):
        version = yaml_file.stem.split(".")[0]

        resolved_version = load_version_from_yaml(version)

        for prompt_key, prompt_id in resolved_version.config.prompts.items():
            prompt_name_version = _prompt_id_to_name_and_version(prompt_id)
            if not prompt_name_version:
                errors.append(
                    f"{yaml_file}: invalid prompt_id for key={prompt_key!r}: {prompt_id!r}"
                )
                continue
            prompt_name, prompt_version = prompt_name_version
            key_to_versions[prompt_name].add(prompt_version)

        for agent in resolved_version.config.execution_agents:
            prompt_name_version = _prompt_id_to_name_and_version(agent.prompt_id)
            if not prompt_name_version:
                errors.append(
                    f"{yaml_file}: invalid prompt_id for agent={agent.name!r}: {agent.prompt_id!r}"
                )
                continue
            prompt_name, prompt_version = prompt_name_version
            key_to_versions[prompt_name].add(prompt_version)

    return PromptMaps(
        key_to_versions=dict(key_to_versions),
        errors=errors,
    )


@dataclass
class SyncRecord:
    prompt_name: str
    version: str
    missing_in: str
    action: str
    detail: str = ""


@dataclass
class SyncReport:
    actions: list[SyncRecord]
    unresolved: list[SyncRecord]


def sync_prompt_versions(
    required_name_versions: dict[str, set[str]],
    local_registry: LocalPromptRegistry,
    langfuse_registry: LangfusePromptRegistry,
    *,
    dry_run: bool,
) -> SyncReport:
    actions: list[SyncRecord] = []
    unresolved: list[SyncRecord] = []

    for prompt_name in sorted(required_name_versions.keys()):
        required_versions = sorted(
            required_name_versions[prompt_name], key=lambda v: _version_sort_key(v)
        )
        local_versions = set(local_registry.prompt_versions(prompt_name) or [])
        langfuse_versions = set(langfuse_registry.prompt_versions(prompt_name) or [])

        for version in required_versions:
            local_has = version in local_versions
            langfuse_has = version in langfuse_versions

            if local_has and langfuse_has:
                continue

            if local_has and not langfuse_has:
                requested_match = VERSION_LABEL_RE.match(version)
                next_remote = _next_numeric_version(langfuse_versions)
                if requested_match is None:
                    unresolved.append(
                        SyncRecord(
                            prompt_name=prompt_name,
                            version=version,
                            missing_in="langfuse",
                            action="skipped",
                            detail="unsupported version label for Langfuse sync",
                        )
                    )
                    continue
                requested_number = int(requested_match.group(1))
                if requested_number != next_remote:
                    unresolved.append(
                        SyncRecord(
                            prompt_name=prompt_name,
                            version=version,
                            missing_in="langfuse",
                            action="skipped",
                            detail=(
                                "cannot create non-sequential Langfuse version "
                                f"(next is v{next_remote})"
                            ),
                        )
                    )
                    continue

                if dry_run:
                    actions.append(
                        SyncRecord(
                            prompt_name=prompt_name,
                            version=version,
                            missing_in="langfuse",
                            action="copy-local-to-langfuse",
                            detail="dry-run",
                        )
                    )
                    langfuse_versions.add(version)
                    continue

                try:
                    prompt_content = local_registry.get_prompt_raw(prompt_name, version)
                    created_version = langfuse_registry.register_prompt(
                        prompt_name, prompt_content, version=version
                    )
                except Exception as exc:
                    unresolved.append(
                        SyncRecord(
                            prompt_name=prompt_name,
                            version=version,
                            missing_in="langfuse",
                            action="failed",
                            detail=str(exc),
                        )
                    )
                    continue

                if created_version != version:
                    unresolved.append(
                        SyncRecord(
                            prompt_name=prompt_name,
                            version=version,
                            missing_in="langfuse",
                            action="failed",
                            detail=(
                                f"created unexpected Langfuse version {created_version!r}"
                            ),
                        )
                    )
                    continue

                langfuse_versions.add(version)
                actions.append(
                    SyncRecord(
                        prompt_name=prompt_name,
                        version=version,
                        missing_in="langfuse",
                        action="copy-local-to-langfuse",
                    )
                )
                continue

            if langfuse_has and not local_has:
                if dry_run:
                    actions.append(
                        SyncRecord(
                            prompt_name=prompt_name,
                            version=version,
                            missing_in="local",
                            action="copy-langfuse-to-local",
                            detail="dry-run",
                        )
                    )
                    local_versions.add(version)
                    continue

                try:
                    prompt_content = langfuse_registry.get_prompt_raw(
                        prompt_name, version
                    )
                    local_registry.register_prompt(
                        prompt_name, prompt_content, version=version
                    )
                except Exception as exc:
                    unresolved.append(
                        SyncRecord(
                            prompt_name=prompt_name,
                            version=version,
                            missing_in="local",
                            action="failed",
                            detail=str(exc),
                        )
                    )
                    continue

                local_versions.add(version)
                actions.append(
                    SyncRecord(
                        prompt_name=prompt_name,
                        version=version,
                        missing_in="local",
                        action="copy-langfuse-to-local",
                    )
                )
                continue

            unresolved.append(
                SyncRecord(
                    prompt_name=prompt_name,
                    version=version,
                    missing_in="both",
                    action="missing-in-both",
                )
            )

    return SyncReport(actions=actions, unresolved=unresolved)


def _print_key_map(key_to_versions: dict[str, set[str]]) -> None:
    print("\nPrompt key -> versions map:")
    for key in sorted(key_to_versions.keys()):
        versions = key_to_versions[key]
        print(f"  - {key}: {', '.join(versions)}")


def _print_errors(errors: Iterable[str]) -> None:
    errors = list(errors)
    if not errors:
        return
    print("\nParse warnings:")
    for error in errors:
        print(f"  - {error}")


def _print_sync_report(report: SyncReport) -> None:
    print("\nSync actions:")
    if not report.actions:
        print("  - none")
    for action in report.actions:
        suffix = f" ({action.detail})" if action.detail else ""
        print(
            f"  - {action.prompt_name}:{action.version} | {action.action} | "
            f"missing in {action.missing_in}{suffix}"
        )

    print("\nVersions not present in both registries:")
    if not report.unresolved:
        print("  - none")
    for unresolved in report.unresolved:
        suffix = f" ({unresolved.detail})" if unresolved.detail else ""
        print(
            f"  - {unresolved.prompt_name}:{unresolved.version} | {unresolved.action} | "
            f"missing in {unresolved.missing_in}{suffix}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize prompt versions between local prompt files and Langfuse "
            "based on all config/versions/*.yaml references."
        )
    )
    parser.add_argument(
        "--versions-dir",
        type=Path,
        default=APP_ROOT / "config" / "versions",
        help="Directory containing copilot version YAML files.",
    )
    parser.add_argument(
        "--prompts-dir",
        type=Path,
        default=APP_ROOT / "prompts",
        help="Directory containing local prompt files (name/version.j2).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without writing to either registry.",
    )
    args = parser.parse_args()

    prompt_maps = collect_prompt_maps(args.versions_dir)
    _print_key_map(prompt_maps.key_to_versions)
    _print_errors(prompt_maps.errors)

    local_registry = LocalPromptRegistry(args.prompts_dir)
    langfuse_registry = LangfusePromptRegistry()

    report = sync_prompt_versions(
        prompt_maps.key_to_versions,
        local_registry,
        langfuse_registry,
        dry_run=args.dry_run,
    )
    _print_sync_report(report)

    return 1 if report.unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
