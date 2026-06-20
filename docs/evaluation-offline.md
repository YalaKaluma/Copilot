# Offline Evaluation (SKAI Copilot)

This document describes how to run **offline evaluations** for the SKAI copilot: load a dataset of questions, run the orchestrator per item, capture events and final response, and attach scores (LLM-as-judge, latency, etc.) to traces.

The offline eval workflow has **two paths**:

1. **create_dataset** — Accept a dataset path (JSONL), create a Langfuse dataset if it doesn’t exist, and append/upsert items. Use this to register or update a Langfuse dataset from a local file.
2. **run_evals** — Run evaluations. Requires `--dataset-name` and `--mode`:
   - **mode=langfuse**: Get the dataset from Langfuse by name; **fails if the dataset is not found**.
   - **mode=local**: Treat `--dataset-name` as a path to a local JSONL file; load and run evals locally (scores are still sent to Langfuse if configured).

When **Langfuse is disabled**, only **run_evals --mode local** is valid (with a file path as `--dataset-name`); scores are not sent. For evaluation during real user sessions (online, per session), see [evaluation-online.md](evaluation-online.md).

## Dataset format

Evaluation items are stored as **JSONL** (one JSON object per line). Each line must match the evaluation schema.

### Schema (per line)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | No | Unique id; if omitted, one is generated. Langfuse uses this for upserts. |
| `input` | string | Yes | User query for the evaluation item. |
| `chat_history` | array | No | Prior conversation as list of `{ "role": "user" \| "assistant" \| "system", "content": "<text>" }`. Default: `[]`. |
| `expected_output` | string | No | Ground truth / reference answer for evaluators (e.g. LLM-as-Judge). |
| `expected_steps` | array | No | Reserved for future orchestrator-step eval. |
| `expected_agents` | array | No | Reserved for future agent-selection eval. |
| `metadata` | object | No | e.g. `system_version`, `tags`, `source`. |

### Example (one line of a JSONL file)

```json
{"id": "item-1", "input": "What categories are available for analysis?", "chat_history": [], "expected_output": "Categories include product categories, subcategories, and brands.", "metadata": {"source": "sample"}}
```

A minimal sample dataset is at `services/backend/app/evaluation/datasets/sample.jsonl`.

## How to run evaluations

### Prerequisites

- Backend env: `OPENAI_API_KEY`, SKAI API credentials (see `environment/.env.backend.example`).
- Optional: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` (and optionally `LANGFUSE_HOST`). When set, **create_dataset** and **run_evals --mode langfuse** use Langfuse; **run_evals --mode local** can still run and will attach scores to traces if Langfuse is configured. When Langfuse is not set, only **run_evals --mode local** (with a file path) works; scores are not sent.

### Path 1: create_dataset

Create or update a Langfuse dataset from a local JSONL file. Creates the dataset if it doesn’t exist and appends items (by `id`; existing ids are skipped).

**From Docker (recommended):**

```bash
# Create/update Langfuse dataset from a JSONL file (dataset name = path stem if omitted)
docker compose exec backend uv run python -m evaluation.run_evaluations create_dataset \
  --dataset-path /app/evaluation/datasets/sample.jsonl

# With an explicit Langfuse dataset name
docker compose exec backend uv run python -m evaluation.run_evaluations create_dataset \
  --dataset-path /app/evaluation/datasets/sample.jsonl \
  --dataset-name copilot-sample
```

**From repo root (pnpm script):**

```bash
pnpm eval:create-dataset
```

(This uses the dataset path and name defined in `package.json`; e.g. `archetype1-descriptive.jsonl` → `archetype1-descriptive`.)

**From host (backend app directory):**

```bash
cd services/backend/app
PYTHONPATH=. uv run python -m evaluation.run_evaluations create_dataset \
  --dataset-path evaluation/datasets/sample.jsonl \
  --dataset-name my-eval-dataset
```

| Argument | Description |
|----------|-------------|
| `--dataset-path` | Path to JSONL file (required). |
| `--dataset-name` | Name for the Langfuse dataset (default: path stem, e.g. `sample` from `sample.jsonl`). |

### Path 2: run_evals

Run the orchestrator on each item, run evaluators, and attach scores. Requires **mode**: `langfuse` (dataset by name) or `local` (dataset from file path).

**From Docker (recommended):**

```bash
# Run against a Langfuse dataset by name (fails if dataset does not exist)
docker compose exec backend uv run python -m evaluation.run_evaluations run_evals \
  --dataset-name my-eval-dataset \
  --mode langfuse \
  --run-name my-run \
  --system-version "$(git rev-parse --short HEAD)"

# Run against a local JSONL file (path inside container)
docker compose exec backend uv run python -m evaluation.run_evaluations run_evals \
  --dataset-name /app/evaluation/datasets/sample.jsonl \
  --mode local \
  --run-name my-run \
  --limit 5
```

**From repo root (pnpm script):**

```bash
# Runs run_evals with dataset-name archetype1-descriptive, mode langfuse
pnpm eval
```

**From host (backend app directory):**

```bash
cd services/backend/app
PYTHONPATH=. uv run python -m evaluation.run_evaluations run_evals \
  --dataset-name evaluation/datasets/sample.jsonl \
  --mode local \
  --run-name my-run \
  --limit 5
