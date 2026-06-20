"""
Eval workflow: two paths.

1. create_dataset: accept dataset path, create Langfuse dataset if not existing, append items.
2. run_evals: accept dataset_name and mode (langfuse | local).
   - mode=langfuse: get dataset from Langfuse by name; fail if not available.
   - mode=local: load dataset from path (dataset_name is path) and run locally.

Run from backend app directory with env loaded (e.g. docker compose exec backend):
  uv run python -m evaluation.run_experiment create_dataset --dataset-path /path/to/items.jsonl [--dataset-name my-ds]
  uv run python -m evaluation.run_experiment run_evals --dataset-name my-ds --mode langfuse [--run-name my-run]
  uv run python -m evaluation.run_experiment run_evals --dataset-name /path/to/items.jsonl --mode local [--run-name my-run]
"""

import argparse
import asyncio
from pathlib import Path
import sys
import time
import uuid
from typing import Any, Literal

from langfuse._client.datasets import DatasetItemClient
from packages.langfuse.client import flush as langfuse_flush, get_langfuse_client
from schemas.evaluation import EvalDatasetItem, EvalRunResult
from config.versioning import ResolvedVersion, get_copilot_version
from services.llm.openai_client import AsyncOpenaiClient
from evaluation.dataset_source import (
    create_langfuse_dataset_from_path,
    get_langfuse_dataset_by_name,
    load_local_dataset,
)
from evaluation.runner import run_orchestrator_for_item
from evaluation.evaluators import (
    EvaluatorProtocol,
    direct_metrics,
    llm_judge_evaluator_clarity,
    llm_judge_evaluator_completeness,
    llm_judge_evaluator_factual_accuracy,
    llm_judge_evaluator_factual_accuracy_grounded,
    llm_judge_evaluator_faithfulness,
    llm_judge_evaluator_relevance,
    llm_judge_evaluator_safety,
    llm_judge_evaluator_answer_criteria,
    archetype_classification_evaluator,
)
from services.skai_api import SKAIApi
from services.skai_api_v2.client import SkaiApiV2Client
from services.skai_auth_service import get_skai_auth_service
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)

EVALUATORS: list[EvaluatorProtocol] = [
    direct_metrics,
    llm_judge_evaluator_factual_accuracy,
    llm_judge_evaluator_factual_accuracy_grounded,
    llm_judge_evaluator_relevance,
    llm_judge_evaluator_clarity,
    llm_judge_evaluator_completeness,
    llm_judge_evaluator_safety,
    llm_judge_evaluator_faithfulness,
    llm_judge_evaluator_answer_criteria,
    archetype_classification_evaluator,
]


async def _get_skai_service_for_eval(
    resolved_version: ResolvedVersion,
) -> SKAIApi | SkaiApiV2Client:
    """Return the version-appropriate SKAI client for evaluations."""
    settings = get_settings()
    if settings.skai_user_name and settings.skai_password:
        skai_auth = get_skai_auth_service()
        # Same credentials as FE POST /skai/auth/login; strip to match form input
        username = (settings.skai_user_name or "").strip()
        password = (settings.skai_password or "").strip()
        token = await skai_auth.get_token_for_credentials(username, password)
        extra_headers: dict[str, str] = {}
        if settings.skai_api_origin:
            extra_headers["Origin"] = settings.skai_api_origin
        if settings.skai_api_referer:
            extra_headers["Referer"] = settings.skai_api_referer
        if settings.skai_api_user_agent:
            extra_headers["User-Agent"] = settings.skai_api_user_agent
        if not extra_headers.get("Origin") or not extra_headers.get("Referer"):
            logger.warning(
                "SKAI API often requires Origin and Referer. Set SKAI_API_ORIGIN and "
                "SKAI_API_REFERER to the SKAI client app URL (e.g. from environment/.env.backend.example)."
            )
        logger.info("Using SKAI credential auth (SKAI_USER_NAME / SKAI_PASSWORD)")
        if (
            resolved_version.config.orchestrator_version
            == "single_agent_promo_orchestrator"
        ):
            return SkaiApiV2Client(
                base_url=settings.skai_api_url,
                api_key=settings.skai_api_key,
                auth_token=token,
                extra_headers=extra_headers,
            )
        return SKAIApi(
            base_url=settings.skai_api_url,
            api_key=settings.skai_api_key,
            auth_token=token,
            extra_headers=extra_headers,
        )
    raise RuntimeError("SKAI user name and password are not set")


