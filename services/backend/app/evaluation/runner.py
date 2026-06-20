"""Evaluation runner: invoke orchestrator per dataset item and capture events + final response.

run_orchestrator_for_item returns EvalRunResult (content, events, steps, etc.). For Langfuse
dataset runs the task runs evaluators internally then returns only result.content so the
Langfuse UI shows just the text. For local runs the full EvalRunResult is used.
"""

# TDDO: see if we can reuse the orchestrator session implementation for evaluation

from statistics import mean
import time
import uuid

from copilot_agents.orchestrator import get_orchestrator_session
from models.copilot.orchestrators import OrchestratorEvent, OrchestratorEventType
from packages.langfuse.client import create_trace_id, get_current_trace_id
from schemas.evaluation import EvalDatasetItem, EvalRunResult
from models.copilot.base import ChatEvent
from config.versioning import ResolvedVersion
from services.llm.openai_client import AsyncOpenaiClient
from services.skai_api import SKAIApi
from services.skai_api_v2.client import SkaiApiV2Client


async def run_orchestrator_for_item(
    item: EvalDatasetItem,
    *,
    llm_service: AsyncOpenaiClient,
    skai_service: SKAIApi | SkaiApiV2Client,
    run_id: str | None = None,
    resolved_version: ResolvedVersion,
    # run_name: str | None = None,
    # system_version: str | None = None,
) -> EvalRunResult:
    """
    Run the orchestrator for one evaluation item; collect events and final response.

    When langfuse is provided, creates a single trace for this run and executes the
    orchestrator inside it; returns trace_id in the result. Otherwise no trace is created.

    Option B clarification handling: if the orchestrator emits request_info, we reply with the first suggested action and continue
    Returns:
        Dict with: output, events, latency_seconds, is_complete, session_id,
        and trace_id (when langfuse is provided).
    """
    run_id = run_id or str(uuid.uuid4())
    item_id = item.id or "unknown"
    session_id = f"eval-{item_id}-{run_id}"

    number_of_turns = 1

    session = get_orchestrator_session(
        version_config=resolved_version,
        session_id=session_id,
        chat_history=item.chat_history,
        skai_service=skai_service,
        llm_service=llm_service,
    )
    session.stream_final_answer = False

    events_all: list[OrchestratorEvent] = []
    start = time.perf_counter()

    # TODO: evaluate multi turn chats beter later
    current_user_message = item.input

    trace_id = get_current_trace_id() or create_trace_id(str(uuid.uuid4()))
    last_event_content = ""
    while True:
        session.chat_history.append(
            ChatEvent(role="user", content=current_user_message)
        )
        async for event in session.execute(trace_id):
            if event.event_type == OrchestratorEventType.request_info:
                user_suggested_options = event.metadata.get("actions")
                if user_suggested_options:
                    current_user_message = user_suggested_options[0]
                else:
                    current_user_message = "You have freedom to make assumptions for me"

                number_of_turns += 1

            events_all.append(event)
        last_event_content = event.content

        if session.is_complete:
            break
        if number_of_turns > 4:
            break

    latency_seconds = time.perf_counter() - start
    output = session.final_answer or session.last_answer or last_event_content
    predicted_archetype = session.classification["question_archetype"]

    return EvalRunResult(
        item=item,
        content=output,
        events=events_all,
        latency_seconds=latency_seconds,
        is_complete=session.is_complete,
        number_of_turns=number_of_turns,
        session_id=session_id,
        trace_id=trace_id,
        steps=session.plan.steps if session.plan else [],
        plan_completion=mean(session.plan_progress) if session.plan_progress else 0,
        predicted_archetype=predicted_archetype,
    )
