"""Integration tests for SKAI list filters."""

import json
import pytest
from collections.abc import Coroutine
from typing import Any, Callable

from core.config import get_settings
from services.skai_api import SKAIApi
from services.skai_auth_service import SkaiAuthService
from tools.skai.tools import (
    _exec_get_category_landscape,
    _exec_get_category_trends,
    _exec_get_channel_assortment,
    _exec_get_channel_fair_share,
    _exec_get_channel_intensity,
    _exec_get_channel_landscape,
    _exec_get_channel_transparency_brand,
    _exec_get_channel_transparency_retailer,
    _exec_get_promo_calendar,
    _exec_get_promo_event_scatter,
    _exec_get_promo_heatmap,
    _exec_get_promo_investment_trends,
    _exec_get_promo_market_effectiveness,
    _exec_get_price_outliers,
    _exec_get_price_spread,
    _exec_get_pricing_evolution,
)

_settings = get_settings()
_missing_config: list[str] = []
if not _settings.skai_user_name:
    _missing_config.append("SKAI_USER_NAME")
if not _settings.skai_password:
    _missing_config.append("SKAI_PASSWORD")
if not _settings.skai_cognito_region:
    _missing_config.append("SKAI_COGNITO_REGION")
if not _settings.skai_cognito_user_pool_id:
    _missing_config.append("SKAI_COGNITO_USER_POOL_ID")
if not _settings.skai_cognito_client_id:
    _missing_config.append("SKAI_COGNITO_CLIENT_ID")

pytestmark = pytest.mark.skipif(
    bool(_missing_config),
    reason=(
        "SKAI integration not configured: " + ", ".join(_missing_config)
        if _missing_config
        else ""
    ),
)


async def _create_skai_api() -> SKAIApi:
    settings = get_settings()
    if not settings.skai_user_name or not settings.skai_password:
        raise RuntimeError("SKAI credentials are not configured")
    auth_service = SkaiAuthService(settings)
    token = await auth_service.get_token_for_credentials(
        settings.skai_user_name, settings.skai_password
    )
    extra_headers: dict[str, str] = {}
    if settings.skai_api_origin:
        extra_headers["Origin"] = settings.skai_api_origin
    if settings.skai_api_referer:
        extra_headers["Referer"] = settings.skai_api_referer
    if settings.skai_api_user_agent:
        extra_headers["User-Agent"] = settings.skai_api_user_agent
    return SKAIApi(
        base_url=settings.skai_api_url,
        api_key=settings.skai_api_key,
        auth_token=token,
        extra_headers=extra_headers,
    )


def _extract_items(response: dict) -> list[dict]:
    data = response.get("data", [])
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    charts = response.get("charts")
    if not charts:
        return []
    if isinstance(charts, str):
        try:
            charts = json.loads(charts)
        except json.JSONDecodeError:
            return []
    if not isinstance(charts, list):
        return []
    items: list[dict] = []
    for chart in charts:
        if not isinstance(chart, dict):
            continue
        chart_data = chart.get("data", [])
        if not isinstance(chart_data, list):
            continue
        items.extend(item for item in chart_data if isinstance(item, dict))
    return items


def _collect_values(items: list[dict], keys: list[str]) -> list[str]:
    values: list[str] = []
    seen = set()
    for item in items:
        for key in keys:
            value = item.get(key)
            if not isinstance(value, str):
                continue
            if not value or value in seen:
                continue
            seen.add(value)
            values.append(value)
    return values


def _pick_filter_values_from_baseline(
    items: list[dict],
    filter_values: dict[str, list[str]],
    value_keys: list[str],
    filter_candidates: list[str],
) -> tuple[str, list[str]] | None:
    baseline_values = _collect_values(items, value_keys)
    if not baseline_values:
        return None
    for filter_name in filter_candidates:
        allowlist = filter_values.get(filter_name, [])
        if allowlist:
            allowed = set(allowlist)
            selected = [value for value in baseline_values if value in allowed]
        else:
            selected = list(baseline_values)
        if len(selected) >= 2:
            return filter_name, selected[:2]
    return None


def _extract_event_ids(response: dict) -> set[int]:
    event_ids: set[int] = set()
    for item in _extract_items(response):
        if not isinstance(item, dict):
            continue
        event_id = item.get("event_id")
        if event_id is None:
            event_id = item.get("eventId")
        if isinstance(event_id, int):
            event_ids.add(event_id)
    return event_ids


def _extract_item_keys(response: dict, key_fields: list[str] | None = None) -> set[str]:
    items = _extract_items(response)
    if not items:
        return set()
    keys: set[str] = set()
    if key_fields:
        for item in items:
            keys.add(
                "|".join(f"{key}={item.get(key)}" for key in key_fields if key in item)
            )
        return keys
    event_ids = _extract_event_ids(response)
    if event_ids:
        return {str(event_id) for event_id in event_ids}
    for item in items:
        keys.add(
            "|".join(f"{key}={item[key]}" for key in sorted(item.keys()) if key in item)
        )
    return keys


