from typing import Any

import pandas as pd

from copilot_agents.core import Agent
from core.config import get_settings
from models.copilot.base import Tool, ToolInput, ToolParameter, ToolProperty
from models.skai_api_v2.filters import FilterOptions
from models.skai_api_v2.promo import PromoHeatmapDim, PromoHeatmapRequest
from tools.skai.common import (
    array_property,
    date_property,
    parse_list_param,
    string_property,
    write_local_code_execution_dataset,
)
from tools.skai_v2.common import (
    normalize_filter_context,
    parse_optional_string,
    require_v2_skai_service,
)


def _get_heatmap_tool_properties(
    filter_context: FilterOptions | None,
    axis_enums: list[str],
) -> dict[str, ToolProperty]:
    filter_context = normalize_filter_context(filter_context)
    return {
        "x_axis": string_property(
            "X-axis dimension for the heatmap.",
            enum_vals=axis_enums,
        ),
        "y_axis": string_property(
            "Y-axis dimension for the heatmap.",
            enum_vals=axis_enums,
        ),
        "market": string_property(
            "Market scope such as FR, BE, or UK only if known.",
            nullable=True,
        ),
        "period_start": string_property(
            "Period lower bound in YYYY-MM format.",
            nullable=True,
        ),
        "period_end": string_property(
            "Period upper bound in YYYY-MM format.",
            nullable=True,
        ),
        "start_date": date_property("Analysis period start date", nullable=True),
        "end_date": date_property("Analysis period end date", nullable=True),
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
        "duration_bin": array_property(
            "Filter by promo duration bins such as 1w, 2w, or unknown (comma-separated).",
            nullable=True,
        ),
        "depth_bin": array_property(
            "Filter by discount depth bins such as 0-10%, 10-20%, or unknown (comma-separated).",
            nullable=True,
        ),
        "tslp_bin": array_property(
            "Filter by time-since-last-promo bins (comma-separated).",
            nullable=True,
        ),
        "depth_deciles": array_property(
            "Filter by discount depth deciles (comma-separated).",
            nullable=True,
        ),
        "promo_tactics": array_property(
            "Filter by promo tactics (comma-separated).",
            nullable=True,
        ),
    }


def _build_heatmap_request(args: dict[str, Any]) -> PromoHeatmapRequest:
    return PromoHeatmapRequest(
        x_dim_kind=PromoHeatmapDim(args.get("x_axis", PromoHeatmapDim.retailer.value)),
        y_dim_kind=PromoHeatmapDim(args.get("y_axis", PromoHeatmapDim.sku.value)),
        market=parse_optional_string(args.get("market")) or "UK",
        period_start=parse_optional_string(args.get("period_start")),
        period_end=parse_optional_string(args.get("period_end")),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=parse_list_param(args.get("brands")),
        retailers=parse_list_param(args.get("retailers")),
        categories=parse_list_param(args.get("categories")),
        subcategories=parse_list_param(args.get("subcategories")),
        channels=parse_list_param(args.get("channels")),
        price_tiers=parse_list_param(args.get("price_tiers")),
        pack_size_range_values=parse_list_param(args.get("pack_size_range_values")),
        sku_ids=parse_list_param(args.get("sku_ids")),
        duration_bin=parse_list_param(args.get("duration_bin")),
        depth_bin=parse_list_param(args.get("depth_bin")),
        tslp_bin=parse_list_param(args.get("tslp_bin")),
        depth_deciles=parse_list_param(args.get("depth_deciles")),
        promo_tactics=parse_list_param(args.get("promo_tactics")),
    )


def _build_large_payload_response(
    api_response, dataset: list[dict[str, Any]]
) -> dict[str, Any]:
    summary = api_response.summary.model_dump(
        mode="json",
        exclude_none=True,
        warnings=False,
    )
    df = pd.DataFrame(dataset)
    available_x_values = (
        df["x_value"].dropna().astype(str).unique().tolist()
        if "x_value" in df.columns
        else []
    )
    available_y_values = (
        df["y_value"].dropna().astype(str).unique().tolist()
        if "y_value" in df.columns
        else []
    )
    response: dict[str, Any] = {
        "summary": summary,
        "columns_in_raw_data": df.columns.tolist(),
        "available_x_values": available_x_values,
        "available_y_values": available_y_values,
    }
    if api_response.envelope is not None:
        response["envelope"] = api_response.envelope.model_dump(
            mode="json",
            exclude_none=True,
            warnings=False,
        )
    return response


async def _exec_get_promo_heatmap(
    agent: Agent,
    args: dict[str, Any],
) -> dict[str, Any]:
    api_client = require_v2_skai_service(agent)
    request = _build_heatmap_request(args)
    api_response = await api_client.promo.get_heatmap(request)

    rows = api_response.data or []
    if len(rows) <= get_settings().skai_max_data_items:
        return api_response.model_dump(
            mode="json",
            exclude_none=True,
            warnings=False,
        )

    dataset = [row.model_dump(mode="json", exclude_none=True) for row in rows]
    df = pd.DataFrame(dataset)
    response = _build_large_payload_response(api_response, dataset)
    file_path = write_local_code_execution_dataset(
        agent.session_id,
        "promo_heatmap_v2.csv",
        df,
    )
    response["additional_info"] = (
        "Large payload detected. Use local code interpreter tooling to analyse "
        f"data saved in file {file_path} in CSV format"
    )
    return response


def create_get_promo_heatmap_tool(
    filter_context: FilterOptions | None = None,
) -> Tool:
    filter_context = normalize_filter_context(filter_context)
    axis_enums = [axis.value for axis in PromoHeatmapDim]
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_heatmap",
            description=(
                "Get the SKAI v2 promo heatmap. "
                "Returns a two-dimensional view of promo investment, incremental GP, sales, ROI, and uplift "
                "across the selected X and Y axes. Large responses are exported for code execution analysis."
            ),
            parameters=ToolParameter(
                properties=_get_heatmap_tool_properties(filter_context, axis_enums),
                required=[],
            ),
        ),
        executor=_exec_get_promo_heatmap,
    )
