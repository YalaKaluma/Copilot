# Online Evaluation (SKAI Copilot)

This document describes **online evaluation**: metrics collected during real user sessions and sent to Langfuse when a session completes. Online evaluation runs **per session**, not per turn—scores are computed once per completed session using the full conversation and final answer.

## Per session, not per turn

Online evaluation is triggered when an **orchestrator session** completes, not after each user or assistant turn.

- **When it runs:** After the orchestrator finishes (e.g. delivers a final answer or completes its workflow). The orchestrator service schedules `run_online_evals(trace_id)` as a background task when `session.is_complete` and Langfuse is enabled.
- **Scope of each run:** One evaluation run per session. The run uses:
  - **Input:** The first user message in the session (for LLM-as-judge context).
  - **Output:** The session’s final answer (`last_answer`).
  - **Events:** All orchestrator events for the session (tool calls, tool results, errors, etc.).
  - **Aggregates:** Total latency for the session, number of turns, plan completion, and steps.
- **Implication:** You do not get separate scores for each turn; you get one set of scores per session, summarizing the whole interaction.

## Flow

1. User interacts with the copilot (one or more turns).
2. When the orchestrator marks the session complete, the service checks Langfuse is enabled.
3. If enabled, it schedules `session.run_online_evals(trace_id)` in the background (non-blocking).
4. `run_online_evals` builds an `EvalRunResult` from the session (first user message, final answer, all events, latency, turns, plan completion, steps).
5. The same evaluators as offline run on this result (direct metrics + LLM-as-judge).
6. Scores are attached to the **trace** via Langfuse `create_score(...)`; `langfuse.flush()` is called in the task callback.

## Prerequisites

- **Langfuse:** Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and optionally `LANGFUSE_HOST`. If Langfuse is not configured, online evaluation is not scheduled.
- No extra user action: online evals run automatically when a session completes and Langfuse is configured.

## Evaluators (same as offline)

Online evaluation reuses the evaluators in `evaluation/evaluators.py` and `evaluation/online_evaluation.py`:

| Evaluator | Description |
|-----------|-------------|
| `direct_metrics` | Latency, number_of_turns, tool calls, tool_call_waste, tool_call_waste_ratio, error_count, has_errors, is_complete, plan_completion |
| `relevance` | Does the answer address the user's question? |
| `clarity` | Readability and coherence |
| `completeness` | Are all requested aspects covered? |
| `safety` | No harmful, biased, or off-policy content |
| `faithfulness` | Grounding in tool outputs (when events contain tool results) |
| `factual_accuracy_grounded` | Factual consistency with tool outputs (when events contain tool results) |
| `factual_accuracy` | Consistency with reference answer (online: no reference, so this evaluator is skipped in practice) |

Scores are written to the trace that was used for the session (the `trace_id` passed to `run_online_evals`).

## Implementation details

- **Orchestrator:** `OrchestratorSession.run_online_evals(trace_id)` in `copilot_agents/orchestrator.py` builds `EvalRunResult` and calls `evaluate_online(eval_result)`.
- **Online evaluation module:** `evaluation/online_evaluation.py` runs the evaluator list and attaches each score to the trace via `langfuse_client.create_score(...)`. No `flush()` in this module; the orchestrator service callback calls `langfuse_flush()` after the task completes.
- **Service:** `services/orchestrator_service.py` schedules the task after streaming or non-streaming invoke when the session is complete and Langfuse is enabled. Failures in the eval task are logged and do not affect the user response.

## Viewing results in Langfuse

1. Open your Langfuse project.
2. Go to **Traces** and find the trace for the completed session (e.g. by session or message id).
3. The trace has the full orchestrator span tree and **Scores** (e.g. `latency_seconds`, `relevance`, `clarity`) attached at the trace level.
4. Use **Score Analytics** to compare sessions or filter by score.

## Comparison with offline evaluation

| Aspect | Online | Offline |
|--------|--------|--------|
| **When** | When a real session completes | When you run `pnpm eval` (or `run_evaluations run_evals`) with a dataset |
| **Granularity** | One evaluation per **session** | One evaluation per **dataset item** (each item can be single- or multi-turn in the runner) |
| **Input** | First user message + full session state | Dataset item input (e.g. one user message per item) |
| **Reference answer** | Not used (no expected_output) | Optional per item (`expected_output.reference_answer`) |
| **Trace** | One trace per session (last turn's trace_id in multi-turn conversations) | One trace per item (last turn’s trace_id in multi-turn runner) |

See [evaluation-offline.md](evaluation-offline.md) for dataset format, how to run offline evals, and evaluator details.
