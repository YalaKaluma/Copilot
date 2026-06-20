"""Unit tests for OrchestratorService session-id and assistant_message_id handling."""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from models.copilot.orchestrators import (
    OrchestratorEvent,
    OrchestratorEventType,
    OrchestratorStages,
)
from models.copilot.base import ChatEvent
from schemas.orchestrator import OrchestratorChatRequest
from services.orchestrator_service import OrchestratorService


class TestOrchestratorServiceInvoke:
    """Test invoke() session-id normalization and assistant_message_id passing."""

    @pytest.mark.asyncio
    async def test_stream_invoke_forwards_session_id(self):
        """Session ID is passed through to _invoke_stream (resolution is in router)."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        observed_session_ids: list[str] = []

        async def fake_invoke_stream(
            request,
            session_id,
            assistant_message_id,
            user_id,
            user_email_id=None,
            skai_service=None,
            **kwargs,
        ):
            observed_session_ids.append(session_id)
            yield "ok"

        service._invoke_stream = fake_invoke_stream  # type: ignore[method-assign]

        skai_service = object()
        async for _ in service.invoke(
            OrchestratorChatRequest(messages=[{"role": "user", "content": "first"}]),
            session_id="session-one",
            assistant_message_id=uuid4(),
            user_id="user-1",
            stream=True,
            skai_service=skai_service,
        ):
            pass

        async for _ in service.invoke(
            OrchestratorChatRequest(messages=[{"role": "user", "content": "second"}]),
            session_id="session-two",
            assistant_message_id=uuid4(),
            user_id="user-1",
            stream=True,
            skai_service=skai_service,
        ):
            pass

        assert len(observed_session_ids) == 2
        assert observed_session_ids[0] == "session-one"
        assert observed_session_ids[1] == "session-two"

    @pytest.mark.asyncio
    async def test_non_stream_invoke_preserves_explicit_session_id(self):
        """An explicit session_id should be passed through unchanged."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        observed_session_ids: list[str] = []

        async def fake_invoke_text(
            request,
            session_id,
            assistant_message_id,
            user_id,
            user_email_id=None,
            skai_service=None,
            **kwargs,
        ):
            observed_session_ids.append(session_id)
            return "ok"

        service._invoke_text = fake_invoke_text  # type: ignore[method-assign]

        skai_service = object()
        async for _ in service.invoke(
            OrchestratorChatRequest(messages=[{"role": "user", "content": "hello"}]),
            session_id="explicit-session-id",
            assistant_message_id=uuid4(),
            user_id="user-1",
            stream=False,
            skai_service=skai_service,
        ):
            pass

        assert observed_session_ids == ["explicit-session-id"]

    @pytest.mark.asyncio
    async def test_stream_invoke_passes_assistant_message_id_to_invoke_stream(self):
        """assistant_message_id is passed through to _invoke_stream for trace and done event."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        observed_assistant_message_ids: list = []

        async def fake_invoke_stream(
            request,
            session_id,
            assistant_message_id,
            user_id,
            user_email_id=None,
            skai_service=None,
            **kwargs,
        ):
            observed_assistant_message_ids.append(assistant_message_id)
            yield "ok"

        service._invoke_stream = fake_invoke_stream  # type: ignore[method-assign]

        expected_id = uuid4()
        skai_service = object()
        async for _ in service.invoke(
            OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}]),
            session_id="s1",
            assistant_message_id=expected_id,
            user_id="user-1",
            stream=True,
            skai_service=skai_service,
        ):
            pass

        assert len(observed_assistant_message_ids) == 1
        assert observed_assistant_message_ids[0] == expected_id

    @pytest.mark.asyncio
    async def test_non_stream_invoke_passes_assistant_message_id_to_invoke_text(self):
        """assistant_message_id is passed through to _invoke_text."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        observed_assistant_message_ids: list = []

        async def fake_invoke_text(
            request,
            session_id,
            assistant_message_id,
            user_id,
            user_email_id=None,
            skai_service=None,
            **kwargs,
        ):
            observed_assistant_message_ids.append(assistant_message_id)
            return "ok"

        service._invoke_text = fake_invoke_text  # type: ignore[method-assign]

        expected_id = uuid4()
        skai_service = object()
        async for _ in service.invoke(
            OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}]),
            session_id="s1",
            assistant_message_id=expected_id,
            user_id="user-1",
            stream=False,
            skai_service=skai_service,
        ):
            pass

        assert len(observed_assistant_message_ids) == 1
        assert observed_assistant_message_ids[0] == expected_id

    @pytest.mark.asyncio
    async def test_invoke_stream_done_event_includes_message_id(self, mocker):
        """Streamed done event includes message_id from assistant_message_id (Phase 2)."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        mock_session = mocker.Mock()
        mock_session.stream_final_answer = True
        mock_session.is_complete = False
        mock_session.final_answer = "Done."
        mock_session.plan = None
        # Must be JSON-serializable (stage.value is used in sse_event)
        mock_session.current_stage = SimpleNamespace(value="done")

        async def execute_yield_stage_complete_done(*args, **kwargs):
            # Yield one event that the service skips (stage_complete + stage=done),
            # so the stream continues to the service's "done" event.
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.stage_complete,
                stage=OrchestratorStages.done,
                content="Workflow complete",
            )

        mock_session.execute = execute_yield_stage_complete_done
        mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )

        expected_id = uuid4()
        request = OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}])
        chunks: list[str] = []
        async for chunk in service._invoke_stream(
            request,
            session_id="s1",
            assistant_message_id=expected_id,
            user_id="user-1",
            skai_service=mocker.Mock(),
        ):
            chunks.append(chunk)

        done_lines = [
            line.strip()
            for line in chunks
            if line.strip().startswith("data: ") and line.strip() != "data: [DONE]"
        ]
        done_payloads = []
        for line in done_lines:
            data = line[6:].strip()
            if data and data != "[DONE]":
                try:
                    done_payloads.append(json.loads(data))
                except json.JSONDecodeError:
                    pass
        done_events = [p for p in done_payloads if p.get("type") == "done"]
        assert len(done_events) == 1
        assert done_events[0].get("message_id") == str(expected_id)


class TestOrchestratorServiceOnlineEvalDispatch:
    """Test that online evaluation is dispatched as a non-blocking background task."""

    @pytest.fixture(autouse=True)
    def _patch_evaluate_online(self, mocker):
        """Patch evaluate_online so tests never call LLM (OPENAI_API_KEY not required in CI)."""
        mocker.patch(
            "copilot_agents.orchestrator.evaluate_online",
            new_callable=AsyncMock,
            return_value=None,
        )

    @pytest.mark.asyncio
    async def test_stream_schedules_online_evals_when_complete_and_langfuse_enabled(
        self, mocker
    ):
        """When session is complete and Langfuse enabled, run_online_evals is scheduled."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        mock_session = mocker.Mock()
        mock_session.stream_final_answer = True
        mock_session.is_complete = True
        mock_session.final_answer = "Done."
        mock_session.plan = None
        mock_session.current_stage = SimpleNamespace(value="done")

        run_online_evals_calls = []
        run_online_evals_started = asyncio.Event()

        async def capture_run_online_evals(trace_id):
            run_online_evals_calls.append(trace_id)
            run_online_evals_started.set()
            await asyncio.sleep(0.05)

        mock_session.run_online_evals = capture_run_online_evals

        one_content_event = OrchestratorEvent(
            event_type=OrchestratorEventType.content,
            stage=OrchestratorStages.done,
            content="Final answer",
        )

        async def execute_yield_one(*args, **kwargs):
            yield one_content_event

        mock_session.execute = execute_yield_one
        mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )
        mocker.patch(
            "services.orchestrator_service.is_langfuse_enabled",
            return_value=True,
        )
        create_task_spy = mocker.patch(
            "services.orchestrator_service.asyncio.create_task",
            wraps=asyncio.create_task,
        )

        assistant_message_id = uuid4()
        request = OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}])
        chunks = []
        async for chunk in service._invoke_stream(
            request,
            session_id="s1",
            assistant_message_id=assistant_message_id,
            user_id="user-1",
            skai_service=mocker.Mock(),
        ):
            chunks.append(chunk)

        assert len(chunks) > 0, "Stream should yield at least the done event"
        assert create_task_spy.called
        await run_online_evals_started.wait()
        assert len(run_online_evals_calls) == 1
        from services.tracing import to_trace_id

        assert run_online_evals_calls[0] == to_trace_id(assistant_message_id)

    @pytest.mark.asyncio
    async def test_stream_online_evals_non_blocking(self, mocker):
        """Stream returns immediately without waiting for run_online_evals to finish."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        mock_session = mocker.Mock()
        mock_session.stream_final_answer = True
        mock_session.is_complete = True
        mock_session.final_answer = "Done."
        mock_session.plan = None
        mock_session.current_stage = SimpleNamespace(value="done")

        async def slow_run_online_evals(trace_id):
            await asyncio.sleep(0.4)

        mock_session.run_online_evals = slow_run_online_evals

        one_event = OrchestratorEvent(
            event_type=OrchestratorEventType.content,
            stage=OrchestratorStages.done,
            content="Done",
        )

        async def execute_yield_one(*args, **kwargs):
            yield one_event

        mock_session.execute = execute_yield_one
        mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )
        mocker.patch(
            "services.orchestrator_service.is_langfuse_enabled",
            return_value=True,
        )

        request = OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}])
        start = time.monotonic()
        chunks = []
        async for chunk in service._invoke_stream(
            request,
            session_id="s1",
            assistant_message_id=uuid4(),
            user_id="user-1",
            skai_service=mocker.Mock(),
        ):
            chunks.append(chunk)
        elapsed = time.monotonic() - start

        assert len(chunks) > 0, "Stream should yield at least the done event"
        assert elapsed < 0.25, "Stream must complete without waiting for online evals"

    @pytest.mark.asyncio
    async def test_stream_does_not_schedule_online_evals_when_langfuse_disabled(
        self, mocker
    ):
        """When Langfuse is disabled, run_online_evals is not scheduled."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        mock_session = mocker.Mock()
        mock_session.stream_final_answer = True
        mock_session.is_complete = True
        mock_session.final_answer = "Done."
        mock_session.plan = None
        mock_session.current_stage = SimpleNamespace(value="done")

        run_online_evals_called = []

        async def capture_run_online_evals(trace_id):
            run_online_evals_called.append(trace_id)

        mock_session.run_online_evals = capture_run_online_evals

        one_event = OrchestratorEvent(
            event_type=OrchestratorEventType.content,
            stage=OrchestratorStages.done,
            content="Done",
        )

        async def execute_yield_one(*args, **kwargs):
            yield one_event

        mock_session.execute = execute_yield_one
        mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )
        mocker.patch(
            "services.orchestrator_service.is_langfuse_enabled",
            return_value=False,
        )
        create_task_spy = mocker.patch(
            "services.orchestrator_service.asyncio.create_task",
        )

        request = OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}])
        async for _ in service._invoke_stream(
            request,
            session_id="s1",
            assistant_message_id=uuid4(),
            user_id="user-1",
            skai_service=mocker.Mock(),
        ):
            pass

        assert not create_task_spy.called
        assert len(run_online_evals_called) == 0

    @pytest.mark.asyncio
    async def test_stream_does_not_schedule_online_evals_when_waiting_for_info(
        self, mocker
    ):
        """When session is waiting for user info (not complete), run_online_evals not scheduled."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        mock_session = mocker.Mock()
        mock_session.stream_final_answer = True
        mock_session.is_complete = False
        mock_session.final_answer = None
        mock_session.plan = None
        mock_session.current_stage = SimpleNamespace(value="scoping")

        request_info_event = OrchestratorEvent(
            event_type=OrchestratorEventType.request_info,
            stage=OrchestratorStages.scoping,
            content="Need more info",
        )

        async def execute_yield_request_info(*args, **kwargs):
            yield request_info_event

        mock_session.execute = execute_yield_request_info
        mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )
        mocker.patch(
            "services.orchestrator_service.is_langfuse_enabled",
            return_value=True,
        )
        create_task_spy = mocker.patch(
            "services.orchestrator_service.asyncio.create_task",
        )

        request = OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}])
        chunks = []
        async for chunk in service._invoke_stream(
            request,
            session_id="s1",
            assistant_message_id=uuid4(),
            user_id="user-1",
            skai_service=mocker.Mock(),
        ):
            chunks.append(chunk)

        assert any("waiting_for_info" in c for c in chunks)
        assert not create_task_spy.called

    @pytest.mark.asyncio
    async def test_non_stream_schedules_online_evals_when_complete_and_langfuse_enabled(
        self, mocker
    ):
        """Non-streaming invoke schedules run_online_evals when complete and Langfuse enabled."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        mock_session = mocker.Mock()
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.plan = None

        run_online_evals_calls = []

        async def capture_run_online_evals(trace_id):
            run_online_evals_calls.append(trace_id)

        mock_session.run_online_evals = capture_run_online_evals

        one_event = OrchestratorEvent(
            event_type=OrchestratorEventType.content,
            stage=OrchestratorStages.done,
            content="Result",
        )

        async def execute_yield_one(*args, **kwargs):
            yield one_event

        mock_session.execute = execute_yield_one
        mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )
        mocker.patch(
            "services.orchestrator_service.is_langfuse_enabled",
            return_value=True,
        )
        create_task_spy = mocker.patch(
            "services.orchestrator_service.asyncio.create_task",
            wraps=asyncio.create_task,
        )

        request = OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}])
        result = await service._invoke_text(
            request,
            session_id="s1",
            assistant_message_id=uuid4(),
            user_id="user-1",
            skai_service=mocker.Mock(),
        )

        assert "result" in result.lower() or "done" in result.lower()
        assert create_task_spy.called
        await asyncio.sleep(0.02)
        assert len(run_online_evals_calls) == 1

    @pytest.mark.asyncio
    async def test_non_stream_online_evals_non_blocking(self, mocker):
        """Non-streaming invoke returns immediately without waiting for run_online_evals."""
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        mock_session = mocker.Mock()
        mock_session.stream_final_answer = False
        mock_session.is_complete = True
        mock_session.plan = None

        async def slow_run_online_evals(trace_id):
            await asyncio.sleep(0.4)

        mock_session.run_online_evals = slow_run_online_evals

        one_event = OrchestratorEvent(
            event_type=OrchestratorEventType.content,
            stage=OrchestratorStages.done,
            content="Done",
        )

        async def execute_yield_one(*args, **kwargs):
            yield one_event

        mock_session.execute = execute_yield_one
        mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )
        mocker.patch(
            "services.orchestrator_service.is_langfuse_enabled",
            return_value=True,
        )

        request = OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}])
        start = time.monotonic()
        result = await service._invoke_text(
            request,
            session_id="s1",
            assistant_message_id=uuid4(),
            user_id="user-1",
            skai_service=mocker.Mock(),
        )
        elapsed = time.monotonic() - start

        assert result
        assert elapsed < 0.25, "Non-stream invoke must not wait for online evals"