```

| Argument | Description |
|----------|-------------|
| `--dataset-name` | Langfuse dataset name (mode=langfuse) or path to JSONL file (mode=local) (required). |
| `--mode` | `langfuse` or `local` (required). |
| `--run-name` | Name for this experiment run (default: `copilot-eval-<timestamp>`). |
| `--system-version` | Optional tag, e.g. git SHA, for reproducibility. |
| `--limit` | Max number of items to run (default: all). |

## What each path does

### create_dataset

- Loads items from the JSONL file at `--dataset-path`.
- Requires Langfuse (exits with an error if Langfuse is not configured).
- Creates a Langfuse dataset with the given name (or path stem) if it does not exist.
- Appends items to the dataset; items already present (by `id`) are skipped.
- Does **not** run the orchestrator or evaluators.

### run_evals

**mode=langfuse**

- Fetches the Langfuse dataset by `--dataset-name`. **Fails if the dataset does not exist** (no auto-creation).
- Runs the experiment via Langfuse’s native runner: `dataset.run_experiment(name=..., task=..., evaluators=[])`. For each item, the task runs the orchestrator, runs evaluators internally, attaches scores to the trace, then returns only the display text so the Langfuse UI shows just the assistant answer. A **dataset run** is created in Langfuse for comparison in the UI.

**mode=local**

- Loads items from the JSONL file at `--dataset-name` (treated as a path). Fails if the file does not exist.
- Runs the orchestrator per item and evaluators; if Langfuse is configured, scores are attached to traces. If Langfuse is disabled, scores are not sent.

**Task and evaluators (both modes)**

- For each item, the **runner** creates an orchestrator session and runs it. A **trace** is created per run (via Langfuse `create_trace_id`); the result’s `trace_id` is used for score attachment.
- Item-level evaluators run with the full run result (`input`, `content`, `events`, `expected_output`, `metadata`, etc.). Scores are attached to the corresponding trace.
- **Clarification handling:** If the orchestrator emits `request_info`, the runner injects a reply and continues up to 4 turns; then stops.

Traces are tagged with `run_name` and `system_version` in metadata so you can filter by run in the Langfuse UI.

## Viewing results in Langfuse

1. Open your Langfuse project (e.g. https://cloud.langfuse.com).
2. Go to **Traces** and filter by metadata `run_name` (or `system_version`) to see traces for a given run.
3. Each trace has the full orchestrator span tree and **Scores** (e.g. `latency_seconds`, `quality`) attached to the trace.
4. Use **Score Analytics** to compare runs or filter by score.

## Evaluators (no expected values)

The following evaluators do **not** require `expected_output` (reference answer, expected steps, or expected agents), per the [AI Copilot Evaluation Framework](https://www.notion.so/AI-Copilot-Evaluation-Framework-3030de3387ea8125b424d90c987a195a):

| Evaluator | Description | When it runs |
|-----------|-------------|--------------|
| `direct_metrics` | Latency, turns, tool calls, tool_call_waste (repeated same params), waste_ratio, error count, has_errors, completion, plan_completion | Always |
| `relevance` | Does the answer address the user's question? | Always |
| `clarity` | Readability and coherence | Always |
| `completeness` | Are all requested aspects covered? | Always |
| `safety` | No harmful, biased, or off-policy content | Always |
| `faithfulness` | Grounding in tool outputs (no hallucination) | When events contain tool results |
| `factual_accuracy_grounded` | Factual consistency with tool outputs | When events contain tool results |
| `factual_accuracy` | Consistency with reference answer | Only when `expected_output.reference_answer` is set |

The runner supports multi-turn items (up to 4 turns) when the orchestrator emits `request_info`; see "What each path does" above. For online evaluation (per real user session), see [evaluation-online.md](evaluation-online.md).

## Extending the framework

- **New metrics**: add fields to `expected_output` (e.g. `expected_steps`) and implement a new evaluator in `evaluation/evaluators.py` that returns `Evaluation(name="...", value=..., comment=...)`, then add it to `EVALUATORS` in `run_evaluations.py`; scores are attached to traces in `_evaluate_and_attach_scores`.
- **Clarification handling**: the runner already injects a reply when the orchestrator emits `request_info` (first suggested option or a default message) and continues up to 4 turns. A configurable `default_clarification_reply` could be added for customization.
- **Token/cost**: when the LLM client exposes usage, add it to the runner result and an optional cost evaluator.

## References

- [evaluation-online.md](evaluation-online.md): online evaluation (per session, not per turn).
- [AI Copilot Evaluation Framework](https://www.notion.so/AI-Copilot-Evaluation-Framework-3030de3387ea8125b424d90c987a195a) (Notion): dimensions (final answer, orchestrator steps, agent selection, system metrics).
- [Langfuse: Experiments via SDK](https://langfuse.com/docs/evaluation/experiments/experiments-via-sdk).
- [Langfuse: LLM-as-a-Judge](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge).
