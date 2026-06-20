"""Unit tests for evaluation evaluators."""

import pytest

from evaluation.evaluators import (
    archetype_classification_evaluator,
    direct_metrics,
    llm_judge_evaluator,
    llm_judge_evaluator_answer_criteria,
    llm_judge_evaluator_clarity,
    llm_judge_evaluator_completeness,
    llm_judge_evaluator_factual_accuracy,
    llm_judge_evaluator_faithfulness,
    llm_judge_evaluator_relevance,
    llm_judge_evaluator_safety,
)
from langfuse import Evaluation
from schemas.evaluation import EvalDatasetItem, EvalRunResult, LLMJudgeMetrics
from models.copilot.orchestrators import (
    OrchestratorEvent,
    OrchestratorEventType,
    OrchestratorStages,
)


def _make_item(
    item_id: str | None = "item-1",
    content: str = "What is the revenue?",
    reference_answer: str | None = None,
) -> EvalDatasetItem:
    return EvalDatasetItem(
        id=item_id,
        input=content,
        chat_history=[],
        expected_output=reference_answer,
    )


def _make_run_result(
    item: EvalDatasetItem | None = None,
    content: str = "The answer",
    latency_seconds: float = 0.5,
    number_of_turns: int = 1,
    predicted_archetype: str | None = None,
) -> EvalRunResult:
    return EvalRunResult(
        item=item or _make_item(),
        content=content,
        events=[],
        latency_seconds=latency_seconds,
        is_complete=True,
        number_of_turns=number_of_turns,
        session_id="eval-1-abc",
        trace_id="trace-123",
        plan_completion=True,
        predicted_archetype=predicted_archetype,
    )


def _make_orchestrator_event_from_dict(event_dict: dict) -> OrchestratorEvent:
    """Build OrchestratorEvent from a dict (e.g. type, stage, content, tool_name, tool_args, tool_result)."""
    return OrchestratorEvent(
        event_type=OrchestratorEventType(event_dict["type"]),
        stage=OrchestratorStages(event_dict.get("stage", "execution")),
        content=event_dict.get("content", ""),
        tool_name=event_dict.get("tool_name"),
        tool_args=event_dict.get("tool_args"),
        tool_result=event_dict.get("tool_result"),
    )


# --- direct_metrics ---


def _make_run_result_with_events(
    item: EvalDatasetItem | None = None,
    content: str = "The answer",
    latency_seconds: float = 0.5,
    number_of_turns: int = 1,
    events: list[dict] | None = None,
    predicted_archetype: str | None = None,
) -> EvalRunResult:
    """Build EvalRunResult with optional events for event-based metrics."""
    events_resolved = [_make_orchestrator_event_from_dict(e) for e in (events or [])]
    return EvalRunResult(
        item=item or _make_item(),
        content=content,
        events=events_resolved,
        latency_seconds=latency_seconds,
        is_complete=True,
        number_of_turns=number_of_turns,
        session_id="eval-1-abc",
        trace_id="trace-123",
        plan_completion=True,
        predicted_archetype=predicted_archetype,
    )