class TestOrchestratorServiceGetOrCreateSession:
    def test_get_or_create_session_raises_when_llm_not_configured(self, mocker):
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        request = OrchestratorChatRequest(messages=[])

        with pytest.raises(RuntimeError):
            service._get_or_create_session(
                session_id="session-1",
                user_id="user-1",
                request=request,
                skai_service=mocker.Mock(),
            )

    def test_get_or_create_session_creates_new_session_with_default_version(
        self, mocker
    ):
        settings = SimpleNamespace(
            openai_api_key=None, skai_copilot_version="v-default"
        )
        service = OrchestratorService(settings)
        service._llm_client = object()

        version = SimpleNamespace(
            config=SimpleNamespace(version="v-default", orchestrator_version="v1")
        )
        mock_get_version = mocker.patch(
            "services.orchestrator_service.get_copilot_version",
            return_value=version,
        )

        created_sessions: list[object] = []

        class FakeSession:
            def __init__(
                self,
                version_config: object,
                session_id: str,
                chat_history: list[ChatEvent],
                skai_service: object,
                llm_service: object,
                *,
                filter_options=None,
            ):
                self.session_id = session_id
                self.chat_history = list(chat_history)
                self.llm_service = llm_service
                self.skai_service = skai_service
                self.version_config = version_config
                self.version_id = getattr(version_config, "version_id", None)
                self.waiting_for_info = False
                created_sessions.append(self)

        mocker.patch(
            "services.orchestrator_service.get_orchestrator_session",
            FakeSession,
        )

        chat_history = [
            ChatEvent(role="user", content="hello"),
        ]
        request = OrchestratorChatRequest(messages=chat_history)
        skai_service = mocker.Mock()

        session = service._get_or_create_session(
            session_id="session-1",
            user_id="user-1",
            request=request,
            skai_service=skai_service,
        )

        assert isinstance(session, FakeSession)
        assert session.session_id == "session-1"
        assert session.chat_history == chat_history
        key = service._session_key("session-1", "user-1")
        assert service._sessions[key] is session
        mock_get_version.assert_called_once_with("v-default")

    def test_get_or_create_session_recreates_session_when_version_changes(self, mocker):
        settings = SimpleNamespace(openai_api_key=None, skai_copilot_version="v1")
        service = OrchestratorService(settings)
        service._llm_client = object()

        version_v1 = SimpleNamespace(
            config=SimpleNamespace(version="v1", orchestrator_version="v1")
        )
        version_v2 = SimpleNamespace(
            config=SimpleNamespace(version="v2", orchestrator_version="v1")
        )

        def fake_get_version(version_id: str):
            return version_v1 if version_id == "v1" else version_v2

        mocker.patch(
            "services.orchestrator_service.get_copilot_version",
            side_effect=fake_get_version,
        )

        created_sessions: list[object] = []

        class FakeSession:
            def __init__(
                self,
                session_id: str,
                chat_history: list[ChatEvent],
                llm_service: object,
                skai_service: object,
                version_config: object,
                *,
                filter_options=None,
            ):
                self.session_id = session_id
                self.chat_history = list(chat_history)
                self.llm_service = llm_service
                self.skai_service = skai_service
                self.version_config = version_config
                self.version_id = getattr(version_config, "version_id", None)
                self.waiting_for_info = False
                created_sessions.append(self)

        mocker.patch(
            "services.orchestrator_service.OrchestratorSession",
            FakeSession,
        )

        skai_service = mocker.Mock()
        chat_history_v1 = [ChatEvent(role="user", content="first")]
        chat_history_v2 = [ChatEvent(role="user", content="second")]

        request1 = OrchestratorChatRequest(messages=chat_history_v1)
        session1 = service._get_or_create_session(
            session_id="session-1",
            user_id="user-1",
            request=request1,
            skai_service=skai_service,
        )

        request2 = OrchestratorChatRequest(
            messages=chat_history_v2,
            skai_version="v2",
        )
        session2 = service._get_or_create_session(
            session_id="session-1",
            user_id="user-1",
            request=request2,
            skai_service=skai_service,
        )

        key = service._session_key("session-1", "user-1")
        assert session1 is not session2
        assert service._sessions[key] is session2
        assert session2.chat_history == chat_history_v2

    def test_get_or_create_session_appends_latest_user_message_when_waiting_for_info(
        self, mocker
    ):
        settings = SimpleNamespace(openai_api_key=None, skai_copilot_version="v1")
        service = OrchestratorService(settings)
        service._llm_client = object()

        mocker.patch(
            "services.orchestrator_service.get_copilot_version",
            return_value=SimpleNamespace(version_id="v1"),
        )

        existing_session = SimpleNamespace(
            version_id="v1",
            waiting_for_info=True,
            chat_history=[ChatEvent(role="user", content="original")],
        )

        key = service._session_key("session-1", "user-1")
        service._sessions[key] = existing_session

        chat_history = [
            ChatEvent(role="user", content="first"),
            ChatEvent(role="assistant", content="assistant"),
            ChatEvent(role="user", content="latest"),
        ]
        request = OrchestratorChatRequest(messages=chat_history)

        result_session = service._get_or_create_session(
            session_id="session-1",
            user_id="user-1",
            request=request,
            skai_service=mocker.Mock(),
        )

        assert result_session is existing_session
        assert len(existing_session.chat_history) == 2
        assert existing_session.chat_history[-1] == chat_history[-1]

    def test_get_or_create_session_refreshes_chat_history_when_session_is_complete(
        self, mocker
    ):
        settings = SimpleNamespace(openai_api_key=None, skai_copilot_version="v1")
        service = OrchestratorService(settings)
        service._llm_client = object()

        mocker.patch(
            "services.orchestrator_service.get_copilot_version",
            return_value=SimpleNamespace(version_id="v1"),
        )

        existing_session = SimpleNamespace(
            version_id="v1",
            waiting_for_info=False,
            chat_history=[ChatEvent(role="user", content="original")],
        )

        key = service._session_key("session-1", "user-1")
        service._sessions[key] = existing_session

        chat_history = [
            ChatEvent(role="user", content="first"),
        ]
        request = OrchestratorChatRequest(messages=chat_history)

        result_session = service._get_or_create_session(
            session_id="session-1",
            user_id="user-1",
            request=request,
            skai_service=mocker.Mock(),
        )

        assert result_session is existing_session
        assert result_session.chat_history == chat_history


