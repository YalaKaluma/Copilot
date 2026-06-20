import time

import yaml
from openai.types.responses import (
    ResponseOutputItemAddedEvent,
    ResponseOutputMessage,
    ResponseOutputText,
    ResponseReasoningItem,
)
from openai.types.responses.response import Response
from openai.types.responses.response_completed_event import ResponseCompletedEvent
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_output_item import ResponseOutputItem
from openai.types.responses.response_reasoning_summary_text_delta_event import (
    ResponseReasoningSummaryTextDeltaEvent,
)
from packages.langfuse.types import LangfuseAsType
from schemas.evaluation import EvalDatasetItem, EvalRunResult
from evaluation.online_evaluation import evaluate_online
from models.skai_api.autogen import (
    FilterOptions,
    FilterValuesResponse as FilterValuesResponseV1,
    RelatedFiltersRequest as RelatedFiltersRequestV1,
)
from models.skai_api_v2.filters import (
    FilterValuesResponse as FilterValuesResponseV2,
    RelatedFiltersRequest as RelatedFiltersRequestV2,
)
from core.config import get_settings
from prompts.orchestrator.copilot import format_filter_context
from schemas.structured_responses import IntentClassificationResponse
from services.python_repl import PythonREPL
from services.skai_api_v2.client import SkaiApiV2Client

from .core import Agent
from models.copilot.orchestrators import (
    OrchestratorClassification,
    OrchestratorStages,
    OrchestratorEvent,
    OrchestratorEventType,
)
from models.copilot.base import ChatEvent, Tool
from models.copilot.structured_output import Plan
from typing import Any, AsyncGenerator, Callable, Literal, cast
import asyncio
import re

from tools.agent.core import code_execution_tool, execute_tool_for_agent
from tools.orchestrator.base import orchestrator_move_stage
from tools.orchestrator.charts import create_show_chart
from tools.orchestrator.scoping import create_request_more_info
from services.llm.openai_client import AsyncOpenaiClient
import json
from services.skai_api import SKAIApi, get_filter_options
from tools.skai_v2.tools import get_skai_promo_tools

from services.tracing import observation_context
from config.versioning import ResolvedVersion
from tools.orchestrator.execution import generate_handoffs
from tools.orchestrator.planning import create_plan, create_plan_update
from core.logging import get_logger

logger = get_logger(__name__)
CLARIFICATION_ACTION_LIMIT = 5

EXCLUDED_FILTER_OPTIONS = {
    "brands": {"NOT AVAILABLE"},
}

FilterValuesResponseAny = FilterValuesResponseV1 | FilterValuesResponseV2


def _extract_thinking(arguments: dict) -> tuple[str | None, dict]:
    """Extract thinking from tool arguments and return it separately.

    Returns:
        Tuple of (thinking_text, remaining_arguments)
    """
    thinking = arguments.pop("thinking", None)
    return thinking, arguments


def _event(
    event_type: OrchestratorEventType,
    stage: OrchestratorStages,
    content: str,
    **kwargs,
) -> OrchestratorEvent:
    """Helper to create OrchestratorEvent with less boilerplate."""
    return OrchestratorEvent(
        event_type=event_type,
        stage=stage,
        content=content,
        **kwargs,
    )


def _format_numbered_list(text: str) -> str:
    """Format text with numbered items into a readable list.

    Converts patterns like "1) item 2) item" or "1. item 2. item"
    into proper newline-separated lists.
    """
    # Match list markers like "1)" / "1." only when they are standalone:
    # - at the start of text, or after whitespace / ":" / ";"
    # - followed by at least one whitespace character
    #
    # This avoids mangling parenthesized values "(1)" and date fragments like
    # "2025-12-01)," which previously caused broken markdown rendering.
    pattern = re.compile(r"(?:(?<=^)|(?<=[\s:;]))(\d+[.)])\s+")
    matches = list(pattern.finditer(text))
    if len(matches) > 1:
        formatted_lines: list[str] = []
        first_match = matches[0]
        leading_text = text[: first_match.start(1)].strip()
        if leading_text:
            formatted_lines.append(leading_text)

        for idx, match in enumerate(matches):
            marker = match.group(1)
            item_start = match.end()
            item_end = (
                matches[idx + 1].start(1) if idx + 1 < len(matches) else len(text)
            )
            item_text = text[item_start:item_end].strip()
            if item_text:
                formatted_lines.append(f"\n{marker} {item_text}")

        return "".join(formatted_lines).strip()

    return text


