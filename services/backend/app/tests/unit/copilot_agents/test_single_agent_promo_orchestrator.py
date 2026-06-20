from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest
from openai.types.responses.response import Response
from openai.types.responses.response_completed_event import ResponseCompletedEvent

from config.versioning import (
    AgentModelConfig,
    ArchetypeConfig,
    CopilotVersionConfig,
    ResolvedVersion,
)
from copilot_agents.orchestrator import SingleAgentPromoOrchestrator
from models.copilot.base import ChatEvent, Tool, ToolInput, ToolParameter, ToolProperty
from models.copilot.orchestrators import OrchestratorEventType
from schemas.structured_responses import IntentClassificationResponse
from models.skai_api_v2.filters import FilterValuesResponse
from models.skai_api_v2.promo import PromoHeatmapResponse
from services.skai_api_v2.client import SkaiApiV2Client


def _build_version_config() -> ResolvedVersion:
    config = CopilotVersionConfig(
        version="v9-dev",
        execution_agents=[],
        model=AgentModelConfig(model_id="gpt-5.2"),
        prompts={
            "base": "base:v4",
            "orchestrator": "single_agent_promo_orchestrator:v1",
            "intent_classifier": "intent-classification-system:v2",
        },
        orchestrator_version="single_agent_promo_orchestrator",
        archetype_config={
            "A1": ArchetypeConfig(
                scoping_framework="A1 scoping",
                planning_framework="A1 planning",
                response_format="A1 response",
                promo_analysis_framework="A1 promo",
            ),
            "A2": ArchetypeConfig(
                scoping_framework="A2 scoping",
                planning_framework="A2 planning",
                response_format="A2 response",
                promo_analysis_framework="A2 promo",
            ),
            "A3": ArchetypeConfig(
                scoping_framework="A3 scoping",
                planning_framework="A3 planning",
                response_format="A3 response",
                promo_analysis_framework="A3 promo",
            ),
            "A4": ArchetypeConfig(
                scoping_framework="A4 scoping",
                planning_framework="A4 planning",
                response_format="A4 response",
                promo_analysis_framework="A4 promo",
            ),
            "A5": ArchetypeConfig(
                scoping_framework="A5 scoping",
                planning_framework="A5 planning",
                response_format="A5 response",
                promo_analysis_framework="A5 promo",
            ),
            "A6": ArchetypeConfig(
                scoping_framework="A6 scoping",
                planning_framework="A6 planning",
                response_format="A6 response",
                promo_analysis_framework="A6 promo",
            ),
        },
    )
    resolved = ResolvedVersion(config=config, prompts_dir_root=None)
    resolved.get_prompt = lambda key, context=None: f"{key} prompt"  # type: ignore[method-assign]
    return resolved


def _build_filter_values_response() -> FilterValuesResponse:
    return FilterValuesResponse.model_validate(
        {
            "filters": {
                "superCategories": ["Paint"],
                "brands": ["Brand A", "Brand B"],
                "categories": ["Category A"],
                "subcategories": ["Subcategory A"],
                "retailers": ["Retailer A"],
                "channels": ["Online"],
                "priceTiers": ["Premium"],
                "packSizeRangeValues": ["0-5L"],
                "skuIds": ["SKU001"],
            },
            "metadata": {
                "tenantId": 42,
                "lastUpdated": "2026-06-04T09:15:00Z",
                "dataRange": {
                    "minDate": "2025-01-01",
                    "maxDate": "2026-05-31",
                },
            },
        }
    )


def _build_heatmap_response() -> PromoHeatmapResponse:
    return PromoHeatmapResponse.model_validate(
        {
            "data": [
                {
                    "xValue": "Brand A",
                    "yValue": "Retailer A",
                    "investment": "10.00",
                    "incrementalGp": "5.00",
                    "totalSales": "100.00",
                    "roiPct": 0.4,
                    "upliftPct": 0.1,
                    "salesUpliftPct": 0.12,
                    "nPromoWeeks": 4,
                }
            ],
            "summary": {
                "xDimKind": "brand",
                "yDimKind": "retailer",
                "cellCount": 1,
                "totalInvestment": "10.00",
                "totalIncrementalGp": "5.00",
                "totalSales": "100.00",
                "overallRoiPct": 0.4,
                "overallUpliftPct": 0.1,
                "overallSalesUpliftPct": 0.12,
                "nPromoWeeks": 4,
                "currency": "EUR",
            },
        }
    )