class TestDirectMetrics:
    """Tests for direct_metrics."""

    @pytest.mark.asyncio
    async def test_returns_all_direct_metric_evaluations(self):
        """Returns eight Evaluation objects: latency, turns, tool_calls, waste, waste_ratio, error_count, has_errors, is_complete."""
        result = _make_run_result(latency_seconds=2.5, number_of_turns=4)
        evs = await direct_metrics(result)
        assert len(evs) == 9
        assert all(isinstance(e, Evaluation) for e in evs)
        latency_ev = next(e for e in evs if e.name == "latency_seconds")
        assert latency_ev.value == 2.5
        assert "latency" in latency_ev.comment.lower()
        turns_ev = next(e for e in evs if e.name == "number_of_turns")
        assert turns_ev.value == 4
        assert "turns" in turns_ev.comment.lower()
        tool_ev = next(e for e in evs if e.name == "number_of_tool_calls")
        assert tool_ev.value == 0
        waste_ev = next(e for e in evs if e.name == "tool_call_waste")
        assert waste_ev.value == 0
        assert "repeated" in waste_ev.comment.lower()
        waste_ratio_ev = next(e for e in evs if e.name == "tool_call_waste_ratio")
        assert waste_ratio_ev.value == 0.0
        err_ev = next(e for e in evs if e.name == "error_count")
        assert err_ev.value == 0
        has_errors_ev = next(e for e in evs if e.name == "has_errors")
        assert has_errors_ev.value == 0.0
        assert "error" in has_errors_ev.comment.lower()
        complete_ev = next(e for e in evs if e.name == "is_complete")
        assert complete_ev.value == 1.0

    @pytest.mark.asyncio
    async def test_direct_metrics_counts_tool_calls_and_errors_from_events(self):
        """number_of_tool_calls, error_count, and has_errors are derived from events."""
        events = [
            {"type": "tool_call", "tool_name": "foo"},
            {"type": "tool_result", "tool_name": "foo", "tool_result": {"x": 1}},
            {"type": "error", "content": "Something failed"},
        ]
        result = _make_run_result_with_events(events=events)
        evs = await direct_metrics(result)
        tool_ev = next(e for e in evs if e.name == "number_of_tool_calls")
        assert tool_ev.value == 2
        err_ev = next(e for e in evs if e.name == "error_count")
        assert err_ev.value == 1
        has_errors_ev = next(e for e in evs if e.name == "has_errors")
        assert has_errors_ev.value == 1.0

    @pytest.mark.asyncio
    async def test_direct_metrics_counts_repeated_tool_calls_as_waste(self):
        """tool_call_waste is count of tool_call events with same (tool_name, tool_args) as a previous call."""
        events = [
            {"type": "tool_call", "tool_name": "get_data", "tool_args": {"id": "a"}},
            {"type": "tool_result", "tool_name": "get_data", "tool_result": {"x": 1}},
            {"type": "tool_call", "tool_name": "get_data", "tool_args": {"id": "a"}},
            {"type": "tool_result", "tool_name": "get_data", "tool_result": {"x": 1}},
        ]
        result = _make_run_result_with_events(events=events)
        evs = await direct_metrics(result)
        tool_ev = next(e for e in evs if e.name == "number_of_tool_calls")
        assert tool_ev.value == 4
        waste_ev = next(e for e in evs if e.name == "tool_call_waste")
        assert waste_ev.value == 1
        waste_ratio_ev = next(e for e in evs if e.name == "tool_call_waste_ratio")
        assert waste_ratio_ev.value == 0.5


# --- archetype_classification_evaluator ---


class TestArchetypeClassificationEvaluator:
    """Tests for archetype_classification_evaluator."""

    @pytest.mark.asyncio
    async def test_returns_none_when_expected_archetype_missing(self):
        """Returns None when item has no expected_archetype."""
        item = _make_item()
        assert getattr(item, "expected_archetype", None) is None
        result = _make_run_result(item=item, predicted_archetype="A1")
        evs = await archetype_classification_evaluator(result)
        assert evs is None

    @pytest.mark.asyncio
    async def test_returns_none_when_predicted_archetype_missing(self):
        """Returns None when result has no predicted_archetype."""
        item = EvalDatasetItem(
            id="item-1",
            input="Question?",
            chat_history=[],
            expected_archetype="A1",
        )
        result = _make_run_result(item=item, predicted_archetype=None)
        evs = await archetype_classification_evaluator(result)
        assert evs is None

    @pytest.mark.asyncio
    async def test_returns_one_when_match(self):
        """Returns one Evaluation with value 1.0 when expected and predicted match."""
        item = EvalDatasetItem(
            id="item-1",
            input="Question?",
            chat_history=[],
            expected_archetype="A2",
        )
        result = _make_run_result(item=item, predicted_archetype="A2")
        evs = await archetype_classification_evaluator(result)
        assert evs is not None
        assert len(evs) == 1
        assert evs[0].name == "archetype_match"
        assert evs[0].value == 1.0
        assert "A2" in evs[0].comment

    @pytest.mark.asyncio
    async def test_returns_zero_when_mismatch(self):
        """Returns one Evaluation with value 0.0 when expected and predicted differ."""
        item = EvalDatasetItem(
            id="item-1",
            input="Question?",
            chat_history=[],
            expected_archetype="A1",
        )
        result = _make_run_result(item=item, predicted_archetype="A3")
        evs = await archetype_classification_evaluator(result)
        assert evs is not None
        assert len(evs) == 1
        assert evs[0].name == "archetype_match"
        assert evs[0].value == 0.0


# --- llm_judge_evaluator_answer_criteria ---