def _agent_with_skai(skai_service: SKAIApi) -> Any:
    """Minimal adapter so _exec_* (agent, args) can be called with SKAIApi in tests."""

    class _Adapter:
        code_execution_container_id: str | None = None

        def __init__(self, api: SKAIApi) -> None:
            self.skai_service = api
            self.code_interpreter_mode = "local"

    return _Adapter(skai_service)


PROMO_LIST_FILTER_CASES: list[
    tuple[
        str,
        Callable[[Any, dict[str, Any]], Coroutine[Any, Any, Any]],
        list[str],
        list[str],
        list[str] | None,
    ]
] = [
    (
        "category_landscape",
        _exec_get_category_landscape,
        ["brand", "subcategory"],
        ["brands", "subcategories"],
        None,
    ),
    (
        "category_trends",
        _exec_get_category_trends,
        ["brand"],
        ["brands"],
        None,
    ),
    (
        "channel_landscape",
        _exec_get_channel_landscape,
        ["brand", "subcategory"],
        ["brands", "subcategories", "retailers"],
        None,
    ),
    (
        "channel_assortment",
        _exec_get_channel_assortment,
        ["sku_id", "brand", "retailer"],
        ["sku_ids", "brands", "retailers"],
        None,
    ),
    (
        "channel_fair_share",
        _exec_get_channel_fair_share,
        ["brand"],
        ["brands"],
        None,
    ),
    (
        "channel_intensity",
        _exec_get_channel_intensity,
        ["group_value"],
        ["brands"],
        None,
    ),
    (
        "channel_transparency_brand",
        _exec_get_channel_transparency_brand,
        ["group_value"],
        ["brands"],
        None,
    ),
    (
        "channel_transparency_retailer",
        _exec_get_channel_transparency_retailer,
        ["group_value"],
        ["retailers"],
        None,
    ),
    (
        "promo_calendar",
        _exec_get_promo_calendar,
        ["retailer", "brand", "sku_id"],
        ["retailers", "brands", "sku_ids"],
        None,
    ),
    (
        "promo_event_scatter",
        _exec_get_promo_event_scatter,
        ["brand"],
        ["brands"],
        None,
    ),
    (
        "promo_investment_trends",
        _exec_get_promo_investment_trends,
        ["group_value"],
        ["retailers", "brands"],
        ["group_value", "period"],
    ),
    (
        "promo_market_effectiveness",
        _exec_get_promo_market_effectiveness,
        ["group_value"],
        ["retailers", "brands"],
        None,
    ),
    (
        "promo_heatmap",
        _exec_get_promo_heatmap,
        ["x_value", "y_value"],
        ["retailers", "sku_ids"],
        None,
    ),
    (
        "price_spread",
        _exec_get_price_spread,
        ["product_id"],
        ["product_ids"],
        None,
    ),
    (
        "pricing_evolution",
        _exec_get_pricing_evolution,
        ["customer_id"],
        ["customer_ids"],
        None,
    ),
    (
        "price_outliers",
        _exec_get_price_outliers,
        ["customer_id", "product_id"],
        ["customer_ids", "product_ids"],
        None,
    ),
]


# TODO: Extend integration coverage to remaining SKAI tools that use _parse_list_param.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_name,executor,value_keys,filter_candidates,subset_key_fields",
    PROMO_LIST_FILTER_CASES,
)
async def test_promo_list_filters_subset_baseline(
    case_name: str,
    executor: Callable[[Any, dict[str, Any]], Coroutine[Any, Any, Any]],
    value_keys: list[str],
    filter_candidates: list[str],
    subset_key_fields: list[str] | None,
):
    api = await _create_skai_api()
    agent = _agent_with_skai(api)
    async with api:
        filter_response = await api.get_filter_values()
        data_range = filter_response.metadata.data_range
        if not data_range.min_date or not data_range.max_date:
            pytest.skip("SKAI filter metadata missing data range")
        start_date = data_range.min_date.isoformat()
        end_date = data_range.max_date.isoformat()
        baseline_args = {
            "start_date": start_date,
            "end_date": end_date,
        }

        baseline = await executor(agent, baseline_args)
        baseline_keys = _extract_item_keys(baseline, subset_key_fields)
        if not baseline_keys:
            pytest.skip(f"Baseline {case_name} returned no items")

        filter_values = {
            "retailers": filter_response.filters.retailers or [],
            "brands": filter_response.filters.brands or [],
            "sku_ids": filter_response.filters.sku_ids or [],
            "categories": filter_response.filters.categories or [],
            "subcategories": filter_response.filters.subcategories or [],
            "channels": filter_response.filters.channels or [],
        }
        selection = _pick_filter_values_from_baseline(
            _extract_items(baseline),
            filter_values,
            value_keys,
            filter_candidates,
        )
        if selection is None:
            pytest.skip(f"No matching filter values found for {case_name}")
        filter_name, filter_values_selected = selection
        filtered_args = {
            "start_date": start_date,
            "end_date": end_date,
            filter_name: filter_values_selected,
        }
        filtered = await executor(agent, filtered_args)

        filtered_keys = _extract_item_keys(filtered, subset_key_fields)
        assert filtered_keys
        assert filtered_keys.issubset(baseline_keys)