def _normalize_data_points(data_points: Any) -> list[dict[str, Any]]:
    """Normalize data points into a list of dicts."""
    if not isinstance(data_points, list):
        return []
    data_list = []

    def _validate_data_value(value: Any | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    for item in data_points:
        if isinstance(item, dict):
            label = item.get("label")
            value = _validate_data_value(item.get("value"))
            if label and value:
                data_list.append({"label": label, "value": value})
        elif isinstance(item, str):
            parts = item.split(":", 1)
            label, value_str = parts[0].strip(), _validate_data_value(parts[1].strip())
            if label and value_str:
                data_list.append({"label": label, "value": value_str})
    return data_list


def _normalize_actions(
    raw_actions: Any, limit: int = CLARIFICATION_ACTION_LIMIT
) -> list[str]:
    """Normalize action options into a clean list of strings.

    Accepts list/tuple or a single string. Drops empty entries and limits size.
    """
    if raw_actions is None:
        return []
    candidates: list[Any]
    if isinstance(raw_actions, str):
        candidates = [raw_actions]
    elif isinstance(raw_actions, (list, tuple)):
        candidates = list(raw_actions)
    else:
        return []

    actions: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item is None:
            continue
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        actions.append(text)
        if len(actions) >= limit:
            break
    return actions


def _stream_tokens(text: str) -> list[str]:
    """Split text into token-like chunks for streaming.

    We approximate tokens as "word + trailing whitespace" to keep UI updates smooth
    without requiring a tokenizer dependency.
    """
    if not text:
        return []
    tokens = re.findall(r"\S+\s*|\s+", text)
    return tokens if tokens else [text]


class OrchestratorSession(Agent):
    def __init__(
        self,
        session_id: str,
        chat_history: list[ChatEvent],
        llm_service: AsyncOpenaiClient,
        skai_service: SKAIApi | SkaiApiV2Client,
        version_config: ResolvedVersion,
        filter_options: FilterOptions | None = None,
    ):
        super().__init__(
            session_id, chat_history, llm_service, skai_service, version_config
        )
        self.skai_service: SKAIApi | SkaiApiV2Client = skai_service
        self._pending_user_reply: asyncio.Future[str] | None = None
        self.plan: Plan | None = None
        self.plan_progress: list[bool] = []
        self.current_stage = OrchestratorStages.scoping
        self.filter_values: FilterValuesResponseAny | None = None
        self.user_selected_filter_options: FilterOptions | None = filter_options
        # Track if we're waiting for more info - allows non-blocking request_info
        self.waiting_for_info = False
        self.pending_info_request: str | None = None
        self.waiting_stage: OrchestratorStages | None = None
        # Mark when workflow has finished (done stage completed)
        self.is_complete = False
        self.final_answer: str | None = None
        self.last_answer: str | None = None
        # Controls whether the final answer should be streamed token-by-token
        self.stream_final_answer: bool = False

        # retain all events for evaluation
        self._events: list[OrchestratorEvent] = []
        self._total_time = 0.0
        # Classification metadata (set when create_plan is called) for trace
        self.classification: OrchestratorClassification = self._empty_classification()
        # Done-stage metadata (set when move_to_done is called) for trace/UI
        self._done_confidence: str | None = None
        self._done_assumptions_and_risks: str | None = None

    def _empty_classification(self) -> OrchestratorClassification:
        return {
            "question_archetype": None,
            "topic": None,
            "assumptions_used": None,
        }

    def _ensure_plan_progress(self) -> None:
        if not self.plan or not self.plan.steps:
            self.plan_progress = []
            return
        if len(self.plan_progress) != len(self.plan.steps):
            self.plan_progress = [False] * len(self.plan.steps)

    def _build_plan_payload(self) -> dict[str, Any]:
        if not self.plan or not getattr(self.plan, "steps", None):
            return {"steps": []}
        self._ensure_plan_progress()
        steps_payload = []
        for idx, step in enumerate(self.plan.steps):
            status = "completed" if self.plan_progress[idx] else "pending"
            steps_payload.append(
                {
                    "id": f"step-{idx + 1}",
                    "name": step,
                    "status": status,
                }
            )
        completed_count = sum(1 for done in self.plan_progress if done)
        payload: dict[str, Any] = {
            "steps": steps_payload,
            "total_steps": len(steps_payload),
        }
        if steps_payload:
            payload["current_step"] = min(completed_count + 1, len(steps_payload))
        return payload

    def _render_plan_markdown(self) -> str:
        if not self.plan or not getattr(self.plan, "steps", None):
            return "No plan is available to update."
        self._ensure_plan_progress()
        lines = ["The current plan is this. Please work to complete this:"]
        for idx, step in enumerate(self.plan.steps):
            checkbox = "x" if self.plan_progress[idx] else " "
            lines.append(f"- [{checkbox}] {step}")
        return "\n".join(lines)

    async def plan_update(self, step_numbers: list[int]) -> str:
        if not self.plan or not self.plan.steps:
            return "No plan is available to update."
        self._ensure_plan_progress()

        completed_steps = []
        invalid_step_numbers = []
        for step_number in step_numbers:
            if step_number < 1 or step_number > len(self.plan.steps):
                logger.warning(f"Invalid step number: {step_number}")
                invalid_step_numbers.append(step_number)
                continue
            completed_steps.append(step_number)
            self.plan_progress[step_number - 1] = True

        return f"Plan updated successfully. Completed steps: {completed_steps}. Invalid step numbers: {invalid_step_numbers}."

    async def set_plan(
        self,
        steps: list[str],
        assumptions_used: list[str] | None,
    ) -> int | None:
        cleaned_steps = [str(step).strip() for step in steps if str(step).strip()]
        if not cleaned_steps:
            self.plan = None
            self.plan_progress = []
            return None
        self.plan = Plan(steps=cleaned_steps)
        self._ensure_plan_progress()

        if assumptions_used:
            self.classification["assumptions_used"] = assumptions_used

        return len(cleaned_steps)

    def _plan_context_block(self) -> str:
        if not self.plan or not getattr(self.plan, "steps", None):
            return ""
        self._ensure_plan_progress()
        lines = [
            "## Current Execution Plan",
            "",
            "Use this plan to guide execution and call `plan_update` after each completed step.",
            "",
        ]
        for idx, step in enumerate(self.plan.steps):
            checkbox = "x" if self.plan_progress[idx] else " "
            lines.append(f"- [{checkbox}] {step}")
        return "\n".join(lines)

    def _default_assumptions(self) -> str:
        if self.user_selected_filter_options:
            default_assumptions_all = self.user_selected_filter_options.model_dump(
                mode="json", exclude_none=True
            )
            default_assumptions = {
                k: v for k, v in default_assumptions_all.items() if v
            }
        else:
            default_assumptions = {}
        return json.dumps(default_assumptions)

    async def _build_prompt_messages(self, base_content: str) -> list[ChatEvent]:
        filter_values = await self._set_filter_values()

        orchestrator_content = self._version_config.get_prompt(
            "orchestrator",
            context={
                "scope_values": format_filter_context(filter_values),
                "default_assumptions": self._default_assumptions(),
            },
        )

        if not base_content or not orchestrator_content:
            raise ValueError("Base or orchestrator prompt not found")

        messages = [
            ChatEvent(role="system", content=base_content),
            ChatEvent(role="system", content=orchestrator_content),
        ]

        messages.extend(self.chat_history)

        plan_context = self._plan_context_block()
        if plan_context:
            messages.append(ChatEvent(role="system", content=plan_context))

        return messages

    async def _classify_intent(self) -> IntentClassificationResponse | None:
        return None

    def _select_tool_response(self, response: Response) -> ResponseOutputItem | None:
        output = response.output
        for item in output:
            if item.type == "function_call":
                return item
        return output[0] if output else None

    def _select_tool_responses(self, response: Response) -> list[ResponseOutputItem]:
        output = response.output
        function_calls: list[ResponseOutputItem] = [
            item for item in output if item.type == "function_call"
        ]
        if function_calls:
            return function_calls
        return [output[0]] if output else []

    async def await_user_reply(self) -> str:
        loop = asyncio.get_running_loop()
        self._pending_user_reply = loop.create_future()
        try:
            return await self._pending_user_reply
        finally:
            self._pending_user_reply = None  # cleanup

    async def _done(self):
        """Final stage - create final answer, stream it to the user, mark session complete."""
        # Answer is the hand_back result we appended after the handoff (skip "moved to done" which is last)
        answer = self.last_answer or ""
        if not answer:
            for i in range(len(self.chat_history) - 1, -1, -1):
                ev = self.chat_history[i]
                if ev.role == "tool":
                    content = ev.content.strip()
                    if not content or content == "moved to done":
                        continue
                    if content.startswith(
                        "The current plan is this."
                    ) or content.startswith("No plan is available"):
                        continue
                    answer = content
                    break
        self.is_complete = True
        self.final_answer = answer or None
        # Stream a clear "final answer" to the user (optionally token-by-token)
        if answer:
            prefix = "**Final answer:**\n\n"
            if self.stream_final_answer:
                for token in _stream_tokens(prefix):
                    yield _event(
                        OrchestratorEventType.content,
                        OrchestratorStages.done,
                        token,
                    )
                    await asyncio.sleep(0.01)
                for token in _stream_tokens(answer):
                    yield _event(
                        OrchestratorEventType.content,
                        OrchestratorStages.done,
                        token,
                    )
                    await asyncio.sleep(0.01)
            else:
                yield _event(
                    OrchestratorEventType.content,
                    OrchestratorStages.done,
                    f"{prefix}{answer}",
                )
        else:
            yield _event(
                OrchestratorEventType.content,
                OrchestratorStages.done,
                "Workflow completed. No answer was returned.",
            )
        done_meta: dict[str, Any] = {}
        if self._done_confidence is not None:
            done_meta["confidence"] = self._done_confidence
        if self._done_assumptions_and_risks is not None:
            done_meta["assumptions_and_risks"] = self._done_assumptions_and_risks
        yield _event(
            OrchestratorEventType.stage_complete,
            OrchestratorStages.done,
            "Orchestrator workflow completed successfully",
            metadata=done_meta if done_meta else None,
        )
        self.chat_history.append(
            ChatEvent(
                role="assistant",
                content=answer,
            )
        )

    async def _returned_to_user(self):
        """Stage when orchestrator returns control to user due to execution issues."""
        # This stage is entered when execution cannot proceed
        # The message has already been yielded in _single_agent
        pass

    async def _set_filter_values(self) -> FilterValuesResponseAny:

        if self.filter_values is None:
            skai_service = cast(SKAIApi, self.skai_service)
            if self.user_selected_filter_options:
                filter_resp = await skai_service.get_filter_values_related(
                    RelatedFiltersRequestV1(
                        retailers=self.user_selected_filter_options.retailers,
                        categories=self.user_selected_filter_options.categories,
                        subcategories=self.user_selected_filter_options.subcategories,
                        brands=self.user_selected_filter_options.brands,
                        channels=self.user_selected_filter_options.channels,
                        price_tiers=self.user_selected_filter_options.price_tiers,
                        pack_size_range_values=self.user_selected_filter_options.pack_size_range_values,
                    )
                )
            else:
                filter_resp = await get_filter_options(skai_service)
            filters = filter_resp.filters

            for filter_name, excluded_values in EXCLUDED_FILTER_OPTIONS.items():
                fetched_values = getattr(filters, filter_name, None)
                if fetched_values is not None:
                    setattr(
                        filter_resp.filters,
                        filter_name,
                        list(set(fetched_values) - excluded_values),
                    )

            # TODO: Later remove this after validating correct SKU IDs
            sku_ids = filter_resp.filters.sku_ids or []
            sku_id_map = {}
            for index, sku_id in enumerate(sku_ids, 1):
                if index < 10:
                    sku_id_mod = f"SKU00{index}"
                else:
                    sku_id_mod = f"SKU0{index}"
                sku_id_map[sku_id_mod] = sku_id
            filter_resp.filters.sku_ids = list(sku_id_map.keys())
            self.filter_values = filter_resp
        return self.filter_values

    async def _request_more_info(
        self,
        question: str,
        actions: list[str],
        allow_other: bool = True,
        enabler_category: Literal["objective", "scope", "guardrails"] | None = None,
    ) -> AsyncGenerator[OrchestratorEvent, None]:
        self.waiting_for_info = True
        formatted_message = _format_numbered_list(question)
        self.pending_info_request = formatted_message
        self.waiting_stage = self.current_stage
        self.chat_history.append(
            ChatEvent(
                role="assistant",
                content=formatted_message,
            )
        )
        request_meta: dict[str, Any] = {
            "request": formatted_message,
            **({"actions": actions} if actions else {}),
            "allow_other": allow_other,
        }
        if enabler_category is not None:
            request_meta["enabler_category"] = enabler_category
        yield _event(
            OrchestratorEventType.request_info,
            self.current_stage,
            f"**I need some additional information:**\n\n{formatted_message}",
            metadata=request_meta,
        )
        return

    async def _single_agent(self) -> AsyncGenerator[OrchestratorEvent, None]:
        """Single-agent loop that manages scoping, planning, and execution."""
        filter_values = await self._set_filter_values()
        request_more = create_request_more_info().with_thinking()
        show_chart_def = create_show_chart().with_thinking()
        create_plan_def = create_plan().with_thinking()
        plan_update_def = create_plan_update().with_thinking()
        move_to_done = orchestrator_move_stage(OrchestratorStages.done).with_thinking()

        filter_metadata = filter_values.metadata
        data_range = filter_metadata.data_range
        timestamp = get_settings().timestamp
        latest_date = (
            data_range.max_date.isoformat() if data_range.max_date else timestamp
        )
        earliest_date = (
            data_range.min_date.isoformat() if data_range.min_date else "Not available"
        )

        prompt_context = {
            "max_date": latest_date,
            "min_date": earliest_date,
        }
        base_content = self._version_config.get_prompt("base", context=prompt_context)
        # Add thinking parameter to each handoff tool
        python_repl = PythonREPL(self.session_id)
        potential_handoffs = generate_handoffs(
            self.session_id,
            self.llm_service,
            cast(SKAIApi, self.skai_service),
            self._version_config,
            cast(FilterOptions, filter_values.filters),
            prompt_context,
            python_repl,
        )
        handoff_map: dict[
            str, Callable[[], AsyncGenerator[OrchestratorEvent, None]]
        ] = {tool.definition.name: tool.executor for tool in potential_handoffs}
        handoff_tools_with_thinking = [
            tool.definition.with_thinking() for tool in potential_handoffs
        ]

        step_number = 0
        execution_message_recovery_used = False

        # Initial stage handling
        if self.waiting_for_info:
            logger.info("Continuing with user's additional info")
            self.waiting_for_info = False
            self.pending_info_request = None
            resume_stage = self.waiting_stage or self.current_stage
            self.waiting_stage = None
            self.current_stage = resume_stage
            yield _event(
                OrchestratorEventType.progress,
                resume_stage,
                "Processing your additional information...",
            )
        else:
            # New user workflow: clear per-run metadata to avoid leaking prior-turn traces
            self.classification = self._empty_classification()
            self._done_confidence = None
            self._done_assumptions_and_risks = None

            self.current_stage = OrchestratorStages.scoping
            yield _event(
                OrchestratorEventType.stage_start,
                OrchestratorStages.scoping,
                "Starting scoping phase - analyzing your request to understand requirements",
            )
        intent_classification = await self._classify_intent()

        if intent_classification:
            yield _event(
                OrchestratorEventType.thinking,
                self.current_stage,
                intent_classification.reasoning or "Classifying intent...",
            )
            if (
                not intent_classification.archetype
                and intent_classification.clarification_question
            ):
                async for ev in self._request_more_info(
                    intent_classification.clarification_question,
                    intent_classification.user_actions or [],
                    allow_other=True,
                    enabler_category="objective",
                ):
                    yield ev
                return
            elif intent_classification.archetype:
                self.classification["question_archetype"] = (
                    intent_classification.archetype
                )
                if intent_classification.domain_label:
                    self.classification["topic"] = intent_classification.domain_label

        while True:
            total_steps = (
                len(self.plan.steps)
                if self.plan and getattr(self.plan, "steps", None)
                else 0
            )
            yield _event(
                OrchestratorEventType.thinking,
                self.current_stage,
                "Determining next action...",
                transient=True,
                step_number=step_number,
                total_steps=total_steps,
            )

            current_input_messages = await self._build_prompt_messages(base_content)

            tools = handoff_tools_with_thinking + [
                request_more,
                show_chart_def,
                create_plan_def,
                plan_update_def,
                move_to_done,
            ]

            summary_started = False
            final_response = None
            trace_ctx = observation_context(
                as_type=LangfuseAsType.GENERATION.value,
                name="tools_request",
                session_id=self.session_id,
                input_messages=current_input_messages,
                model=self._version_config.config.model.model_id,
                tools=tools,
            )

            with trace_ctx as span:
                stream = self.llm_service.request_tools_stream(
                    current_input_messages,
                    self._version_config.config.model.model_id,
                    tools,
                    reasoning_effort="low",  # TODO: add this in versioning config later
                )
                async for resp_event in stream:
                    event_type = resp_event.type
                    if isinstance(resp_event, ResponseReasoningSummaryTextDeltaEvent):
                        metadata: dict[str, Any] = {"kind": "reasoning_summary"}
                        if not summary_started:
                            metadata["reset"] = True
                            summary_started = True
                        yield _event(
                            OrchestratorEventType.thinking,
                            self.current_stage,
                            resp_event.delta,
                            transient=True,
                            metadata=metadata,
                        )
                    elif isinstance(resp_event, ResponseCompletedEvent):
                        final_response = resp_event.response
                    elif event_type in (
                        "response.failed",
                        "response.incomplete",
                        "response.error",
                    ):
                        error_text = (
                            getattr(resp_event, "error", None)
                            or "Streaming request failed."
                        )
                        if span:
                            span.update(level="ERROR", status_message=error_text)
                        yield _event(
                            OrchestratorEventType.error,
                            self.current_stage,
                            str(error_text),
                            step_number=step_number,
                            total_steps=total_steps,
                        )
                tool_response = (
                    self._select_tool_response(final_response)
                    if final_response
                    else None
                )

                if span:
                    if tool_response is None:
                        span.update(
                            level="ERROR",
                            status_message="No response returned from LLM",
                        )
                    else:
                        span.update(output=tool_response.model_dump(mode="json"))

            if tool_response is None:
                yield _event(
                    OrchestratorEventType.error,
                    self.current_stage,
                    "No response from model, retrying...",
                    step_number=step_number,
                    total_steps=total_steps,
                )
                # do not continue with the loop if there is an error
                break

            if isinstance(tool_response, ResponseFunctionToolCall):
                tool_name = tool_response.name
                arguments_str = tool_response.arguments
                arguments = json.loads(arguments_str) if arguments_str else {}
                tool_id = tool_response.call_id

                thinking, arguments = _extract_thinking(arguments)
                if thinking:
                    yield _event(
                        OrchestratorEventType.thinking,
                        self.current_stage,
                        thinking,
                        transient=True,
                        step_number=step_number,
                        total_steps=total_steps,
                        tool_name=tool_name,
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="assistant",
                            content=f"Thinking: {thinking}\n\nTool call name: {tool_name}\n\nTool call arguments: {arguments}",
                        )
                    )

                if tool_name == request_more.name:
                    question = str(arguments.get("question", str(arguments)))
                    actions = _normalize_actions(arguments.get("actions"))
                    allow_other = arguments.get("allow_other", True)
                    if not isinstance(allow_other, bool):
                        allow_other = True

                    enabler_category = arguments.get("enabler_category")

                    async for ev in self._request_more_info(
                        question,
                        actions,
                        allow_other,
                        enabler_category,
                    ):
                        yield ev
                    return

                if tool_name == create_plan_def.name:
                    if self.current_stage == OrchestratorStages.scoping:
                        yield _event(
                            OrchestratorEventType.stage_complete,
                            OrchestratorStages.scoping,
                            "Scoping complete - creating execution plan",
                        )
                        yield _event(
                            OrchestratorEventType.stage_start,
                            OrchestratorStages.planning,
                            "Starting planning phase - creating execution plan",
                        )
                        self.current_stage = OrchestratorStages.planning
                    elif self.current_stage == OrchestratorStages.planning:
                        yield _event(
                            OrchestratorEventType.progress,
                            OrchestratorStages.planning,
                            "Updating execution plan...",
                        )
                    elif self.current_stage == OrchestratorStages.execution:
                        yield _event(
                            OrchestratorEventType.stage_complete,
                            OrchestratorStages.execution,
                            "Execution is interrupted to update the execution plan",
                        )
                        self.current_stage = OrchestratorStages.planning
                        yield _event(
                            OrchestratorEventType.stage_start,
                            OrchestratorStages.planning,
                            "Starting planning phase - creating execution plan",
                        )

                    yield _event(
                        OrchestratorEventType.tool_call,
                        self.current_stage,
                        f"Executing: {tool_name}",
                        tool_name=tool_name,
                        tool_args=arguments,
                        transient=True,
                    )
                    with observation_context(
                        name=tool_name,
                        as_type=LangfuseAsType.TOOL.value,
                        input={"thinking": thinking, **arguments},
                        session_id=self.session_id,
                    ) as tool_span:
                        if "steps" not in arguments:
                            tool_call_status = False
                            result_str = "Steps are required to create a plan."
                        else:
                            number_of_steps = await self.set_plan(
                                steps=arguments["steps"],
                                assumptions_used=arguments.get("assumptions_used"),
                            )
                            if number_of_steps is None:
                                tool_call_status = False
                                result_str = "Plan creation failed - no valid steps were provided."
                            else:
                                tool_call_status = True
                                result_str = (
                                    f"Plan created with {number_of_steps} steps."
                                )
                        self.chat_history.append(
                            ChatEvent(
                                role="system",
                                content=f"[Called {tool_name} with tool call ID {tool_id}]",
                            )
                        )
                        self.chat_history.append(
                            ChatEvent(
                                role="tool",
                                tool_call_id=tool_id,
                                content=result_str,
                            )
                        )

                        if not tool_call_status:
                            yield _event(
                                OrchestratorEventType.error,
                                self.current_stage,
                                result_str,
                            )
                            if tool_span:
                                tool_span.update(
                                    level="ERROR",
                                    status_message=result_str,
                                )
                            continue
                        if tool_span:
                            tool_span.update(output=result_str)

                    yield _event(
                        OrchestratorEventType.plan_created,
                        self.current_stage,
                        result_str,
                        total_steps=number_of_steps,
                        plan=self.plan.model_dump() if self.plan else None,
                        metadata=self.classification,
                    )

                    yield _event(
                        OrchestratorEventType.stage_complete,
                        OrchestratorStages.planning,
                        "Planning complete - execution plan ready",
                    )
                    self.current_stage = OrchestratorStages.execution
                    yield _event(
                        OrchestratorEventType.stage_start,
                        OrchestratorStages.execution,
                        f"Starting execution phase - {number_of_steps} steps to execute",
                        total_steps=number_of_steps,
                    )

                    continue

                if tool_name == plan_update_def.name:
                    yield _event(
                        OrchestratorEventType.tool_call,
                        self.current_stage,
                        f"Executing: {tool_name}",
                        step_number=step_number,
                        total_steps=total_steps,
                        tool_name=tool_name,
                        tool_args=arguments,
                        transient=True,
                    )
                    with observation_context(
                        name=tool_name,
                        as_type=LangfuseAsType.TOOL.value,
                        input={"thinking": thinking, **arguments},
                        session_id=self.session_id,
                    ) as tool_span:
                        result_str = await self.plan_update(**arguments)
                        if tool_span:
                            tool_span.update(output=result_str)

                    self.chat_history.append(
                        ChatEvent(
                            role="system",
                            content=f"[Called {tool_name} with tool call ID {tool_id}]",
                        )
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="tool",
                            tool_call_id=tool_id,
                            content=result_str,
                        )
                    )

                    plan_payload = self._build_plan_payload()
                    yield _event(
                        OrchestratorEventType.plan,
                        self.current_stage,
                        "Plan updated",
                        plan=plan_payload,
                        step_number=step_number,
                        total_steps=total_steps,
                    )
                    continue

                if tool_name in handoff_map:
                    if self.current_stage == OrchestratorStages.scoping:
                        yield _event(
                            OrchestratorEventType.stage_complete,
                            OrchestratorStages.scoping,
                            "Scoping complete - creating execution plan",
                        )
                        yield _event(
                            OrchestratorEventType.stage_start,
                            OrchestratorStages.planning,
                            "Starting planning phase - creating execution plan",
                        )
                        self.current_stage = OrchestratorStages.planning
                    if not self.plan:
                        auto_step = f"Execute {tool_name} for requested analysis"
                        self.plan = Plan(steps=[auto_step])
                        self._ensure_plan_progress()
                        plan_dict = self.plan.model_dump()
                        auto_plan_meta = self.classification
                        yield _event(
                            OrchestratorEventType.plan_created,
                            OrchestratorStages.planning,
                            "Plan created with 1 step (auto-generated)",
                            total_steps=1,
                            plan=plan_dict,
                            metadata=auto_plan_meta,
                        )
                    if self.current_stage == OrchestratorStages.planning:
                        yield _event(
                            OrchestratorEventType.stage_complete,
                            OrchestratorStages.planning,
                            "Planning complete - execution plan ready",
                        )
                        self.current_stage = OrchestratorStages.execution
                        total_steps = len(self.plan.steps) if self.plan else 0
                        yield _event(
                            OrchestratorEventType.stage_start,
                            OrchestratorStages.execution,
                            f"Starting execution phase - {total_steps} steps to execute",
                            total_steps=total_steps,
                        )

                    step_number += 1

                    executor = handoff_map[tool_name]

                    hand_back_result_dict = None

                    with observation_context(
                        name=tool_name,
                        as_type=LangfuseAsType.TOOL.value,
                        input={"thinking": thinking, **arguments},
                        session_id=self.session_id,
                    ) as tool_span:
                        try:
                            result = executor(**arguments)
                            async for event in result:
                                yield event
                                if (
                                    event.event_type
                                    == OrchestratorEventType.tool_result
                                    and event.tool_name == "hand_back"
                                    and event.tool_result
                                ):
                                    hand_back_result_dict = event.tool_result
                            if not hand_back_result_dict:
                                if tool_span:
                                    tool_span.update(
                                        level="ERROR",
                                        status_message="Hand back completed with no answer",
                                    )
                                logger.error("Hand back completed with no answer")
                                yield _event(
                                    OrchestratorEventType.error,
                                    OrchestratorStages.execution,
                                    "Hand back completed with no answer",
                                    step_number=step_number,
                                    total_steps=total_steps,
                                    tool_name=tool_name,
                                )
                                break

                            if tool_span:
                                tool_span.update(output=hand_back_result_dict)
                        except Exception as e:
                            logger.error(f"Execution error in {tool_name}: {e}")
                            if tool_span:
                                tool_span.update(
                                    level="ERROR",
                                    status_message=f"Execution error in {tool_name}: {e}",
                                )
                            yield _event(
                                OrchestratorEventType.error,
                                OrchestratorStages.execution,
                                f"An error occurred during execution: {str(e)}",
                                step_number=step_number,
                                total_steps=total_steps,
                                tool_name=tool_name,
                            )
                            break

                    self.chat_history.append(
                        ChatEvent(
                            role="system",
                            content=f"[Called {tool_name} with tool call ID {tool_id}]",
                        )
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="tool",
                            tool_call_id=tool_id,
                            content=json.dumps(hand_back_result_dict),
                        )
                    )
                    logger.debug(
                        "Orchestrator appended handoff call and result to chat_history (%s)",
                        tool_name,
                    )

                    # TODO: later decide if we want to enable this again
                    # answer_lower = hand_back_result_str.lower()
                    # raw_actions = hand_back_result_dict.get("actions", [])
                    # actions = _normalize_actions(raw_actions)
                    # allow_other = hand_back_result_dict.get("allow_other", True)
                    # if not isinstance(allow_other, bool):
                    #     allow_other = True

                    # # to ask back from the user, there must be actions.
                    # needs_user_action = (
                    #     "no data" in answer_lower
                    #     or "user needs to" in answer_lower
                    #     or "update parameters" in answer_lower
                    #     or "could not find" in answer_lower
                    #     or "no results" in answer_lower
                    #     or "empty" in answer_lower
                    #     or "error" in answer_lower
                    # ) and actions
                    # if needs_user_action:
                    #     message_parts = [f"**{hand_back_result_str}**"]
                    #     message_parts.append(
                    #         "\n\n**What would you like to do?** You can adjust the parameters (brands, dates, categories, etc.) or ask a different question."
                    #     )
                    #     full_message = "".join(message_parts)
                    #     logger.info(
                    #         "Agent indicated user action needed, returning to user"
                    #     )

                    #     async for ev in self._request_more_info(
                    #         question=full_message,
                    #         actions=actions,
                    #         allow_other=allow_other,
                    #         enabler_category="scope",
                    #     ):
                    #         yield ev
                    #     return
                    continue

                if tool_name == show_chart_def.name:
                    title = arguments.get("title", "Untitled Chart")
                    chart_type_raw = arguments.get("chart_type", "bar")
                    data_raw = arguments.get("data_points", [])
                    chart_type = (
                        chart_type_raw
                        if chart_type_raw in ("bar", "line", "pie")
                        else "bar"
                    )
                    data_list = _normalize_data_points(data_raw)
                    chart_payload = {
                        "title": title.strip(),
                        "chartType": chart_type,
                        "data": data_list,
                    }
                    yield _event(
                        OrchestratorEventType.chart,
                        self.current_stage,
                        f"Chart: {title.strip()}",
                        chart=chart_payload,
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="system",
                            content=f"[Called {tool_name} with tool call ID {tool_id}]",
                        )
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="tool",
                            tool_call_id=tool_id,
                            content=("Chart is shown to the user"),
                        )
                    )
                    continue

                if tool_name == move_to_done.name:
                    final_answer = arguments["answer"]
                    self.last_answer = final_answer

                    done_confidence = arguments.get("confidence")
                    assumptions_and_risks = arguments.get("assumptions_and_risks")
                    if done_confidence is not None:
                        self._done_confidence = str(done_confidence)
                    if assumptions_and_risks is not None:
                        self._done_assumptions_and_risks = str(assumptions_and_risks)

                    yield _event(
                        OrchestratorEventType.stage_complete,
                        OrchestratorStages.execution,
                        f"Execution complete - {step_number} steps executed",
                        step_number=step_number,
                        total_steps=total_steps,
                    )
                    break
                else:
                    yield _event(
                        OrchestratorEventType.error,
                        self.current_stage,
                        f"Unexpected tool: {tool_name}",
                        step_number=step_number,
                        total_steps=total_steps,
                    )
                    break

            elif isinstance(tool_response, ResponseReasoningItem):
                reasoning_list = tool_response.summary
                if reasoning_list:
                    summary_text = " ".join([r.text for r in reasoning_list])
                    self.chat_history.append(
                        ChatEvent(role="assistant", content=summary_text)
                    )
                    yield _event(
                        OrchestratorEventType.thinking,
                        self.current_stage,
                        summary_text,
                        transient=True,
                        step_number=step_number,
                        total_steps=total_steps,
                    )
                continue
            elif isinstance(tool_response, ResponseOutputMessage):
                content = tool_response.content
                if content:
                    parts = [
                        item.text
                        for item in content
                        if isinstance(item, ResponseOutputText)
                    ]
                    text = " ".join(parts) if parts else str(content)
                    text = text.strip() if text else ""
                    if text:
                        self.last_answer = text
                        # If we're in execution and the model replied with text instead of
                        # a tool call (e.g. after show_chart), append it and loop once so
                        # the model can call move_to_done instead of going straight to completed.
                        if (
                            self.current_stage == OrchestratorStages.execution
                            and not execution_message_recovery_used
                        ):
                            execution_message_recovery_used = True
                            self.chat_history.append(
                                ChatEvent(role="assistant", content=text)
                            )
                            yield _event(
                                OrchestratorEventType.content,
                                self.current_stage,
                                text,
                                step_number=step_number,
                                total_steps=total_steps,
                            )
                            continue
                break
            else:
                yield _event(
                    OrchestratorEventType.error,
                    self.current_stage,
                    f"Unexpected response type: {tool_response.type}, finishing execution...",
                    step_number=step_number,
                    total_steps=total_steps,
                )
                break

        python_repl.cleanup()

        async for event in self._done():
            yield event

    async def run_online_evals(self, trace_id: str):
        """Run online evaluations on the events."""

        first_user_content = self.chat_history[0].content if self.chat_history else ""
        eval_item = EvalDatasetItem(
            id=f"eval-{self.session_id}",
            input=first_user_content,
            chat_history=self.chat_history[1:] if len(self.chat_history) > 1 else [],
            expected_output=None,
        )

        eval_result = EvalRunResult(
            item=eval_item,
            content=self.last_answer or "",
            events=self._events,
            latency_seconds=self._total_time,
            is_complete=self.is_complete,
            number_of_turns=len(
                [1 for item in self.chat_history if item.role == "user"]
            ),
            session_id=self.session_id,
            trace_id=trace_id,
            plan_completion=all(self.plan_progress),
            steps=self.plan.steps if self.plan else [],
        )
        await evaluate_online(eval_result)

    async def execute(self, trace_id: str, user_email_id: str | None = None):
        """Execute the orchestrator workflow starting from scoping."""
        start_time = time.perf_counter()
        with observation_context(
            name="orchestrator_execute",
            as_type=LangfuseAsType.AGENT.value,
            input_messages=self.chat_history,
            session_id=self.session_id,
            trace_id=trace_id,
            user_id=user_email_id,
        ) as span:
            if span:
                config_yaml = yaml.safe_dump(
                    self._version_config.config.model_dump(mode="json"),
                    sort_keys=False,
                )
                span.update(metadata={"copilot_config_yaml": config_yaml})
            event = None
            event_dict = {}
            async for event in self._single_agent():
                self._events.append(event)
                yield event
            if event:
                event_dict = event.model_dump(mode="json")
                if self.last_answer:
                    event_dict["content"] = self.last_answer
            if span:
                span.update(output=event_dict)
        self._total_time += time.perf_counter() - start_time