def _build_v2_client() -> SkaiApiV2Client:
    client = SkaiApiV2Client(base_url="https://example.test")
    filter_response = _build_filter_values_response()
    heatmap_response = _build_heatmap_response()
    cast(Any, client).filters = SimpleNamespace(
        get_values=AsyncMock(return_value=filter_response),
        get_related=AsyncMock(return_value=filter_response),
    )
    cast(Any, client).promo = SimpleNamespace(
        get_heatmap=AsyncMock(return_value=heatmap_response),
    )
    return client


def _tool_call_event(
    name: str,
    arguments: dict[str, Any],
    *,
    call_id: str,
) -> ResponseCompletedEvent:
    response = Response.model_validate(
        {
            "id": f"resp-{call_id}",
            "created_at": 0,
            "model": "gpt-5.2",
            "object": "response",
            "output": [
                {
                    "arguments": json.dumps(arguments),
                    "call_id": call_id,
                    "name": name,
                    "type": "function_call",
                    "id": f"fc-{call_id}",
                    "status": "completed",
                }
            ],
            "parallel_tool_calls": False,
            "status": "completed",
            "tool_choice": "auto",
            "tools": [],
        }
    )
    return ResponseCompletedEvent.model_validate(
        {
            "response": response.model_dump(mode="json"),
            "sequence_number": 0,
            "type": "response.completed",
        }
    )


def _multi_tool_call_event(
    calls: list[tuple[str, dict[str, Any], str]],
) -> ResponseCompletedEvent:
    response = Response.model_validate(
        {
            "id": "resp-multi",
            "created_at": 0,
            "model": "gpt-5.2",
            "object": "response",
            "output": [
                {
                    "arguments": json.dumps(arguments),
                    "call_id": call_id,
                    "name": name,
                    "type": "function_call",
                    "id": f"fc-{call_id}",
                    "status": "completed",
                }
                for name, arguments, call_id in calls
            ],
            "parallel_tool_calls": True,
            "status": "completed",
            "tool_choice": "auto",
            "tools": [],
        }
    )
    return ResponseCompletedEvent.model_validate(
        {
            "response": response.model_dump(mode="json"),
            "sequence_number": 0,
            "type": "response.completed",
        }
    )


def _build_stream(
    events: list[ResponseCompletedEvent],
) -> Any:
    event_iter = iter(events)

    async def _request_tools_stream(*args, **kwargs) -> AsyncGenerator[Any, None]:
        yield next(event_iter)

    return _request_tools_stream


def _fake_code_execution_tool() -> Tool:
    async def _executor(agent, code: str, **kwargs: Any) -> dict[str, Any]:
        return {"stdout": f"executed:{code}", "stderr": "", "ok": True}

    return Tool(
        definition=ToolInput(
            name="code_execution",
            description="Execute code",
            parameters=ToolParameter(
                properties={
                    "code": ToolProperty(
                        type="string",
                        description="The code to execute.",
                    )
                },
                required=["code"],
            ),
        ),
        executor=_executor,
    )


