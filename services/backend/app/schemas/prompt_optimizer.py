from typing import Literal
from pydantic import BaseModel, Field


class SavePromptRequest(BaseModel):
    """Request body for saving a single prompt under a new prompt version identifier."""

    content: str
    prompt_version: str


class SaveNewVersionRequest(BaseModel):
    """Request body for creating a new Skai version (reuses base refs for unsaved prompts)."""

    new_version_id: str
    prompt_version: str


class RunExperimentRequest(BaseModel):
    """Request body for running an evaluation experiment with a given copilot version."""

    system_version: str = Field(
        ..., description="Copilot version id to evaluate (e.g. v1, v1-modified)"
    )
    dataset_name: str = Field(
        default="archetype1-descriptive",
        description="Langfuse dataset name (mode=langfuse) or path to JSONL (mode=local).",
    )
    mode: Literal["langfuse", "local"] = Field(
        default="langfuse",
        description="langfuse: load dataset from Langfuse by name; local: load from path.",
    )
    run_name: str | None = Field(
        default=None,
        description="Name for this run (default: copilot-eval-<timestamp>).",
    )
    limit: int | None = Field(
        default=10,
        description="Max items to run (default: 10). None = all.",
    )
