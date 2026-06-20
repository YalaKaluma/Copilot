"""Dataset source resolution for offline evaluation.

Two workflows:
- create_dataset: load JSONL from path, create Langfuse dataset if not existing, append/upsert items.
- run_evals: mode=langfuse get dataset by name (fail if not found); mode=local load from path.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from packages.langfuse import get_langfuse_client
from schemas.evaluation import (
    EvalDatasetItem,
    LangfuseEvalDataset,
    LocalEvalDataset,
)

from core.logging import get_logger

logger = get_logger(__name__)


def load_jsonl(path: Path) -> list[EvalDatasetItem]:
    """Load JSONL file; each line is a JSON object (dataset item)."""
    items = []
    with path.open() as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(EvalDatasetItem.model_validate_json(line))
            except (json.JSONDecodeError, ValidationError) as e:
                logger.warning("Skip line %s: %s", i + 1, e)
    return items


def create_langfuse_dataset_from_path(
    dataset_path: Path,
    dataset_name: str | None = None,
) -> LangfuseEvalDataset:
    """Load JSONL from path, create Langfuse dataset if not existing, append/upsert items.

    Args:
        dataset_path: Path to JSONL file.
        dataset_name: Name for the Langfuse dataset. Defaults to path.stem.

    Returns:
        LangfuseEvalDataset with the created/updated dataset.

    Raises:
        FileNotFoundError: If dataset_path does not exist.
        RuntimeError: If Langfuse is not configured.
    """
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    langfuse = get_langfuse_client()
    if not langfuse:
        raise RuntimeError("Langfuse is not configured; cannot create dataset")
    items = load_jsonl(dataset_path)
    name = dataset_name or dataset_path.stem
    try:
        dataset = langfuse.get_dataset(name)
    except Exception as e:
        if _is_404(e):
            langfuse.create_dataset(
                name=name,
                description="Registered from local JSONL for evaluation",
            )
            dataset = langfuse.get_dataset(name)
        else:
            raise

    existing_items = dataset.items
    existing_ids = {item.id for item in existing_items}

    for item in items:
        if item.id in existing_ids:
            continue
        metadata: dict[str, Any] = item.metadata or {}
        if item.expected_agents:
            metadata["expected_agents"] = [
                {"name": agent.name, "tools": ",".join(agent.tools)}
                for agent in item.expected_agents
            ]
        if item.expected_steps:
            metadata["expected_steps"] = item.expected_steps
        if item.expected_archetype is not None:
            metadata["expected_archetype"] = item.expected_archetype
        if item.expected_answer_criteria:
            metadata["expected_answer_criteria"] = item.expected_answer_criteria
        if item.chat_history:
            metadata["chat_history"] = [
                e.model_dump(mode="json") for e in item.chat_history
            ]
        metadata["answerable_by_dataset"] = item.answerable_by_dataset
        langfuse.create_dataset_item(
            dataset_name=dataset.name,
            input=item.input,
            expected_output=item.expected_output or item.expected_answer_criteria,
            metadata=metadata,
            id=item.id,
        )

    dataset = langfuse.get_dataset(name)
    return LangfuseEvalDataset(type="langfuse_dataset", dataset=dataset)


def get_langfuse_dataset_by_name(name: str) -> LangfuseEvalDataset:
    """Get a Langfuse dataset by name. Fails if not found or Langfuse not configured.

    Raises:
        RuntimeError: If Langfuse is not configured.
        FileNotFoundError: If dataset does not exist (404).
    """
    langfuse = get_langfuse_client()
    if not langfuse:
        raise RuntimeError("Langfuse is not configured")
    try:
        dataset = langfuse.get_dataset(name)
    except Exception as e:
        if _is_404(e):
            raise FileNotFoundError(f"Langfuse dataset not found: {name}") from e
        raise
    return LangfuseEvalDataset(type="langfuse_dataset", dataset=dataset)


def load_local_dataset(
    dataset_name: str,
    dataset_path: Path | None = None,
    limit: int | None = None,
) -> LocalEvalDataset:
    """Load evaluation items from a local JSONL file.

    Raises:
        FileNotFoundError: If dataset_path does not exist.
    """
    dataset_path = (
        dataset_path or Path(__file__).parent / "datasets" / f"{dataset_name}.jsonl"
    )
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")
    items = load_jsonl(dataset_path)
    if limit is not None:
        items = items[:limit]
    return LocalEvalDataset(type="local_dataset", items=items)


def _is_404(e: Exception) -> bool:
    """Heuristic: treat as 404 if message or repr mentions 404 or Not Found."""
    msg = (getattr(e, "message", "") or str(e) or "").lower()
    if "404" in msg or "not found" in msg:
        return True
    # httpx/requests style
    if (
        hasattr(e, "response")
        and getattr(getattr(e, "response", None), "status_code", None) == 404
    ):
        return True
    return False