async def _run_tasks_with_tracing(
    data: list[EvalDatasetItem],
    *,
    llm_service: AsyncOpenaiClient,
    skai_service: SKAIApi | SkaiApiV2Client,
    resolved_version: ResolvedVersion,
    # run_name: str,
    # system_version: str | None,
) -> list[EvalRunResult]:
    """
    Run orchestrator for each item. Trace is created inside the runner; returns (item, result, trace_id).
    """
    results: list[EvalRunResult] = []

    tasks = [
        run_orchestrator_for_item(
            item,
            llm_service=llm_service,
            skai_service=skai_service,
            # run_name=run_name,
            # system_version=system_version or "unspecified",
            run_id=str(uuid.uuid4()),
            resolved_version=resolved_version,
        )
        for item in data
        if item.answerable_by_dataset
    ]

    results = await asyncio.gather(*tasks)

    return results


async def _evaluate_and_attach_scores(
    result: EvalRunResult,
) -> None:
    """Evaluate the result and attach scores to the trace."""
    tasks = [evaluator(result) for evaluator in EVALUATORS]
    evs_results = await asyncio.gather(*tasks)

    evs = [ev for ev_results in evs_results for ev in ev_results or []]

    langfuse_client = get_langfuse_client()
    if not langfuse_client:
        logger.error("Langfuse not enabled, skipping score attachment")
        return
    if not result.trace_id:
        logger.error("Trace ID not found, skipping score attachment")
        return
    for ev in evs:
        if ev is None:
            continue
        langfuse_client.create_score(
            trace_id=result.trace_id,
            name=ev.name,
            value=ev.value,
            comment=ev.comment,
            data_type="NUMERIC",
        )
    langfuse_flush()


def _langfuse_item_to_eval_item(item: DatasetItemClient) -> EvalDatasetItem:
    """Convert Langfuse dataset item (object or dict) to EvalDatasetItem (flat schema)."""

    metadata = (
        item.metadata if item.metadata and isinstance(item.metadata, dict) else {}
    )
    meta_copy = dict(metadata)

    eval_item_dict = {
        "id": item.id,
        "input": str(item.input),
        "chat_history": meta_copy.pop("chat_history", []),
        "expected_output": (
            None if item.expected_output is None else str(item.expected_output)
        ),
        "expected_steps": meta_copy.pop("expected_steps", []),
        "expected_agents": meta_copy.pop("expected_agents", []),
        "expected_archetype": meta_copy.pop("expected_archetype", None),
        "expected_answer_criteria": meta_copy.pop("expected_answer_criteria", None),
        "answerable_by_dataset": meta_copy.pop("answerable_by_dataset", True),
        "metadata": meta_copy,
    }

    return EvalDatasetItem(**eval_item_dict)


def _make_langfuse_task(
    llm_service: AsyncOpenaiClient,
    skai_service: SKAIApi | SkaiApiV2Client,
    resolved_version: ResolvedVersion,
):
    """Return an async task for dataset.run_experiment.

    The task runs the orchestrator, runs evaluators (with full EvalRunResult), attaches
    scores to the trace, then returns only the display text (content). Langfuse stores
    and shows that string in the UI; evaluators still see the full result because we
    run them inside the task before returning.
    """

    async def run_item(*, item: DatasetItemClient, **kwargs: Any) -> str | None:
        eval_item = _langfuse_item_to_eval_item(item)
        if not eval_item.answerable_by_dataset:
            logger.warning(
                "Item %s is not answerable by the dataset, skipping", eval_item.id
            )
            return None
        result = await run_orchestrator_for_item(
            eval_item,
            llm_service=llm_service,
            skai_service=skai_service,
            run_id=str(uuid.uuid4()),
            resolved_version=resolved_version,
        )
        await _evaluate_and_attach_scores(result)
        return result.content

    return run_item


def _cmd_create_dataset(args: argparse.Namespace) -> int:
    """Create/update Langfuse dataset from JSONL path; append items."""
    try:
        source = create_langfuse_dataset_from_path(
            args.dataset_path,
            dataset_name=args.dataset_name,
        )
        logger.info(
            "Dataset created/updated: %s (%s items)",
            source.dataset.name,
            len(source.dataset.items),
        )
        return 0
    except FileNotFoundError as e:
        logger.error("Dataset file not found: %s", e)
        return 1
    except RuntimeError as e:
        logger.error("Langfuse not configured: %s", e)
        return 1


