from typing import Any

from copilot_agents.core import Agent
from models.skai_api_v2.filters import FilterOptions
from services.skai_api_v2.client import SkaiApiV2Client


def parse_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def normalize_filter_context(filter_context: FilterOptions | None) -> FilterOptions:
    return filter_context or FilterOptions()


def require_v2_skai_service(agent: Agent) -> SkaiApiV2Client:
    skai_service = agent.skai_service
    if not isinstance(skai_service, SkaiApiV2Client):
        raise TypeError(
            "skai_v2 tools require agent.skai_service to be SkaiApiV2Client. "
            f"Received {type(skai_service).__name__}."
        )
    return skai_service
