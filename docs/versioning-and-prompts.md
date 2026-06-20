# Versioning system: Copilot versions and prompt registry

This document describes how **copilot version config** and **prompt content** are versioned. **Only the Langfuse registry is supported** for normal operation; the app resolves all prompts from Langfuse at runtime. Local `.j2` files are for **authoring and testing only**; a sync script pushes them to Langfuse.

## Overview

- **Copilot version** = a named configuration (e.g. `v1`, `v2`) that selects which execution agents and which **prompt refs** (e.g. `base:v1`, `orchestrator:v2`) the app uses.
- **Prompt ref** = `name:version` (e.g. `base:v1`). The actual prompt text is resolved at runtime by the **Langfuse prompt registry** (fetch by name and version).
- **Langfuse registry (supported)** = prompts stored in Langfuse; the app fetches by name and version (integer), mapped from refs like `v1`, `v2`. Requires Langfuse configured.
- **Local prompts (testing only)** = Jinja `.j2` files under `app/prompts/{name}/{version}.j2`. Used for authoring, the prompt optimizer UI, and tests. A **sync script** registers missing versions in Langfuse so the app can use them.

---

## Copilot version config (YAML)

- **Location:** `services/backend/app/config/versions/{version_id}.yaml` (e.g. `v1.yaml`, `v2.yaml`).
- **Contents:** Pydantic-validated YAML: `version`, `execution_agents`, optional `tools`/`model`, and **`prompts`** (and per-agent `prompt_id`).

Example shape:

```yaml
version: v1
execution_agents:
  - domain: category
    name: category_agent
    description: "..."
    prompt_id: category_agent:v1
prompts:
  base: base:v1
  orchestrator: orchestrator:v1
```

- **Prompt refs:** Each value is `name:version` (e.g. `base:v1`). Keys in `prompts` are logical names (e.g. `base`, `orchestrator`); execution agents also have a `prompt_id` in the same form.
- **Loading:** `load_version_from_yaml(version_id)` reads the YAML and builds a **ResolvedVersion** that uses the **Langfuse prompt registry** to resolve content for those refs.

---

## Prompt registry: Langfuse only (local for testing)

At runtime the app uses **LangfusePromptRegistry** only. Prompts are fetched from Langfuse by **name** and **version** (integer parsed from refs like `v1`). Variables are compiled via Langfuse `compile()`. **Langfuse must be configured** (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST`).

- **Langfuse:** Prompt **name** matches our config name; **version** is an integer (1, 2, …). Ref `base:v1` maps to Langfuse prompt `base` version 1.
- **Local `.j2` files** exist under `app/prompts/{name}/{version}.j2` for **authoring and testing only**. The prompt optimizer UI reads and writes these files. They are not used at runtime unless you run with a local registry in tests.

**ResolvedVersion** (from `config.versioning`) holds the loaded YAML and the Langfuse registry. It resolves a **key** (e.g. `base` or an agent name) to `(name, version)` from the config, then calls `registry.get_prompt(name, version, context)` or `registry.get_prompt_raw(name, version)`.

---

## Syncing local prompts to Langfuse

Because the app uses **only Langfuse** at runtime, prompt versions should stay aligned between local files and Langfuse. The helper script **`services/backend/app/scripts/sync_prompt_registries.py`** synchronizes both ways:

1. **Discover required refs:** Scans `config/versions/*.yaml` and builds a prompt key → versions map (from `prompts.*` and each agent `prompt_id`).
2. **Check both registries:** For each required `(name, version)`, checks local (`app/prompts/name/version.j2`) and Langfuse.
3. **Copy missing versions:** If missing on one side but present on the other, copies the raw prompt content to the missing registry.
4. **Report gaps:** Prints versions still missing in either registry (or both) after sync.

So:

- **Two-way sync:** Local ↔ Langfuse for required versions in copilot config files.
- **Idempotent:** Safe to run repeatedly; only missing versions are created/copied.
- **Order-aware for Langfuse:** Missing remote versions are created in version order.

**Run (uv):** `cd services/backend/app && uv run python -m scripts.sync_prompt_registries --dry-run` (remove `--dry-run` to apply).

**Run (pnpm):**
- From repo root: `pnpm sync-prompt-registries:dry-run`
- Apply changes: `pnpm sync-prompt-registries`
- Remove `--dry-run` to apply changes.

**When to run:** After changing prompt refs in `config/versions/*.yaml`, after editing local prompt files, or after Langfuse prompt updates. Requires Langfuse env vars set (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST`).

---

## Prompt optimizer (UI)

The prompt optimizer UI **reads and writes local** `.j2` files only (it does not talk to Langfuse). Use it to edit prompts; then run the sync script to align local and Langfuse prompt versions used at runtime.

---

## Code references

| Concept | Location |
|--------|----------|
| Version YAML loading, ResolvedVersion | `services/backend/app/config/versioning.py` |
| LangfusePromptRegistry, Protocol (LocalPromptRegistry for tests) | `services/backend/app/config/prompt_registry.py` |
| Sync script | `services/backend/app/scripts/sync_prompt_registries.py` |