def run_evals(
    dataset_name: str,
    mode: Literal["langfuse", "local"],
    run_name: str,
    system_version: str | None,
    limit: int | None,
) -> int:
    """Run evals: mode=langfuse get dataset by name (fail if missing); mode=local load from path."""

    settings = get_settings()
    run_name = run_name or f"copilot-eval-{int(time.time())}"
    system_version = system_version or settings.skai_copilot_version
    resolved_version = get_copilot_version(system_version, no_cache=False)
    llm_service = AsyncOpenaiClient()
    if mode == "langfuse":
        try:
            dataset_source = get_langfuse_dataset_by_name(dataset_name)
        except FileNotFoundError as e:
            logger.error("Langfuse dataset not found: %s", e)
            return 1
        except RuntimeError as e:
            logger.error("Langfuse not configured: %s", e)
            return 1
        dataset = dataset_source.dataset

        async def _run_langfuse() -> None:
            skai_service = await _get_skai_service_for_eval(resolved_version)
            task_fn = _make_langfuse_task(llm_service, skai_service, resolved_version)
            result = dataset.run_experiment(
                name=run_name,
                description=system_version or "Offline evaluation run",
                task=task_fn,
                evaluators=[],  # we handle this in the task itself so that we can evalaute on the full result
                metadata={
                    "system_version": resolved_version.config.version,
                },
            )
            logger.info(
                "Experiment result: %s",
                getattr(result, "format", lambda: str(result))(),
            )

        logger.info("Starting evaluation (Langfuse): run_name=%s", run_name)
        asyncio.run(_run_langfuse())
    else:

        try:
            dataset_source_local = load_local_dataset(
                dataset_name=dataset_name,
                limit=limit,
            )
        except FileNotFoundError as e:
            logger.error("Dataset file not found: %s", e)
            return 1
        items = dataset_source_local.items
        if not items:
            logger.error("No items loaded from %s", dataset_name)
            return 1

        async def _run_local() -> None:
            skai_service = await _get_skai_service_for_eval(resolved_version)
            results = await _run_tasks_with_tracing(
                items,
                llm_service=llm_service,
                skai_service=skai_service,
                resolved_version=resolved_version,
            )
            for result in results:
                await _evaluate_and_attach_scores(result)

        logger.info(
            "Starting evaluation (local): run_name=%s items=%s", run_name, len(items)
        )
        asyncio.run(_run_local())

    langfuse_flush()
    logger.info("Evaluation finished. Run name: %s", run_name)
    return 0


def _cmd_run_evals(args: argparse.Namespace) -> int:
    """Run evals: mode=langfuse get dataset by name (fail if missing); mode=local load from path."""
    run_name = args.run_name or f"copilot-eval-{int(time.time())}"
    system_version = args.system_version

    return run_evals(args.dataset_name, args.mode, run_name, system_version, args.limit)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Eval workflow: create_dataset or run_evals.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # create_dataset
    create_parser = subparsers.add_parser(
        "create_dataset",
        help="Create/update Langfuse dataset from JSONL path; append items.",
    )
    create_parser.add_argument(
        "--dataset-path",
        type=Path,
        required=True,
        help="Path to JSONL file.",
    )
    create_parser.add_argument(
        "--dataset-name",
        type=str,
        default=None,
        help="Name for the Langfuse dataset (default: path stem).",
    )
    create_parser.set_defaults(func=_cmd_create_dataset)

    # run_evals
    run_parser = subparsers.add_parser(
        "run_evals", help="Run evals: langfuse (by name) or local (by path)."
    )
    run_parser.add_argument(
        "--mode",
        type=str,
        choices=["langfuse", "local"],
        default="langfuse",
        help="langfuse: get dataset from Langfuse (fail if not found). local: load from path.",
    )
    run_parser.add_argument(
        "--run-name",
        type=str,
        default=None,
        help="Name for this experiment run (default: copilot-eval-<timestamp>).",
    )
    run_parser.add_argument(
        "--dataset-name",
        type=str,
        required=True,
        help="Name of the dataset to run (default: None).",
    )
    run_parser.add_argument(
        "--system-version",
        type=str,
        default=None,
        help="Optional system version (e.g. git SHA) to tag the run.",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of items to run (default: all).",
    )
    run_parser.set_defaults(func=_cmd_run_evals)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