@pytest.mark.asyncio
async def test_single_agent_promo_orchestrator_executes_direct_tool_loop(monkeypatch):
    client = _build_v2_client()
    llm_service = SimpleNamespace()
    llm_service.request_structured = AsyncMock(
        return_value=IntentClassificationResponse(
            reasoning="Promo reporting request",
            archetype="A1",
            domain_label="D4",
        )
    )
    llm_service.request_tools_stream = _build_stream(
        [
            _tool_call_event(
                "create_plan",
                {
                    "thinking": "Plan the work",
                    "steps": ["Fetch filters", "Analyze heatmap"],
                },
                call_id="create-plan",
            ),
            _tool_call_event(
                "skai_get_promo_heatmap",
                {
                    "thinking": "Fetch heatmap",
                    "x_axis": "brand",
                    "y_axis": "retailer",
                    "brands": ["Brand A"],
                },
                call_id="heatmap",
            ),
            _tool_call_event(
                "code_execution",
                {"thinking": "Compute summary", "code": "print('ok')"},
                call_id="code",
            ),
            _tool_call_event(
                "show_chart",
                {
                    "thinking": "Show a small chart",
                    "title": "ROI by Brand",
                    "chart_type": "bar",
                    "data_points": ["Brand A:0.4"],
                },
                call_id="chart",
            ),
            _tool_call_event(
                "plan_update",
                {"thinking": "Mark the work done", "step_numbers": [1, 2]},
                call_id="plan-update",
            ),
            _tool_call_event(
                "move_to_done",
                {
                    "thinking": "Finish",
                    "answer": "Promo performance is strongest for Brand A.",
                    "confidence": "high",
                },
                call_id="done",
            ),
        ]
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.code_execution_tool",
        _fake_code_execution_tool,
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.PythonREPL",
        lambda session_id: SimpleNamespace(cleanup=lambda: None),
    )

    session = SingleAgentPromoOrchestrator(
        session_id="promo-v2-session",
        chat_history=[ChatEvent(role="user", content="How is Brand A performing?")],
        llm_service=llm_service,
        skai_service=client,
        version_config=_build_version_config(),
    )

    events = [event async for event in session._single_agent()]

    client.filters.get_values.assert_awaited_once_with()
    client.promo.get_heatmap.assert_awaited_once()
    llm_service.request_structured.assert_awaited_once()
    assert session.classification["question_archetype"] == "A1"
    assert session.classification["topic"] == "D4"
    assert any(
        event.event_type == OrchestratorEventType.plan_created for event in events
    )
    assert any(
        event.event_type == OrchestratorEventType.tool_result for event in events
    )
    assert any(event.event_type == OrchestratorEventType.chart for event in events)
    assert any(event.event_type == OrchestratorEventType.plan for event in events)
    assert session.final_answer == "Promo performance is strongest for Brand A."


@pytest.mark.asyncio
async def test_single_agent_promo_orchestrator_reuses_cached_filters_after_clarification(
    monkeypatch,
):
    client = _build_v2_client()
    llm_service = SimpleNamespace()
    llm_service.request_structured = AsyncMock(
        return_value=IntentClassificationResponse(
            reasoning="Need brand clarification first",
            archetype="A1",
            domain_label="D4",
        )
    )
    llm_service.request_tools_stream = _build_stream(
        [
            _tool_call_event(
                "request_more_information",
                {
                    "thinking": "Need a clearer brand choice",
                    "question": "Which brand should I analyze?",
                    "actions": ["Brand A", "Brand B"],
                },
                call_id="clarify",
            )
        ]
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.code_execution_tool",
        _fake_code_execution_tool,
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.PythonREPL",
        lambda session_id: SimpleNamespace(cleanup=lambda: None),
    )

    session = SingleAgentPromoOrchestrator(
        session_id="promo-v2-session",
        chat_history=[ChatEvent(role="user", content="Analyze promo performance")],
        llm_service=llm_service,
        skai_service=client,
        version_config=_build_version_config(),
    )

    first_events = [event async for event in session._single_agent()]
    assert first_events[-1].event_type == OrchestratorEventType.request_info
    assert session.waiting_for_info is True

    session.chat_history.append(ChatEvent(role="user", content="Brand A"))
    llm_service.request_tools_stream = _build_stream(
        [
            _tool_call_event(
                "move_to_done",
                {
                    "thinking": "Now we can finish",
                    "answer": "I will focus on Brand A.",
                },
                call_id="done-after-clarify",
            )
        ]
    )

    second_events = [event async for event in session._single_agent()]

    client.filters.get_values.assert_awaited_once_with()
    assert llm_service.request_structured.await_count == 1
    assert any(
        event.event_type == OrchestratorEventType.progress
        and "Processing your additional information" in event.content
        for event in second_events
    )