class OrchestratorSessionV2(OrchestratorSession):
    """Orchestrator session for v2 of the orchestrator."""

    async def _classify_intent(self) -> IntentClassificationResponse | None:
        classification_model = "gpt-5-mini"

        if self.classification["question_archetype"] is not None:
            return None

        intent_classifier_content = self._version_config.get_prompt("intent_classifier")

        messages = [
            ChatEvent(role="system", content=intent_classifier_content),
            *self.chat_history,
        ]

        trace_ctx = observation_context(
            as_type=LangfuseAsType.GENERATION.value,
            name="intent_classifier",
            session_id=self.session_id,
            input_messages=messages,
            model=classification_model,
        )

        with trace_ctx as span:
            try:
                response = await self.llm_service.request_structured(
                    messages,
                    classification_model,
                    IntentClassificationResponse,
                    reasoning_effort=None,
                )
            except Exception as e:
                logger.error(f"Error classifying intent: {e}")
                if span:
                    span.update(
                        level="ERROR",
                        status_message=f"Error classifying intent: {str(e)}",
                    )
                raise
            if span:
                span.update(output=response.model_dump(mode="json"))
        return response

    async def _build_prompt_messages(self, base_content: str) -> list[ChatEvent]:
        filter_values = await self._set_filter_values()

        if not self.classification["question_archetype"]:
            raise ValueError("Question archetype not found")

        archetype_config = self._version_config.config.archetype_config[
            self.classification["question_archetype"]
        ]
        scoping_framework = archetype_config.scoping_framework
        planning_framework = archetype_config.planning_framework
        response_structure = archetype_config.response_format

        if self.classification["topic"] and self.classification["topic"] in [
            "D4",
            "DX",
        ]:
            planning_framework = f"""
            {planning_framework}
            {archetype_config.promo_analysis_framework}
            """

        orchestrator_content = self._version_config.get_prompt(
            "orchestrator",
            context={
                "scope_values": format_filter_context(filter_values),
                "default_assumptions": self._default_assumptions(),
                "scoping_framework": scoping_framework,
                "planning_framework": planning_framework,
                "response_structure": response_structure,
            },
        )

        if not base_content or not orchestrator_content:
            raise ValueError("Base or orchestrator prompt not found")

        messages = [
            ChatEvent(role="system", content=base_content),
            ChatEvent(role="system", content=orchestrator_content),
        ]

        messages.extend(self.chat_history)

        plan_context = self._plan_context_block()
        if plan_context:
            messages.append(ChatEvent(role="system", content=plan_context))

        return messages


