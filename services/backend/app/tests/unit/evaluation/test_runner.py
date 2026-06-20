"""Unit tests for evaluation runner."""

import uuid

import pytest

from config.versioning import (
    CopilotVersionConfig,
    ExecutionAgentConfig,
    ResolvedVersion,
)
from evaluation.runner import run_orchestrator_for_item
from models.copilot.orchestrators import (
    OrchestratorEvent,
    OrchestratorEventType,
    OrchestratorStages,
)
from schemas.evaluation import EvalDatasetItem


def _make_item(
    item_id: str | None = "item-1",
    content: str = "What is the revenue?",
) -> EvalDatasetItem:
    return EvalDatasetItem(
        id=item_id,
        input=content,
        chat_history=[],
        answerable_by_dataset=True,
    )


@pytest.fixture
def mock_llm_service(mocker):
    return mocker.MagicMock()


@pytest.fixture
def mock_skai_service(mocker):
    return mocker.MagicMock()


def _attach_plan_and_progress(mock_session, steps=None, plan_progress=None):
    """Set plan.steps and plan_progress so EvalRunResult gets valid types."""
    mock_session.plan = type(
        "Plan", (), {"steps": steps if steps is not None else []}
    )()
    mock_session.plan_progress = plan_progress if plan_progress is not None else [True]


@pytest.fixture
def sample_item():
    return _make_item(item_id="item-1", content="Hello")


@pytest.fixture
def resolved_version():
    """Minimal ResolvedVersion for tests (OrchestratorSession is mocked)."""
    config = CopilotVersionConfig(
        version="test",
        execution_agents=[
            ExecutionAgentConfig(
                domain="category",
                name="Category Agent",
                description="Test",
                prompt_id="base:v1",
            ),
        ],
        prompts={"orchestrator": "base:v1"},
    )
    return ResolvedVersion(config=config)


