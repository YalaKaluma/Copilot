from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, TypedDict
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


def _serialize_for_json(obj: Any, path: str = "") -> Any:
    """Recursively convert date/datetime objects and Pydantic models to JSON-serializable format."""
    if isinstance(obj, datetime):
        logger.debug(f"Serializing datetime at {path}: {obj}")
        return obj.isoformat()
    elif isinstance(obj, date):
        logger.debug(f"Serializing date at {path}: {obj}")
        return obj.isoformat()
    elif isinstance(obj, BaseModel):
        # Handle Pydantic models by converting to dict first, then recursively serializing
        logger.debug(f"Serializing Pydantic model at {path}: {type(obj).__name__}")
        return _serialize_for_json(obj.model_dump(), path)
    elif isinstance(obj, dict):
        return {k: _serialize_for_json(v, f"{path}.{k}") for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_serialize_for_json(item, f"{path}[{i}]") for i, item in enumerate(obj)]
    return obj


class OrchestratorStages(StrEnum):
    scoping = "scoping"
    planning = "planning"
    execution = "execution"
    done = "done"
    returned_to_user = "returned_to_user"


class OrchestratorEventType(StrEnum):
    """Types of events the orchestrator can emit."""

    stage_start = "stage_start"
    stage_complete = "stage_complete"
    progress = "progress"
    content = "content"
    plan = "plan"
    request_info = "request_info"
    tool_call = "tool_call"
    tool_result = "tool_result"
    thinking = "thinking"
    plan_created = "plan_created"
    chart = "chart"
    error = "error"


class OrchestratorEvent(BaseModel):
    """Structured event emitted by the orchestrator."""

    event_type: OrchestratorEventType
    stage: OrchestratorStages
    content: str

    # Transient flag - if true, the event is ephemeral and shouldn't be persisted
    # Used for thinking/reasoning that users may want to see but not store
    transient: bool = False

    # Progress tracking
    step_number: int | None = None
    total_steps: int | None = None

    # Tool execution details
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    tool_result: dict[str, Any] | None = None

    # Plan details
    plan: Any | None = None

    # Chart payload for chart event (title, chartType, data)
    chart: dict[str, Any] | None = None

    # Additional metadata
    metadata: dict[str, Any] | None = None

    def to_sse_dict(self) -> dict:
        """Convert to dict for SSE serialization, excluding None values.

        Handles date/datetime objects by converting them to ISO format strings.
        """
        data: dict[str, Any] = {
            "type": self.event_type.value,
            "stage": self.stage.value,
            "content": self.content,
        }

        # Always include transient if true - frontend uses this to not persist the event
        if self.transient:
            data["transient"] = True

        if self.step_number is not None:
            data["step_number"] = self.step_number
        if self.total_steps is not None:
            data["total_steps"] = self.total_steps
        if self.tool_name is not None:
            data["tool_name"] = self.tool_name
        if self.tool_args is not None:
            data["tool_args"] = _serialize_for_json(self.tool_args)
        if self.tool_result is not None:
            data["tool_result"] = _serialize_for_json(self.tool_result)
        if self.plan is not None:
            data["plan"] = _serialize_for_json(self.plan)
        if self.chart is not None:
            data["chart"] = _serialize_for_json(self.chart)
        if self.metadata is not None:
            data["metadata"] = _serialize_for_json(self.metadata)

        return data


class OrchestratorClassification(TypedDict):
    question_archetype: Literal["A1", "A2", "A3", "A4", "A5", "A6"] | None
    topic: Literal["D1", "D2", "D3", "D4", "D5", "D6", "DX"] | None
    assumptions_used: list[str] | None