class TestLlmJudgeEvaluatorAnswerCriteria:
    """Tests for llm_judge_evaluator_answer_criteria."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_criteria(self):
        """Returns None when item has no expected_answer_criteria."""
        item = _make_item()
        result = _make_run_result(item=item)
        evs = await llm_judge_evaluator_answer_criteria(result)
        assert evs is None

    @pytest.mark.asyncio
    async def test_returns_evaluation_when_criteria_present(self, mocker):
        """Returns one Evaluation when criteria present and client returns LLMJudgeMetrics."""
        item = EvalDatasetItem(
            id="item-1",
            input="Question?",
            chat_history=[],
            expected_answer_criteria=["Answer must cover X.", "Answer must cover Y."],
        )
        result = _make_run_result(item=item, content="The answer covers X and Y.")
        mock_response = LLMJudgeMetrics(
            name="answer_criteria",
            rating="Good",
            reasoning="Criteria mostly satisfied.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )
        evs = await llm_judge_evaluator_answer_criteria(result)
        assert evs is not None
        assert len(evs) == 1
        assert evs[0].name == "answer_criteria"
        assert evs[0].value == 0.6
        assert evs[0].comment == "Criteria mostly satisfied."


# --- llm_judge_evaluator ---


class TestLlmJudgeEvaluator:
    """Tests for llm_judge_evaluator."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_reference_and_factual_accuracy(self, mocker):
        """Returns None when expected_output has no reference_answer and metric is factual_accuracy."""
        item = _make_item(reference_answer=None)
        result = _make_run_result(item=item, content="Some answer")
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mocker.MagicMock(),
        )

        evs = await llm_judge_evaluator(result, "factual_accuracy")

        assert evs is None

    @pytest.mark.asyncio
    async def test_returns_evaluation_when_reference_present(self, mocker):
        """Returns list of one Evaluation when reference present and client returns LLMJudgeMetrics."""
        item = _make_item(reference_answer="Expected answer")
        result = _make_run_result(item=item, content="The assistant said X")
        mock_response = LLMJudgeMetrics(
            name="factual_accuracy",
            rating="Good",
            reasoning="Mostly correct.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )

        evs = await llm_judge_evaluator(result, "factual_accuracy")

        assert evs is not None
        assert len(evs) == 1
        assert evs[0].name == "factual_accuracy"
        assert evs[0].value == 0.6  # Good -> 0.6
        assert evs[0].comment == "Mostly correct."

    @pytest.mark.asyncio
    async def test_prompt_includes_input_reference_and_output(self, mocker):
        """request_structured is called with prompt containing user input, reference, and output."""
        item = _make_item(content="User question?", reference_answer="Ref answer")
        result = _make_run_result(item=item, content="Model output here")
        mock_response = LLMJudgeMetrics(
            name="relevance",
            rating="Excellent",
            reasoning="Fully relevant.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )

        await llm_judge_evaluator(result, "relevance")

        mock_client.request_structured.assert_called_once()
        call_args = mock_client.request_structured.call_args
        chat_history = call_args[0][0]
        assert len(chat_history) == 1
        prompt = chat_history[0].content
        assert "User question?" in prompt
        assert "Ref answer" in prompt
        assert "Model output here" in prompt
        assert "Relevance" in prompt or "relevance" in prompt

    @pytest.mark.asyncio
    async def test_calls_request_structured_with_gpt5_mini_and_llm_judge_metrics(
        self, mocker
    ):
        """Uses model gpt-5-mini and response type LLMJudgeMetrics."""
        item = _make_item(reference_answer="Ref")
        result = _make_run_result(item=item)
        mock_response = LLMJudgeMetrics(
            name="clarity",
            rating="Fair",
            reasoning="Okay.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )

        await llm_judge_evaluator(result, "clarity")

        call_args = mock_client.request_structured.call_args
        assert call_args[0][1] == "gpt-5-mini"
        assert call_args[0][2] is LLMJudgeMetrics
        assert call_args[1].get("reasoning_effort") is None

    @pytest.mark.asyncio
    async def test_uses_no_reference_placeholder_when_expected_output_none(
        self, mocker
    ):
        """When expected_output is None, prompt contains (No reference answer provided)."""
        item = _make_item(reference_answer=None)
        result = _make_run_result(item=item, content="Out")
        mock_response = LLMJudgeMetrics(
            name="relevance",
            rating="Good",
            reasoning="Relevant.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )

        await llm_judge_evaluator(result, "relevance")

        prompt = mock_client.request_structured.call_args[0][0][0].content
        assert "(No reference answer provided)" in prompt

    @pytest.mark.asyncio
    async def test_score_maps_rating_to_float(self, mocker):
        """Evaluation value is the score from LLMJudgeMetrics (0.0–1.0)."""
        item = _make_item(reference_answer="Ref")
        result = _make_run_result(item=item)
        for rating, expected_score in [
            ("ExtremelyPoor", 0.0),
            ("Poor", 0.2),
            ("Fair", 0.4),
            ("Good", 0.6),
            ("Excellent", 1.0),
        ]:
            mock_response = LLMJudgeMetrics(
                name="clarity",
                rating=rating,
                reasoning="Ok",
            )
            mock_client = mocker.MagicMock()
            mock_client.request_structured = mocker.AsyncMock(
                return_value=mock_response,
            )
            mocker.patch(
                "evaluation.evaluators.AsyncOpenaiClient",
                return_value=mock_client,
            )

            evs = await llm_judge_evaluator(result, "clarity")

            assert evs is not None
            assert len(evs) == 1
            assert evs[0].value == expected_score


# --- llm_judge_evaluator_factual_accuracy, _relevance, _clarity ---


class TestLlmJudgeEvaluatorDelegates:
    """Tests that metric-specific evaluators delegate to llm_judge_evaluator."""

    @pytest.mark.asyncio
    async def test_factual_accuracy_calls_llm_judge_with_factual_accuracy(self, mocker):
        """llm_judge_evaluator_factual_accuracy calls llm_judge_evaluator(output, 'factual_accuracy')."""
        result = _make_run_result(item=_make_item(reference_answer="Ref"))
        mock_judge = mocker.AsyncMock(return_value=[mocker.MagicMock()])
        mocker.patch(
            "evaluation.evaluators.llm_judge_evaluator",
            mock_judge,
        )

        await llm_judge_evaluator_factual_accuracy(result)

        mock_judge.assert_called_once_with(result, "factual_accuracy")

    @pytest.mark.asyncio
    async def test_relevance_calls_llm_judge_with_relevance(self, mocker):
        """llm_judge_evaluator_relevance calls llm_judge_evaluator(output, 'relevance')."""
        result = _make_run_result(item=_make_item())
        mock_judge = mocker.AsyncMock(return_value=[mocker.MagicMock()])
        mocker.patch(
            "evaluation.evaluators.llm_judge_evaluator",
            mock_judge,
        )

        await llm_judge_evaluator_relevance(result)

        mock_judge.assert_called_once_with(result, "relevance")

    @pytest.mark.asyncio
    async def test_clarity_calls_llm_judge_with_clarity(self, mocker):
        """llm_judge_evaluator_clarity calls llm_judge_evaluator(output, 'clarity')."""
        result = _make_run_result(item=_make_item())
        mock_judge = mocker.AsyncMock(return_value=[mocker.MagicMock()])
        mocker.patch(
            "evaluation.evaluators.llm_judge_evaluator",
            mock_judge,
        )

        await llm_judge_evaluator_clarity(result)

        mock_judge.assert_called_once_with(result, "clarity")


# --- llm_judge_evaluator_faithfulness ---


class TestLlmJudgeEvaluatorFaithfulness:
    """Tests for llm_judge_evaluator_faithfulness (no expected values)."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_tool_results(self):
        """Returns None when events contain no tool_result events."""
        result = _make_run_result(item=_make_item(), content="Some answer")
        evs = await llm_judge_evaluator_faithfulness(result)
        assert evs is None

    @pytest.mark.asyncio
    async def test_returns_evaluation_when_tool_results_present(self, mocker):
        """Returns one Evaluation when events contain tool_result and client returns metrics."""
        events = [
            {
                "type": "tool_result",
                "tool_name": "get_data",
                "tool_result": {"value": 42},
            },
        ]
        result = _make_run_result_with_events(
            item=_make_item(), content="The value is 42.", events=events
        )
        mock_response = LLMJudgeMetrics(
            name="faithfulness",
            rating="Excellent",
            reasoning="Fully grounded.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )

        evs = await llm_judge_evaluator_faithfulness(result)

        assert evs is not None
        assert len(evs) == 1
        assert evs[0].name == "faithfulness"
        assert evs[0].value == 1.0
        assert evs[0].comment == "Fully grounded."


# --- llm_judge_evaluator_completeness, _safety ---


class TestLlmJudgeEvaluatorCompletenessAndSafety:
    """Tests that completeness and safety run without reference (no expected values)."""

    @pytest.mark.asyncio
    async def test_completeness_calls_llm_judge_with_completeness(self, mocker):
        """llm_judge_evaluator_completeness runs and returns evaluation (no reference needed)."""
        item = _make_item(reference_answer=None)
        result = _make_run_result(item=item, content="Answer")
        mock_response = LLMJudgeMetrics(
            name="completeness",
            rating="Good",
            reasoning="Most aspects covered.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )

        evs = await llm_judge_evaluator_completeness(result)

        assert evs is not None
        assert len(evs) == 1
        assert evs[0].name == "completeness"
        assert evs[0].value == 0.6

    @pytest.mark.asyncio
    async def test_safety_calls_llm_judge_with_safety(self, mocker):
        """llm_judge_evaluator_safety runs and returns evaluation (no reference needed)."""
        item = _make_item(reference_answer=None)
        result = _make_run_result(item=item, content="Answer")
        mock_response = LLMJudgeMetrics(
            name="safety",
            rating="Excellent",
            reasoning="Fully safe.",
        )
        mock_client = mocker.MagicMock()
        mock_client.request_structured = mocker.AsyncMock(return_value=mock_response)
        mocker.patch(
            "evaluation.evaluators.AsyncOpenaiClient",
            return_value=mock_client,
        )

        evs = await llm_judge_evaluator_safety(result)

        assert evs is not None
        assert len(evs) == 1
        assert evs[0].name == "safety"
        assert evs[0].value == 1.0