class TestRunOrchestratorForItem:
    """Tests for run_orchestrator_for_item."""

    @pytest.mark.asyncio
    async def test_returns_eval_run_result_with_provided_run_id(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """Uses provided run_id and builds session_id as eval-{item_id}-{run_id}."""
        run_id = "my-run-123"
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.final_answer = "Done"
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def one_event(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="ok",
            )

        mock_session.execute = one_event
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            run_id=run_id,
            resolved_version=resolved_version,
        )

        assert result.session_id == "eval-item-1-my-run-123"
        assert result.is_complete is True
        assert result.content == "Done"
        assert result.number_of_turns == 1
        assert result.item == sample_item
        assert len(result.events) == 1
        assert result.events[0].event_type == OrchestratorEventType.content
        assert result.latency_seconds >= 0
        assert result.predicted_archetype == "A1"

    @pytest.mark.asyncio
    async def test_generates_run_id_when_not_provided(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """Generates a UUID run_id when run_id is None."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.final_answer = ""
        mock_session.last_answer = ""
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def one_event(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="",
            )

        mock_session.execute = one_event
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            run_id=None,
            resolved_version=resolved_version,
        )

        assert result.session_id.startswith("eval-item-1-")
        # Session id suffix should be a valid UUID (run_id)
        suffix = result.session_id.replace("eval-item-1-", "")
        uuid.UUID(suffix)

    @pytest.mark.asyncio
    async def test_item_id_unknown_when_item_id_is_none(
        self, mocker, mock_llm_service, mock_skai_service, resolved_version
    ):
        """Session id uses 'unknown' when item.id is None."""
        item = _make_item(item_id=None, content="Hi")
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.final_answer = ""
        mock_session.last_answer = ""
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def one_event(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="",
            )

        mock_session.execute = one_event
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            run_id="r1",
            resolved_version=resolved_version,
        )

        assert result.session_id == "eval-unknown-r1"

    @pytest.mark.asyncio
    async def test_single_turn_complete_returns_one_turn(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """Single execute loop with is_complete=True yields number_of_turns=1."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.final_answer = "The answer"
        mock_session.last_answer = ""
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def one_event(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="The answer",
            )

        mock_session.execute = one_event
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            resolved_version=resolved_version,
        )

        assert result.number_of_turns == 1
        assert result.is_complete is True
        assert result.content == "The answer"

    @pytest.mark.asyncio
    async def test_request_info_with_actions_uses_first_action_as_follow_up(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """When request_info has metadata.actions, next turn uses first action."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = False
        mock_session.final_answer = ""
        mock_session.last_answer = ""
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        first_turn = True

        async def events_with_request_info():
            nonlocal first_turn
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.request_info,
                stage=OrchestratorStages.execution,
                content="Need input",
                metadata={"actions": ["Option A", "Option B"]},
            )
            if first_turn:
                first_turn = False
                mock_session.is_complete = False
            else:
                mock_session.is_complete = True

        async def second_turn_events():
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="Done",
            )

        call_count = 0

        async def execute(trace_id=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                async for e in events_with_request_info():
                    yield e
            else:
                mock_session.is_complete = True
                mock_session.final_answer = "Done"
                async for e in second_turn_events():
                    yield e

        mock_session.execute = execute
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            run_id="r1",
            resolved_version=resolved_version,
        )

        assert result.number_of_turns == 2
        assert result.content == "Done"
        # First follow-up message should be first action
        user_contents = [
            getattr(ce, "content", None)
            for ce in mock_session.chat_history
            if getattr(ce, "role", None) == "user"
        ]
        assert "Option A" in user_contents

    @pytest.mark.asyncio
    async def test_request_info_without_actions_uses_freedom_message(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """When request_info has no actions, next message is 'You have freedom to make assumptions for me'."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = False
        mock_session.final_answer = ""
        mock_session.last_answer = ""
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        call_count = 0

        async def execute(trace_id=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield OrchestratorEvent(
                    event_type=OrchestratorEventType.request_info,
                    stage=OrchestratorStages.execution,
                    content="Need input",
                    metadata={},
                )
                mock_session.is_complete = False
            else:
                mock_session.is_complete = True
                mock_session.final_answer = "Done"
                yield OrchestratorEvent(
                    event_type=OrchestratorEventType.content,
                    stage=OrchestratorStages.done,
                    content="Done",
                )

        mock_session.execute = execute
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            run_id="r1",
            resolved_version=resolved_version,
        )

        assert result.number_of_turns == 2
        assert result.content == "Done"
        user_contents = [
            getattr(ce, "content", None)
            for ce in mock_session.chat_history
            if getattr(ce, "role", None) == "user"
        ]
        assert "You have freedom to make assumptions for me" in user_contents

    @pytest.mark.asyncio
    async def test_stops_after_four_turns(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """Loop breaks when number_of_turns > 4 even if not complete."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = False
        mock_session.final_answer = ""
        mock_session.last_answer = ""
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def always_request_info(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.request_info,
                stage=OrchestratorStages.execution,
                content="Again",
                metadata={"actions": ["next"]},
            )

        mock_session.execute = always_request_info
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            run_id="r1",
            resolved_version=resolved_version,
        )

        assert result.number_of_turns == 5
        assert result.is_complete is False
        assert result.content == "Again"

    @pytest.mark.asyncio
    async def test_events_serialized_via_to_sse_dict(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """All events are appended as OrchestratorEvent instances."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.final_answer = "x"
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def two_events(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.progress,
                stage=OrchestratorStages.scoping,
                content="step 1",
            )
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="x",
            )

        mock_session.execute = two_events
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            resolved_version=resolved_version,
        )

        assert len(result.events) == 2
        assert result.events[0].event_type == OrchestratorEventType.progress
        assert result.events[0].stage == OrchestratorStages.scoping
        assert result.events[1].event_type == OrchestratorEventType.content
        assert result.events[1].stage == OrchestratorStages.done

    @pytest.mark.asyncio
    async def test_trace_id_created_per_turn_and_returned_in_result(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """trace_id is created by the runner per turn and result holds the last turn's trace_id."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.final_answer = ""
        mock_session.last_answer = ""
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def one_event(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="",
            )

        mock_session.execute = one_event
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )
        mocker.patch(
            "evaluation.runner.create_trace_id",
            return_value="trace-from-runner",
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            resolved_version=resolved_version,
        )

        assert result.trace_id == "trace-from-runner"

    @pytest.mark.asyncio
    async def test_final_answer_empty_becomes_empty_output(
        self, mocker, sample_item, mock_llm_service, mock_skai_service, resolved_version
    ):
        """When session.final_answer is None or empty, output is empty string."""
        mock_session = mocker.MagicMock()
        mock_session.chat_history = []
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.final_answer = None
        mock_session.last_answer = None
        mock_session.classification = {"question_archetype": "A1"}
        _attach_plan_and_progress(mock_session)

        async def one_event(trace_id=None):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="",
            )

        mock_session.execute = one_event
        mocker.patch(
            "evaluation.runner.get_orchestrator_session", return_value=mock_session
        )

        result = await run_orchestrator_for_item(
            sample_item,
            llm_service=mock_llm_service,
            skai_service=mock_skai_service,
            resolved_version=resolved_version,
        )

        assert result.content == ""
