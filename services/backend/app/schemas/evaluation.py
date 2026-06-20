"""Evaluation dataset and run schemas.

Aligns with Langfuse DatasetItem: input, expected_output, metadata.
Used for local JSONL datasets and when syncing to Langfuse.
"""

from dataclasses import dataclass
from typing import Literal
from langfuse._client.datasets import DatasetClient
from pydantic import BaseModel, Field

from models.copilot.orchestrators import OrchestratorEvent
from models.copilot.base import ChatEvent


class Agent(BaseModel):
    """Expected agent for an evaluation item."""

    name: str = Field(..., description="Name of the agent")
    tools: list[str] = Field(..., description="Tools used by the agent")


class EvalDatasetItem(BaseModel):
    """One evaluation case: input messages and optional expected output.

    id is optional; if omitted, generate (e.g. UUID) when pushing to Langfuse.
    """

    id: str | None = Field(
        default=None,
        description="Unique id; Langfuse uses this for upserts. Omit to auto-generate.",
    )
    input: str = Field(..., description="User query for the evaluation item")
    chat_history: list[ChatEvent] = Field(
        default_factory=list, description="Chat history for the evaluation item"
    )

    expected_output: str | None = Field(
        default=None,
        description="Ground truth / reference for evaluators",
    )
    expected_steps: list[str] | None = Field(
        default=None,
        description="Reserved for future orchestrator-step eval (Section 2 of framework)",
    )
    expected_agents: list[Agent] | None = Field(
        default=None,
        description="Reserved for future agent-selection eval (Section 3 of framework)",
    )
    expected_archetype: str | None = Field(
        default=None,
        description="Expected archetype of the evaluation item",
    )
    expected_answer_criteria: list[str] | None = Field(
        default=None,
        description="List of criteria to evaluate the answer (what a good response should satisfy)",
    )
    metadata: dict[str, str | int | float | bool] | None = Field(
        default=None,
        description="e.g. system_version, tags, source",
    )
    answerable_by_dataset: bool = Field(
        default=True,
        description="Whether the answer is answerable by the dataset",
    )


LLM_JUDGE_METRIC_TYPE = Literal[
    "factual_accuracy",
    "factual_accuracy_grounded",
    "relevance",
    "clarity",
    "completeness",
    "safety",
    "faithfulness",
    "answer_criteria",
]


class LLMJudgeMetrics(BaseModel):
    """Metrics for the LLM-as-judge evaluator."""

    name: LLM_JUDGE_METRIC_TYPE = Field(..., description="Name of the metric")
    rating: Literal["ExtremelyPoor", "Poor", "Fair", "Good", "Excellent"] = Field(
        ...,
        description="Rating of the evaluation item adhering to the rubric",
    )
    reasoning: str = Field(..., description="Reasoning of the evaluation item")

    @property
    def score(self) -> float:
        """Score of the metric from 0.0 to 1.0."""
        return {
            "ExtremelyPoor": 0.0,
            "Poor": 0.2,
            "Fair": 0.4,
            "Good": 0.6,
            "Excellent": 1.0,
        }[self.rating]


class EvalRunResult(BaseModel):
    """Result of running an evaluation item.

    For UI: use 'content' or 'output' (same value) to show only the assistant text.
    For evaluations: use the full object (events, steps, plan_completion, etc.).
    In Langfuse: map evaluator prompt variable for display text to JSONPath $.output or $.content.
    """

    item: EvalDatasetItem = Field(..., description="Item of the evaluation item")

    content: str = Field(
        ...,
        description="Display text for UI; final assistant answer. Use this or output for Langfuse JSONPath.",
    )
    events: list[OrchestratorEvent] = Field(
        ..., description="Events of the evaluation item"
    )
    latency_seconds: float = Field(..., description="Latency of the evaluation item")
    is_complete: bool = Field(
        ..., description="Whether the evaluation item is complete"
    )
    number_of_turns: int = Field(
        ..., description="Number of turns in the evaluation item"
    )
    agents: list[Agent] = Field(
        default_factory=list, description="Agents used in the evaluation item"
    )
    steps: list[str] = Field(
        default_factory=list, description="Steps used in the evaluation item"
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors encountered in the evaluation item"
    )
    session_id: str = Field(..., description="Session ID of the evaluation item")
    trace_id: str | None = Field(..., description="Trace ID of the evaluation item")
    plan_completion: float = Field(..., description="Whether the plan was completed")
    predicted_archetype: str | None = Field(
        default=None,
        description="Archetype predicted by the orchestrator (e.g. A1–A6) for archetype-classification eval",
    )


@dataclass
class LangfuseEvalDataset:
    """A dataset of evaluation items from Langfuse."""

    type: Literal["langfuse_dataset"] = Field(..., description="Type of the dataset")
    dataset: DatasetClient = Field(..., description="The dataset client")


@dataclass
class LocalEvalDataset:
    """A dataset of evaluation items from a local JSONL file."""

    type: Literal["local_dataset"] = Field(..., description="Type of the dataset")
    items: list[EvalDatasetItem] = Field(..., description="The items in the dataset")


DatasetSource = LangfuseEvalDataset | LocalEvalDataset