class TestOrchestratorServiceSkaiServiceRequirement:
    @pytest.mark.asyncio
    async def test_invoke_text_uses_provided_skai_service(self, mocker):
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))
        service._llm_client = object()
        skai_service = mocker.Mock()

        mock_session = mocker.Mock()
        mock_session.stream_final_answer = False
        mock_session.is_complete = False
        mock_session.current_stage = OrchestratorStages.done

        async def execute_one(*args, **kwargs):
            yield OrchestratorEvent(
                event_type=OrchestratorEventType.content,
                stage=OrchestratorStages.done,
                content="Done",
            )

        mock_session.execute = execute_one
        get_session = mocker.patch.object(
            service, "_get_or_create_session", return_value=mock_session
        )

        request = OrchestratorChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            skai_version="v9-dev",
        )
        result = await service._invoke_text(
            request=request,
            session_id="session-1",
            assistant_message_id=uuid4(),
            user_id="user-1",
            skai_service=skai_service,
        )

        assert "Done" in result
        get_session.assert_called_once_with(
            "session-1",
            "user-1",
            request,
            skai_service,
        )

    @pytest.mark.asyncio
    async def test_invoke_requires_skai_service_argument(self):
        service = OrchestratorService(SimpleNamespace(openai_api_key=None))

        with pytest.raises(TypeError, match="skai_service"):
            async for _ in service.invoke(
                OrchestratorChatRequest(messages=[{"role": "user", "content": "hi"}]),
                session_id="s1",
                assistant_message_id=uuid4(),
                user_id="user-1",
                stream=False,
            ):
                pass
