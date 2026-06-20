from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest

from routers.orchestrator import orchestrator_chat
from schemas.orchestrator import OrchestratorChatRequest


async def _invoke_once(*args, **kwargs):
    yield "Final answer"


@pytest.mark.asyncio
async def test_orchestrator_chat_uses_v2_client_for_v9_dev(mocker):
    v2_client = object()
    service = SimpleNamespace(is_configured=True, invoke=_invoke_once)
    auth = {"user": SimpleNamespace(id="user-1")}
    skai_auth_service = SimpleNamespace(
        get_credentials=AsyncMock(
            return_value=SimpleNamespace(skai_username="u@example.com")
        )
    )

    mocker.patch("routers.orchestrator._requires_skai_v2", return_value=True)
    get_v2 = mocker.patch(
        "routers.orchestrator.get_skai_api_v2_for_user",
        new=AsyncMock(return_value=v2_client),
    )
    get_v1 = mocker.patch("routers.orchestrator.get_skai_api_for_user", new=AsyncMock())

    response = await orchestrator_chat(
        request=OrchestratorChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
            skai_version="v9-dev",
        ),
        service=service,
        auth=auth,
        db=object(),
        skai_auth_service=skai_auth_service,
        settings=SimpleNamespace(skai_copilot_version="v8"),
    )

    get_v2.assert_awaited_once()
    get_v1.assert_not_awaited()
    assert response.content == "Final answer"


@pytest.mark.asyncio
async def test_orchestrator_chat_uses_v1_client_for_existing_versions(mocker):
    v1_client = object()
    service = SimpleNamespace(is_configured=True, invoke=_invoke_once)
    auth = {"user": SimpleNamespace(id="user-1")}
    skai_auth_service = SimpleNamespace(
        get_credentials=AsyncMock(
            return_value=SimpleNamespace(skai_username="u@example.com")
        )
    )

    mocker.patch("routers.orchestrator._requires_skai_v2", return_value=False)
    get_v1 = mocker.patch(
        "routers.orchestrator.get_skai_api_for_user",
        new=AsyncMock(return_value=v1_client),
    )
    get_v2 = mocker.patch(
        "routers.orchestrator.get_skai_api_v2_for_user", new=AsyncMock()
    )

    response = await orchestrator_chat(
        request=OrchestratorChatRequest(
            messages=[{"role": "user", "content": "hi"}],
            stream=False,
        ),
        service=service,
        auth=auth,
        db=object(),
        skai_auth_service=skai_auth_service,
        settings=SimpleNamespace(skai_copilot_version="v8"),
    )

    get_v1.assert_awaited_once()
    get_v2.assert_not_awaited()
    assert response.content == "Final answer"