@pytest.mark.asyncio
async def test_single_agent_promo_orchestrator_passes_archetype_prompt_context(
    monkeypatch,
):
    client = _build_v2_client()
    llm_service = SimpleNamespace()
    llm_service.request_structured = AsyncMock(
        return_value=IntentClassificationResponse(
            reasoning="Diagnostic promo request",
            archetype="A2",
            domain_label="D4",
        )
    )
    llm_service.request_tools_stream = _build_stream(
        [
            _tool_call_event(
                "move_to_done",
                {"thinking": "Finish", "answer": "Done."},
                call_id="done",
            )
        ]
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.code_execution_tool",
        _fake_code_execution_tool,
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.PythonREPL",
        lambda session_id: SimpleNamespace(cleanup=lambda: None),
    )

    version_config = _build_version_config()
    prompt_calls: list[tuple[str, Any]] = []

    def _get_prompt(key: str, context: dict[str, Any] | None = None) -> str:
        prompt_calls.append((key, context))
        return f"{key} prompt"

    version_config.get_prompt = _get_prompt  # type: ignore[method-assign]

    session = SingleAgentPromoOrchestrator(
        session_id="promo-v2-session",
        chat_history=[ChatEvent(role="user", content="Why is promo ROI down?")],
        llm_service=llm_service,
        skai_service=client,
        version_config=version_config,
    )

    _ = [event async for event in session._single_agent()]

    orchestrator_call = next(
        context for key, context in prompt_calls if key == "orchestrator"
    )
    assert orchestrator_call is not None
    assert orchestrator_call["scoping_framework"] == "A2 scoping"
    assert "A2 planning" in orchestrator_call["planning_framework"]
    assert "A2 promo" in orchestrator_call["planning_framework"]
    assert orchestrator_call["response_structure"] == "A2 response"


@pytest.mark.asyncio
async def test_single_agent_promo_orchestrator_executes_parallel_direct_tools(
    monkeypatch,
):
    client = _build_v2_client()
    llm_service = SimpleNamespace()
    llm_service.request_structured = AsyncMock(
        return_value=IntentClassificationResponse(
            reasoning="Descriptive promo request",
            archetype="A1",
            domain_label="D4",
        )
    )
    llm_service.request_tools_stream = _build_stream(
        [
            _tool_call_event(
                "create_plan",
                {"thinking": "Plan the work", "steps": ["Run analysis", "Summarize"]},
                call_id="create-plan",
            ),
            _multi_tool_call_event(
                [
                    (
                        "skai_get_promo_heatmap",
                        {
                            "thinking": "Fetch heatmap",
                            "x_axis": "brand",
                            "y_axis": "retailer",
                        },
                        "heatmap-1",
                    ),
                    (
                        "code_execution",
                        {"thinking": "Summarize metrics", "code": "print('parallel')"},
                        "code-1",
                    ),
                ]
            ),
            _tool_call_event(
                "move_to_done",
                {"thinking": "Finish", "answer": "Done."},
                call_id="done",
            ),
        ]
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.code_execution_tool",
        _fake_code_execution_tool,
    )
    monkeypatch.setattr(
        "copilot_agents.orchestrator.PythonREPL",
        lambda session_id: SimpleNamespace(cleanup=lambda: None),
    )

    session = SingleAgentPromoOrchestrator(
        session_id="promo-v2-session",
        chat_history=[ChatEvent(role="user", content="Show promo performance")],
        llm_service=llm_service,
        skai_service=client,
        version_config=_build_version_config(),
    )

    events = [event async for event in session._single_agent()]

    tool_result_names = [
        event.tool_name
        for event in events
        if event.event_type == OrchestratorEventType.tool_result
    ]
    assert "skai_get_promo_heatmap" in tool_result_names
    assert "code_execution" in tool_result_names
