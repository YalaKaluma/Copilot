from typing import Any

from copilot_agents.core import Agent
from models.copilot.base import Tool, ToolInput, ToolParameter, ToolProperty
from models.skai_api_v2.filters import FilterOptions, RelatedFiltersRequest
from services.skai_api_v2.client import SkaiApiV2Client
from tools.skai.common import array_property, parse_list_param
from tools.skai_v2.common import (
    normalize_filter_context,
    require_v2_skai_service,
)

SUPPORTED_FILTER_FIELDS = (
    "brands",
    "categories",
    "subcategories",
    "retailers",
    "channels",
    "price_tiers",
    "pack_size_range_values",
    "sku_ids",
)


def _get_filter_tool_properties(
    filter_context: FilterOptions | None,
) -> dict[str, ToolProperty]:
    filter_context = normalize_filter_context(filter_context)
    return {
        "brands": array_property(
            "Filter by brand names (comma-separated). Omit for all brands.",
            enum_vals=filter_context.brands,
            nullable=True,
        ),
        "categories": array_property(
            "Filter by category names (comma-separated). Omit for all categories.",
            enum_vals=filter_context.categories,
            nullable=True,
        ),
        "subcategories": array_property(
            "Filter by subcategory names (comma-separated). Omit for all subcategories.",
            enum_vals=filter_context.subcategories,
            nullable=True,
        ),
        "retailers": array_property(
            "Filter by retailer names (comma-separated). Omit for all retailers.",
            enum_vals=filter_context.retailers,
            nullable=True,
        ),
        "channels": array_property(
            "Filter by channel names (comma-separated). Omit for all channels.",
            enum_vals=filter_context.channels,
            nullable=True,
        ),
        "price_tiers": array_property(
            "Filter by price tiers (comma-separated). Omit for all price tiers.",
            enum_vals=filter_context.price_tiers,
            nullable=True,
        ),
        "pack_size_range_values": array_property(
            "Filter by pack size range values (comma-separated). Omit for all pack sizes.",
            enum_vals=filter_context.pack_size_range_values,
            nullable=True,
        ),
        "sku_ids": array_property(
            "Filter by SKU IDs (comma-separated). Omit for all SKUs.",
            enum_vals=filter_context.sku_ids,
            nullable=True,
        ),
    }


def _build_related_filters_payload(args: dict[str, Any]) -> dict[str, Any]:
    return {
        "brands": parse_list_param(args.get("brands")),
        "categories": parse_list_param(args.get("categories")),
        "subcategories": parse_list_param(args.get("subcategories")),
        "retailers": parse_list_param(args.get("retailers")),
        "channels": parse_list_param(args.get("channels")),
        "price_tiers": parse_list_param(args.get("price_tiers")),
        "pack_size_range_values": parse_list_param(args.get("pack_size_range_values")),
        "sku_ids": parse_list_param(args.get("sku_ids")),
    }


async def _get_filter_values_all(client: SkaiApiV2Client) -> dict[str, Any]:
    response = await client.filters.get_values()
    return response.model_dump(mode="json", exclude_none=True)


async def _get_filter_values_related(
    client: SkaiApiV2Client,
    payload: dict[str, Any],
) -> dict[str, Any]:
    request = RelatedFiltersRequest(
        **{key: value for key, value in payload.items() if value is not None}
    )
    response = await client.filters.get_related(request)
    return response.model_dump(mode="json", exclude_none=True)


async def _exec_get_filter_values(
    agent: Agent,
    args: dict[str, Any],
) -> dict[str, Any]:
    api_client = require_v2_skai_service(agent)
    payload = _build_related_filters_payload(args)
    if any(value is not None for value in payload.values()):
        return await _get_filter_values_related(api_client, payload)
    return await _get_filter_values_all(api_client)


def create_get_filter_values_tool(
    filter_context: FilterOptions | None = None,
) -> Tool:
    filter_context = normalize_filter_context(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_filter_values",
            description=(
                "Get available SKAI v2 filter values. "
                "When filters are supplied, returns related filter values narrowed to that perimeter. "
                "When no filters are supplied, returns the full filter list plus metadata."
            ),
            parameters=ToolParameter(
                properties=_get_filter_tool_properties(filter_context),
                required=[],
            ),
        ),
        executor=_exec_get_filter_values,
    )