class SingleAgentPromoOrchestrator(OrchestratorSessionV2):
    """Single-agent promo v2 orchestrator with direct tool execution."""

    def __init__(
        self,
        session_id: str,
        chat_history: list[ChatEvent],
        llm_service: AsyncOpenaiClient,
        skai_service: SkaiApiV2Client,
        version_config: ResolvedVersion,
        filter_options: FilterOptions | None = None,
    ):
        super().__init__(
            session_id,
            chat_history,
            llm_service,
            skai_service,
            version_config,
            filter_options=filter_options,
        )
        self.skai_service: SkaiApiV2Client = skai_service

    async def _set_filter_values(self) -> FilterValuesResponseAny:
        if self.filter_values is None:
            if self.user_selected_filter_options:
                related_request = RelatedFiltersRequestV2(
                    retailers=self.user_selected_filter_options.retailers,
                    categories=self.user_selected_filter_options.categories,
                    subcategories=self.user_selected_filter_options.subcategories,
                    brands=self.user_selected_filter_options.brands,
                    channels=self.user_selected_filter_options.channels,
                    price_tiers=self.user_selected_filter_options.price_tiers,
                    pack_size_range_values=self.user_selected_filter_options.pack_size_range_values,
                    sku_ids=self.user_selected_filter_options.sku_ids,
                )
                if any(
                    value is not None and value != []
                    for value in related_request.model_dump(exclude_none=True).values()
                ):
                    self.filter_values = await self.skai_service.filters.get_related(
                        related_request
                    )
                else:
                    self.filter_values = await self.skai_service.filters.get_values()
            else:
                self.filter_values = await self.skai_service.filters.get_values()
        return cast(FilterValuesResponseV2, self.filter_values)

    async def _single_agent(self) -> AsyncGenerator[OrchestratorEvent, None]:
        filter_values = await self._set_filter_values()
        request_more = create_request_more_info().with_thinking()
        show_chart_def = create_show_chart().with_thinking()
        create_plan_def = create_plan().with_thinking()
        plan_update_def = create_plan_update().with_thinking()
        move_to_done = orchestrator_move_stage(OrchestratorStages.done).with_thinking()

        filter_metadata = filter_values.metadata
        data_range = filter_metadata.data_range
        timestamp = get_settings().timestamp
        latest_date = (
            data_range.max_date.isoformat() if data_range.max_date else timestamp
        )
        earliest_date = (
            data_range.min_date.isoformat() if data_range.min_date else "Not available"
        )
        prompt_context = {
            "max_date": latest_date,
            "min_date": earliest_date,
        }
        base_content = self._version_config.get_prompt("base", context=prompt_context)

        self.python_repl = PythonREPL(self.session_id)
        direct_tools = get_skai_promo_tools(
            cast(FilterValuesResponseV2, filter_values).filters
        )
        code_tool = code_execution_tool()
        direct_tool_map: dict[str, Tool] = {
            tool.definition.name: tool for tool in direct_tools + [code_tool]
        }
        skai_tool_names = {tool.definition.name for tool in direct_tools}
        tools = [tool.definition.with_thinking() for tool in direct_tools]
        tools.append(code_tool.definition.with_thinking())
        tools.extend(
            [
                request_more,
                show_chart_def,
                create_plan_def,
                plan_update_def,
                move_to_done,
            ]
        )

        step_number = 0
        execution_message_recovery_used = False

        if self.waiting_for_info:
            logger.info("Continuing with user's additional info")
            self.waiting_for_info = False
            self.pending_info_request = None
            resume_stage = self.waiting_stage or self.current_stage
            self.waiting_stage = None
            self.current_stage = resume_stage
            yield _event(
                OrchestratorEventType.progress,
                resume_stage,
                "Processing your additional information...",
            )
        else:
            self.classification = self._empty_classification()
            self._done_confidence = None
            self._done_assumptions_and_risks = None
            self.current_stage = OrchestratorStages.scoping
            yield _event(
                OrchestratorEventType.stage_start,
                OrchestratorStages.scoping,
                "Starting scoping phase - analyzing your request to understand requirements",
            )

        intent_classification = await self._classify_intent()
        if intent_classification:
            yield _event(
                OrchestratorEventType.thinking,
                self.current_stage,
                intent_classification.reasoning or "Classifying intent...",
            )
            if (
                not intent_classification.archetype
                and intent_classification.clarification_question
            ):
                async for ev in self._request_more_info(
                    intent_classification.clarification_question,
                    intent_classification.user_actions or [],
                    allow_other=True,
                    enabler_category="objective",
                ):
                    yield ev
                return
            if intent_classification.archetype:
                self.classification["question_archetype"] = (
                    intent_classification.archetype
                )
            if intent_classification.domain_label:
                self.classification["topic"] = intent_classification.domain_label

        while True:
            total_steps = (
                len(self.plan.steps)
                if self.plan and getattr(self.plan, "steps", None)
                else 0
            )
            yield _event(
                OrchestratorEventType.thinking,
                self.current_stage,
                "Determining next action...",
                transient=True,
                step_number=step_number,
                total_steps=total_steps,
            )

            current_input_messages = await self._build_prompt_messages(base_content)

            summary_started = False
            final_response = None
            response_output_item = None
            trace_ctx = observation_context(
                as_type=LangfuseAsType.GENERATION.value,
                name="tools_request",
                session_id=self.session_id,
                input_messages=current_input_messages,
                model=self._version_config.config.model.model_id,
                tools=tools,
            )

            with trace_ctx as span:
                stream = self.llm_service.request_tools_stream(
                    current_input_messages,
                    self._version_config.config.model.model_id,
                    tools,
                    reasoning_effort="low",
                )
                event_types = []
                async for resp_event in stream:
                    event_type = resp_event.type
                    event_types.append(event_type)
                    if isinstance(resp_event, ResponseReasoningSummaryTextDeltaEvent):
                        metadata: dict[str, Any] = {"kind": "reasoning_summary"}
                        if not summary_started:
                            metadata["reset"] = True
                            summary_started = True
                        yield _event(
                            OrchestratorEventType.thinking,
                            self.current_stage,
                            resp_event.delta,
                            transient=True,
                            metadata=metadata,
                        )
                    elif isinstance(resp_event, ResponseCompletedEvent):
                        if span:
                            span.update(
                                output=resp_event.response.model_dump(mode="json")
                            )
                        final_response = resp_event.response

                    elif isinstance(resp_event, ResponseOutputItemAddedEvent):
                        response_output_item = resp_event.item
                        if span:
                            span.update(
                                output=response_output_item.model_dump(mode="json")
                            )
                    elif event_type in (
                        "response.failed",
                        "response.incomplete",
                        "response.error",
                    ):
                        error_text = (
                            getattr(resp_event, "error", None)
                            or "Streaming request failed."
                        )
                        if span:
                            span.update(level="ERROR", status_message=str(error_text))
                        yield _event(
                            OrchestratorEventType.error,
                            self.current_stage,
                            f"Model request failed: {error_text}",
                            step_number=step_number,
                            total_steps=total_steps,
                        )
                        if self.python_repl:
                            self.python_repl.cleanup()
                        return

            if final_response:
                tool_responses = self._select_tool_responses(final_response)
                if response_output_item and not tool_responses:
                    tool_responses = [response_output_item]

            elif response_output_item:
                tool_responses = [response_output_item]
            else:
                yield _event(
                    OrchestratorEventType.error,
                    self.current_stage,
                    "No tool response found, finishing execution...",
                    step_number=step_number,
                    total_steps=total_steps,
                )
                break

            if not tool_responses:
                yield _event(
                    OrchestratorEventType.error,
                    self.current_stage,
                    "No tool response found, finishing execution...",
                    step_number=step_number,
                    total_steps=total_steps,
                )
                break

            direct_tool_calls: list[ResponseFunctionToolCall] = []
            non_direct_tool_calls: list[ResponseFunctionToolCall] = []
            for item in tool_responses:
                if isinstance(item, ResponseFunctionToolCall):
                    if item.name in direct_tool_map:
                        direct_tool_calls.append(item)
                    else:
                        non_direct_tool_calls.append(item)

            if non_direct_tool_calls:
                serial_only_tool_names = {request_more.name, create_plan_def.name}
                serial_only_calls = [
                    tool
                    for tool in non_direct_tool_calls
                    if tool.name in serial_only_tool_names
                ]
                if serial_only_calls and len(non_direct_tool_calls) > 1:
                    self.chat_history.append(
                        ChatEvent(
                            role="tool",
                            content=(
                                "You cannot call "
                                f"{', '.join([tool.name for tool in serial_only_calls])} "
                                "at the same time as other tools. Please call them one by one."
                            ),
                        )
                    )
                    continue

                ordered_non_direct_tool_calls = sorted(
                    non_direct_tool_calls,
                    key=lambda tool: tool.name == move_to_done.name,
                )
                should_break_for_done = False
                for non_direct_tool_call in ordered_non_direct_tool_calls:
                    tool_name = non_direct_tool_call.name
                    tool_id = non_direct_tool_call.call_id
                    arguments = json.loads(non_direct_tool_call.arguments)
                    thinking, arguments = _extract_thinking(arguments)
                    if thinking:
                        yield _event(
                            OrchestratorEventType.thinking,
                            self.current_stage,
                            thinking,
                            transient=True,
                            step_number=step_number,
                            total_steps=total_steps,
                            tool_name=tool_name,
                        )
                        self.chat_history.append(
                            ChatEvent(
                                role="assistant",
                                content=(
                                    f"Thinking: {thinking}\n\nTool call name: {tool_name}\n\n"
                                    f"Tool call arguments: {arguments}"
                                ),
                            )
                        )

                    if tool_name == request_more.name:
                        question = str(arguments.get("question", str(arguments)))
                        actions = _normalize_actions(arguments.get("actions"))
                        allow_other = arguments.get("allow_other", True)
                        if not isinstance(allow_other, bool):
                            allow_other = True
                        enabler_category = arguments.get("enabler_category")
                        async for ev in self._request_more_info(
                            question,
                            actions,
                            allow_other,
                            enabler_category,
                        ):
                            yield ev
                        return

                    if tool_name == create_plan_def.name:
                        if self.current_stage == OrchestratorStages.scoping:
                            yield _event(
                                OrchestratorEventType.stage_complete,
                                OrchestratorStages.scoping,
                                "Scoping complete - creating execution plan",
                            )
                            yield _event(
                                OrchestratorEventType.stage_start,
                                OrchestratorStages.planning,
                                "Starting planning phase - creating execution plan",
                            )
                            self.current_stage = OrchestratorStages.planning
                        elif self.current_stage == OrchestratorStages.planning:
                            yield _event(
                                OrchestratorEventType.progress,
                                OrchestratorStages.planning,
                                "Updating execution plan...",
                            )
                        elif self.current_stage == OrchestratorStages.execution:
                            yield _event(
                                OrchestratorEventType.stage_complete,
                                OrchestratorStages.execution,
                                "Execution is interrupted to update the execution plan",
                            )
                            self.current_stage = OrchestratorStages.planning
                            yield _event(
                                OrchestratorEventType.stage_start,
                                OrchestratorStages.planning,
                                "Starting planning phase - creating execution plan",
                            )

                        yield _event(
                            OrchestratorEventType.tool_call,
                            self.current_stage,
                            f"Executing: {tool_name}",
                            tool_name=tool_name,
                            tool_args=arguments,
                            transient=True,
                        )
                        if "steps" not in arguments:
                            result_str = "Steps are required to create a plan."
                            tool_call_status = False
                        else:
                            number_of_steps = await self.set_plan(
                                steps=arguments["steps"],
                                assumptions_used=arguments.get("assumptions_used"),
                            )
                            if number_of_steps is None:
                                result_str = "Plan creation failed - no valid steps were provided."
                                tool_call_status = False
                            else:
                                result_str = (
                                    f"Plan created with {number_of_steps} steps."
                                )
                                tool_call_status = True
                        self.chat_history.append(
                            ChatEvent(
                                role="system",
                                content=f"[Called {tool_name} with tool call ID {tool_id}]",
                            )
                        )
                        self.chat_history.append(
                            ChatEvent(
                                role="tool",
                                tool_call_id=tool_id,
                                content=result_str,
                            )
                        )
                        if not tool_call_status:
                            yield _event(
                                OrchestratorEventType.error,
                                self.current_stage,
                                result_str,
                            )
                            continue

                        yield _event(
                            OrchestratorEventType.plan_created,
                            self.current_stage,
                            result_str,
                            total_steps=number_of_steps,
                            plan=self.plan.model_dump() if self.plan else None,
                            metadata=self.classification,
                        )
                        yield _event(
                            OrchestratorEventType.stage_complete,
                            OrchestratorStages.planning,
                            "Planning complete - execution plan ready",
                        )
                        self.current_stage = OrchestratorStages.execution
                        yield _event(
                            OrchestratorEventType.stage_start,
                            OrchestratorStages.execution,
                            f"Starting execution phase - {number_of_steps} steps to execute",
                            total_steps=number_of_steps,
                        )
                        continue

                    if tool_name == plan_update_def.name:
                        yield _event(
                            OrchestratorEventType.tool_call,
                            self.current_stage,
                            f"Executing: {tool_name}",
                            step_number=step_number,
                            total_steps=total_steps,
                            tool_name=tool_name,
                            tool_args=arguments,
                            transient=True,
                        )
                        result_str = await self.plan_update(**arguments)
                        self.chat_history.append(
                            ChatEvent(
                                role="system",
                                content=f"[Called {tool_name} with tool call ID {tool_id}]",
                            )
                        )
                        self.chat_history.append(
                            ChatEvent(
                                role="tool",
                                tool_call_id=tool_id,
                                content=result_str,
                            )
                        )
                        yield _event(
                            OrchestratorEventType.plan,
                            self.current_stage,
                            "Plan updated",
                            plan=self._build_plan_payload(),
                            step_number=step_number,
                            total_steps=total_steps,
                        )
                        continue

                    if tool_name == show_chart_def.name:
                        title = arguments.get("title", "Untitled Chart")
                        chart_type_raw = arguments.get("chart_type", "bar")
                        data_raw = arguments.get("data_points", [])
                        chart_type = (
                            chart_type_raw
                            if chart_type_raw in ("bar", "line", "pie")
                            else "bar"
                        )
                        data_list = _normalize_data_points(data_raw)
                        chart_payload = {
                            "title": title.strip(),
                            "chartType": chart_type,
                            "data": data_list,
                        }
                        yield _event(
                            OrchestratorEventType.chart,
                            self.current_stage,
                            f"Chart: {title.strip()}",
                            chart=chart_payload,
                        )
                        self.chat_history.append(
                            ChatEvent(
                                role="system",
                                content=f"[Called {tool_name} with tool call ID {tool_id}]",
                            )
                        )
                        self.chat_history.append(
                            ChatEvent(
                                role="tool",
                                tool_call_id=tool_id,
                                content="Chart is shown to the user",
                            )
                        )
                        continue

                    if tool_name == move_to_done.name:
                        final_answer = arguments["answer"]
                        self.last_answer = final_answer
                        done_confidence = arguments.get("confidence")
                        assumptions_and_risks = arguments.get("assumptions_and_risks")
                        if done_confidence is not None:
                            self._done_confidence = str(done_confidence)
                        if assumptions_and_risks is not None:
                            self._done_assumptions_and_risks = str(
                                assumptions_and_risks
                            )
                        yield _event(
                            OrchestratorEventType.stage_complete,
                            OrchestratorStages.execution,
                            f"Execution complete - {step_number} steps executed",
                            step_number=step_number,
                            total_steps=total_steps,
                        )
                        should_break_for_done = True
                        break

                if should_break_for_done:
                    break

            if direct_tool_calls:

                if self.current_stage == OrchestratorStages.scoping:
                    yield _event(
                        OrchestratorEventType.stage_complete,
                        OrchestratorStages.scoping,
                        "Scoping complete - creating execution plan",
                    )
                    yield _event(
                        OrchestratorEventType.stage_start,
                        OrchestratorStages.planning,
                        "Starting planning phase - creating execution plan",
                    )
                    self.current_stage = OrchestratorStages.planning
                if not self.plan:
                    self.plan = Plan(
                        steps=[
                            f"Execute {tool_call.name} for requested analysis"
                            for tool_call in direct_tool_calls
                        ]
                    )
                    self._ensure_plan_progress()
                    yield _event(
                        OrchestratorEventType.plan_created,
                        OrchestratorStages.planning,
                        f"Plan created with {len(direct_tool_calls)} steps (auto-generated)",
                        total_steps=len(direct_tool_calls),
                        plan=self.plan.model_dump(),
                        metadata=self.classification,
                    )
                if self.current_stage == OrchestratorStages.planning:
                    yield _event(
                        OrchestratorEventType.stage_complete,
                        OrchestratorStages.planning,
                        "Planning complete - execution plan ready",
                    )
                    self.current_stage = OrchestratorStages.execution
                    total_steps = len(self.plan.steps) if self.plan else 0
                    yield _event(
                        OrchestratorEventType.stage_start,
                        OrchestratorStages.execution,
                        f"Starting execution phase - {total_steps} steps to execute",
                        total_steps=total_steps,
                    )

                parsed_calls: list[
                    tuple[ResponseFunctionToolCall, dict[str, Any], str | None]
                ] = []
                for tool_call in direct_tool_calls:
                    arguments = json.loads(tool_call.arguments)
                    thinking, parsed_arguments = _extract_thinking(arguments)
                    parsed_calls.append((tool_call, parsed_arguments, thinking))

                for tool_call, parsed_arguments, thinking in parsed_calls:
                    step_number += 1
                    if thinking:
                        yield _event(
                            OrchestratorEventType.thinking,
                            self.current_stage,
                            thinking,
                            transient=True,
                            step_number=step_number,
                            total_steps=total_steps,
                            tool_name=tool_call.name,
                        )
                        self.chat_history.append(
                            ChatEvent(
                                role="assistant",
                                content=(
                                    f"Thinking: {thinking}\n\nTool call name: {tool_call.name}\n\n"
                                    f"Tool call arguments: {parsed_arguments}"
                                ),
                            )
                        )
                    yield _event(
                        OrchestratorEventType.tool_call,
                        self.current_stage,
                        f"Executing: {tool_call.name}",
                        step_number=step_number,
                        total_steps=total_steps,
                        tool_name=tool_call.name,
                        tool_args=parsed_arguments,
                        transient=True,
                    )

                execution_results = await asyncio.gather(
                    *[
                        execute_tool_for_agent(
                            agent=self,
                            tool_name=tool_call.name,
                            arguments=parsed_arguments,
                            executor=direct_tool_map[tool_call.name].executor,
                            skai_tool_names=skai_tool_names,
                        )
                        for tool_call, parsed_arguments, _ in parsed_calls
                    ],
                    return_exceptions=True,
                )

                start_step_number = step_number - len(parsed_calls) + 1
                for index, ((tool_call, parsed_arguments, _), result) in enumerate(
                    zip(parsed_calls, execution_results, strict=False),
                    start=start_step_number,
                ):
                    if isinstance(result, Exception):
                        yield _event(
                            OrchestratorEventType.error,
                            OrchestratorStages.execution,
                            f"An error occurred during execution: {str(result)}",
                            step_number=index,
                            total_steps=total_steps,
                            tool_name=tool_call.name,
                        )
                        break

                    self.chat_history.append(
                        ChatEvent(
                            role="system",
                            content=f"[Called {tool_call.name} with tool call ID {tool_call.call_id}]",
                        )
                    )
                    self.chat_history.append(
                        ChatEvent(
                            role="tool",
                            tool_call_id=tool_call.call_id,
                            content=json.dumps(result, default=str),
                        )
                    )
                    yield _event(
                        OrchestratorEventType.tool_result,
                        self.current_stage,
                        f"{tool_call.name} completed",
                        step_number=index,
                        total_steps=total_steps,
                        tool_name=tool_call.name,
                        tool_result=result,
                    )
                else:
                    continue

            if direct_tool_calls or non_direct_tool_calls:
                continue
            tool_response = tool_responses[0]
            if isinstance(tool_response, ResponseFunctionToolCall):

                yield _event(
                    OrchestratorEventType.error,
                    self.current_stage,
                    f"Unexpected tool: {tool_name}",
                    step_number=step_number,
                    total_steps=total_steps,
                )
                break

            elif isinstance(tool_response, ResponseReasoningItem):
                reasoning_list = tool_response.summary
                if reasoning_list:
                    summary_text = " ".join([r.text for r in reasoning_list])
                    self.chat_history.append(
                        ChatEvent(role="assistant", content=summary_text)
                    )
                    yield _event(
                        OrchestratorEventType.thinking,
                        self.current_stage,
                        summary_text,
                        transient=True,
                        step_number=step_number,
                        total_steps=total_steps,
                    )
                continue
            elif isinstance(tool_response, ResponseOutputMessage):
                content = tool_response.content
                if content:
                    parts = [
                        item.text
                        for item in content
                        if isinstance(item, ResponseOutputText)
                    ]
                    text = " ".join(parts) if parts else str(content)
                    text = text.strip() if text else ""
                    if text:
                        self.last_answer = text
                        if (
                            self.current_stage == OrchestratorStages.execution
                            and not execution_message_recovery_used
                        ):
                            execution_message_recovery_used = True
                            self.chat_history.append(
                                ChatEvent(role="assistant", content=text)
                            )
                            yield _event(
                                OrchestratorEventType.content,
                                self.current_stage,
                                text,
                                step_number=step_number,
                                total_steps=total_steps,
                            )
                            continue
                break
            else:
                yield _event(
                    OrchestratorEventType.error,
                    self.current_stage,
                    f"Unexpected response type: {tool_response.type}, finishing execution...",
                    step_number=step_number,
                    total_steps=total_steps,
                )
                break

        if self.python_repl:
            self.python_repl.cleanup()

        async for event in self._done():
            yield event


def get_orchestrator_session(
    version_config: ResolvedVersion,
    session_id: str,
    chat_history: list[ChatEvent],
    skai_service: SKAIApi | SkaiApiV2Client,
    llm_service: AsyncOpenaiClient,
    filter_options: FilterOptions | None = None,
) -> OrchestratorSession:
    orchestrator_version = version_config.config.orchestrator_version

    if orchestrator_version == "v1":
        return OrchestratorSession(
            session_id,
            chat_history,
            llm_service,
            skai_service,
            version_config,
            filter_options=filter_options,
        )
    if orchestrator_version == "single_agent_promo_orchestrator":
        if not isinstance(skai_service, SkaiApiV2Client):

            print(f"skai_service: {skai_service}")
            print(f"type(skai_service): {type(skai_service)}")
            raise TypeError(
                "SingleAgentPromoOrchestrator requires SkaiApiV2Client as skai_service."
            )
        return SingleAgentPromoOrchestrator(
            session_id,
            chat_history,
            llm_service,
            skai_service,
            version_config,
            filter_options=filter_options,
        )
    else:
        return OrchestratorSessionV2(
            session_id,
            chat_history,
            llm_service,
            skai_service,
            version_config,
            filter_options=filter_options,
        )
