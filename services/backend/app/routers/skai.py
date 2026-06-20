"""SKAI data endpoints (filter values, etc.)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from config.versioning import get_copilot_version
from core.dependencies import (
    AuthTokenDep,
    DatabaseDep,
    SkaiAuthServiceDep,
    get_skai_api_for_user,
    get_skai_api_v2_for_user,
)
from core.config import Settings, get_settings
from models.skai_api.autogen import FilterValuesResponse as FilterValuesResponseV1
from models.skai_api_v2.filters import FilterValuesResponse as FilterValuesResponseV2
from services.skai_api import SKAIApiError, get_filter_options
from services.skai_api_v2.exceptions import SkaiApiV2Error

router = APIRouter(tags=["SKAI"])


def _requires_skai_v2(version_id: str) -> bool:
    version_config = get_copilot_version(version_id)
    return (
        version_config.config.orchestrator_version == "single_agent_promo_orchestrator"
    )


@router.get(
    "/skai/filter-values",
    summary="Get available filter values from SKAI",
    response_model=dict[str, list[str]],
)
async def get_filter_values(
    auth: AuthTokenDep,
    db: DatabaseDep,
    skai_auth_service: SkaiAuthServiceDep,
    settings: Settings = Depends(get_settings),
    skai_version: str | None = Query(default=None),
) -> dict[str, list[str]]:
    """Return filter options (key -> list of values) from SKAI for the current user.

    Requires the user to be connected to SKAI (Cognito). Returns 401 with
    X-Error-Code: SKAI_AUTH_REQUIRED if not connected. Returns 502 if the
    SKAI API request fails.
    """
    version_id = skai_version or settings.skai_copilot_version
    resp: FilterValuesResponseV1 | FilterValuesResponseV2
    try:
        if _requires_skai_v2(version_id):
            skai_v2 = await get_skai_api_v2_for_user(auth, db, skai_auth_service)
            resp = await skai_v2.filters.get_values()
        else:
            skai_v1 = await get_skai_api_for_user(auth, db, skai_auth_service)
            resp = await get_filter_options(skai_v1)
    except (SKAIApiError, SkaiApiV2Error) as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        ) from e

    filters = resp.filters

    selectable_scope_dimensions = [
        "categories",
        "subcategories",
        "retailers",
        "channels",
        "brands",
        "price_tiers",
    ]

    response = {}
    for dimension in selectable_scope_dimensions:
        if values := getattr(filters, dimension, None):
            response[dimension] = values
    return response
