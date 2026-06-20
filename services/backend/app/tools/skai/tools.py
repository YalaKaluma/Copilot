"""SKAI tool definitions with linked executors for LLM function calling.

This module provides Tool objects that combine ToolInput definitions with
their actual executor functions, enabling LLMs to interact with the SKAI
analytics platform.

Usage:
    from tools.skai import get_category_tools

    # Get category tools with their executors
    tools = get_category_tools()

    # Each tool has both the schema and the callable
    for tool in tools:
        print(tool.definition.name)  # Tool schema for LLM
        result = await tool.execute(skai_api, {"brands": "Brand A"})  # Execute
"""

import json
import pandas as pd
from typing import Any, Callable, Protocol, TypeVar, TypedDict, cast


from models.copilot.base import (
    ToolInput,
    ToolParameter,
    ToolProperty,
    Tool,
)
from models.skai_api.autogen import (
    CDTParams,
    CDTRequest,
    CategoryFormatRequest,
    CategoryInnovationRequest,
    CategoryLandscapeRequest,
    CategoryPackSizeRequest,
    CategoryPriceTiersRequest,
    CategoryProductRequest,
    CategorySeasonalityRequest,
    CategoryTrendsRequest,
    ChannelLandscapeRequest,
    DownloadRequest,
    DriverType,
    ElasticityRequest,
    FilterOptions,
    GTNWaterfallRequest,
    InvestmentDriverRequest,
    MarginContributionRequest,
    NPIProduct,
    PortfolioQuadrantRequest,
    PriceChange,
    PriceOutlierRequest,
    PriceSpreadRequest,
    PricingEvolutionRequest,
    ProfitPoolRequest,
    RelatedFiltersRequest,
    ScatterLegend,
    ScenarioCreate,
    Severity,
    SimulationConfig,
    SimulatorRunRequest,
    TacticXAxis,
)
from models.skai_api.patched import (
    AssortmentRequest,
    BaselineReviewRequest,
    BrandLadderRequest,
    ChannelFairShareRequest,
    ChannelIntensityRequest,
    ChannelTransparencyRequest,
    DeepDiveTacticRequest,
    DiscountDepthQCRequest,
    EventScatterRequest,
    HeatmapRequest,
    MarketEffectivenessRequest,
    PricePackCurveRequest,
    ProductDeepDiveRequest,
    PromoPlannerRequest,
    PromoRequest,
    ScenarioListRequest,
    SimulatorBaseRequest,
    TacticEffectivenessRequest,
)
from copilot_agents.inference.execution_agent import ExecutionAgent
from core.config import get_settings
from services.skai_api import SKAIApi, get_filter_options
from tools.agent.core import generate_hand_back
from tools.skai.common import (
    array_property as _array_property,
    boolean_property as _boolean_property,
    date_property as _date_property,
    integer_property as _integer_property,
    number_property as _number_property,
    parse_list_param as _parse_list_param,
    string_property as _string_property,
    write_local_code_execution_dataset as _write_local_code_execution_dataset,
)

# =============================================================================
# Helper Functions
# =============================================================================


_T = TypeVar("_T", bound=str)


def _parse_list_param_with_allowed_values(
    value: Any, allowed_values: list[_T]
) -> list[_T] | None:
    """Parse a list parameter from string or list with allowed values."""
    list_values = _parse_list_param(value)
    if list_values is None:
        return None
    new_vals = cast(list[_T], list(set(list_values).intersection(allowed_values)))
    return new_vals


def _parse_json_param(value: Any) -> Any:
    """Parse a JSON parameter from string."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _get_common_filter_properties(
    filter_context: FilterOptions,
) -> dict[str, ToolProperty]:
    return {
        "start_date": _date_property("Analysis period start date", nullable=True),
        "end_date": _date_property("Analysis period end date", nullable=True),
        "brands": _array_property(
            "Filter by brand names (comma-separated). Omit or leave blank for all brands.",
            enum_vals=filter_context.brands,
            nullable=True,
        ),
        "categories": _array_property(
            "Filter by category names (comma-separated). Omit or leave blank for all categories.",
            enum_vals=filter_context.categories,
            nullable=True,
        ),
        "subcategories": _array_property(
            "Filter by subcategory names (comma-separated). Omit or leave blank for all subcategories.",
            enum_vals=filter_context.subcategories,
            nullable=True,
        ),
        "retailers": _array_property(
            "Filter by retailer names (comma-separated). Omit or leave blank for all retailers.",
            enum_vals=filter_context.retailers,
            nullable=True,
        ),
        "channels": _array_property(
            "Filter by channel names (comma-separated). Omit or leave blank for all channels.",
            enum_vals=filter_context.channels,
            nullable=True,
        ),
    }


def _get_promo_filter_properties(
    filter_context: FilterOptions,
    include_promo_tactics: bool = True,
) -> dict[str, ToolProperty]:
    """Common filter properties plus depth_deciles and promo_tactics for promo tools."""
    properties = {
        **_get_common_filter_properties(filter_context),
        "depth_deciles": _array_property(
            "Filter by depth deciles (e.g. 10-20%)", nullable=True
        ),
    }
    if include_promo_tactics:
        properties["promo_tactics"] = _array_property(
            "Filter by promo tactics", nullable=True
        )
    return properties


async def _clean_filter_args(args: dict, skai: SKAIApi) -> dict:

    filter_vals = await get_filter_options(skai)

    filter_opts = filter_vals.filters.model_dump(mode="json")

    cleaned_args = args.copy()

    for key, value in args.items():
        if not isinstance(value, list):
            continue
        if key not in filter_opts:
            continue

        # providing all values for a filter is not allowed
        if len(value) == len(filter_opts[key]):
            del cleaned_args[key]
        elif len(value) == 0:
            del cleaned_args[key]
    return cleaned_args


# =============================================================================
# Health & Auth Tools
# =============================================================================


# async def _exec_health_check(agent: ExecutionAgent, args: dict) -> Any:
#     return await api.health()


# def create_health_check_tool() -> Tool:
#     """Create tool for checking API health status."""
#     return Tool(
#         definition=ToolInput(
#             name="skai_health_check",
#             description="Check the health status of the SKAI API service",
#         ),
#         executor=_exec_health_check,
#     )


# async def _exec_get_me(agent: ExecutionAgent, args: dict) -> Any:
#     return await api.get_me()


# def create_get_me_tool() -> Tool:
#     """Create tool for getting current user information."""
#     return Tool(
#         definition=ToolInput(
#             name="skai_get_me",
#             description="Get information about the currently authenticated user including their groups and VTM mode",
#         ),
#         executor=_exec_get_me,
#     )


# =============================================================================
# Config Tools
# =============================================================================


# async def _exec_get_config(agent: ExecutionAgent, args: dict) -> Any:
#     return await api.get_config(args["category"])


# def create_get_config_tool() -> Tool:
#     """Create tool for getting configuration."""
#     return Tool(
#         definition=ToolInput(
#             name="skai_get_config",
#             description="Get configuration settings for a specific category",
#             parameters=ToolParameter(
#                 properties={
#                     "category": _string_property(
#                         "Configuration category: 'baseline', 'deciles', 'promo_planner', or 'suppression'"
#                     ),
#                 },
#                 required=["category"],
#             ),
#         ),
#         executor=_exec_get_config,
#     )


# async def _exec_patch_config(agent: ExecutionAgent, args: dict) -> Any:
#     config = _parse_json_param(args.get("config", {}))
#     request = ConfigPatchRequest(config=config)
#     return await api.patch_config(args["category"], request)


# def create_patch_config_tool() -> Tool:
#     """Create tool for updating configuration."""
#     return Tool(
#         definition=ToolInput(
#             name="skai_patch_config",
#             description="Update configuration settings for a specific category",
#             parameters=ToolParameter(
#                 properties={
#                     "category": _string_property(
#                         "Configuration category: 'baseline', 'deciles', 'promo_planner', or 'suppression'"
#                     ),
#                     "config": _string_property(
#                         "JSON object containing configuration values to update"
#                     ),
#                 },
#                 required=["category", "config"],
#             ),
#         ),
#         executor=_exec_patch_config,
#     )


# =============================================================================
# Admin Tools
# =============================================================================


# async def _exec_seed_config(agent: ExecutionAgent, args: dict) -> Any:
#     return await api.seed_config()


# def create_seed_config_tool() -> Tool:
#     """Create tool for seeding configuration."""
#     return Tool(
#         definition=ToolInput(
#             name="skai_seed_config",
#             description="Seed configuration data (admin only)",
#         ),
#         executor=_exec_seed_config,
#     )


# =============================================================================
# Filter Tools
# =============================================================================


class ToolCreationFunction(Protocol):
    def __call__(self, filter_context: FilterOptions) -> Tool:
        pass


async def _exec_get_filter_values(agent: ExecutionAgent, args: dict) -> dict[str, Any]:
    api = agent.skai_service
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = RelatedFiltersRequest(
        retailers=args.get("retailers"),
        categories=args.get("categories"),
        subcategories=args.get("subcategories"),
        channels=args.get("channels"),
        brands=args.get("brands"),
    )
    api_resp = await api.get_filter_values_related(request)
    filter_context = api_resp.filters

    return filter_context.model_dump(mode="json", exclude_none=True)


def create_get_filter_values_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for getting available filter values."""
    return Tool(
        definition=ToolInput(
            name="skai_get_filter_values",
            description="Get all available filter values for analytics dashboards including brands, categories, retailers, channels, SKU IDs, price tiers, and pack sizes",
            parameters=ToolParameter(
                properties=_get_common_filter_properties(filter_context),
                required=[],
            ),
        ),
        executor=_exec_get_filter_values,
    )


# =============================================================================
# Category Tools
# =============================================================================


class ChartsWithSummary(TypedDict):
    charts: list[dict[str, Any]]
    summary: dict[str, Any]


async def _exec_get_category_landscape(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategoryLandscapeRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        sku_ids=_parse_list_param(args.get("sku_ids")),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
        price_metric=args.get("price_metric", "price_per_unit"),
    )
    api_resp = await api.get_category_landscape(request)

    charts = []

    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    result = {}
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"

    result["summary"] = json.dumps(api_resp.summary, indent=2)

    return result


def create_get_category_landscape_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category landscape analytics."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_landscape",
            description=(
                "Get Category Landscape. "
                "Returns: total sales & volume, share by brand/retailer/subcategory, growth vs prior period, average price, contribution to growth. "
                "Usage: (1) Call broad (category + date range) to establish baseline; (2) Narrow by brand or retailer to isolate share shifts; (3) Switch price_metric to test premiumization vs mix-shift. "
                "Example questions: Who is gaining share? Where is growth coming from? Is the category premiumizing? Which retailer is outperforming?"
            ),
            parameters=ToolParameter(
                properties={
                    **_get_common_filter_properties(filter_context),
                    "sku_ids": _array_property(
                        "Filter by specific SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                    "price_metric": _string_property(
                        "Price calculation method: 'price_per_unit' or 'price_per_scaled_volume'",
                        enum_vals=["price_per_unit", "price_per_scaled_volume"],
                    ),
                    "split_by": _string_property(
                        "Primary grouping dimension: 'brand', 'subcategory', 'category', 'sku', 'manufacturer', 'retailer', 'channel', or 'pack_size' (default: brand)",
                        enum_vals=[
                            "brand",
                            "subcategory",
                            "category",
                            "sku",
                            "manufacturer",
                            "retailer",
                            "channel",
                            "pack_size",
                        ],
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_category_landscape,
    )


async def _exec_get_category_trends(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategoryTrendsRequest(
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
        price_metric=args.get("price_metric", "price_per_unit"),
    )
    api_resp = await api.get_category_trends(request)

    charts = []

    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    result = {}
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"
    full_resp_dict = api_resp.model_dump(mode="json", exclude_none=True)
    result["summary"] = json.dumps(full_resp_dict["summary"], indent=2)
    return result


def create_get_category_trends_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category trends analytics."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_category_trends",
            description="Get Category Trends analytics showing historical performance, growth rates, and trend analysis over time",
            parameters=ToolParameter(
                properties={
                    "brands": common["brands"],
                    "categories": common["categories"],
                    "subcategories": common["subcategories"],
                    "retailers": common["retailers"],
                    "channels": common["channels"],
                    "price_metric": _string_property(
                        "Price calculation method: 'price_per_unit' or 'price_per_scaled_volume'",
                        enum_vals=["price_per_unit", "price_per_scaled_volume"],
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_category_trends,
    )


async def _exec_get_category_format_overview(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategoryFormatRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
        price_metric=args.get("price_metric", "price_per_unit"),
    )
    api_resp = await api.get_category_format_overview(request)

    result = {}
    charts = []
    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"
    api_resp_dict = api_resp.model_dump(mode="json", exclude_none=True)
    result["summary"] = json.dumps(api_resp_dict["summary"], indent=2)
    return result


def create_get_category_format_overview_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category format overview."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_format_overview",
            description="Get Category Format Overview analytics showing performance breakdown by product format and packaging type",
            parameters=ToolParameter(
                properties={
                    **_get_common_filter_properties(filter_context),
                    "price_metric": _string_property(
                        "Price calculation method: 'price_per_unit' or 'price_per_scaled_volume'",
                        enum_vals=["price_per_unit", "price_per_scaled_volume"],
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_category_format_overview,
    )


async def _exec_get_category_price_tiers(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategoryPriceTiersRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
        price_metric=args.get("price_metric", "price_per_unit"),
    )
    api_resp = await api.get_category_price_tiers(request)
    result = {}
    charts = []
    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"
    result["summary"] = json.dumps(api_resp.summary, indent=2)
    return result


def create_get_category_price_tiers_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category price tiers."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_price_tiers",
            description=(
                "Get Price Tiers. "
                "Returns: tier definitions, sales & volume by tier, share by tier, growth by tier, brand distribution across tiers. "
                "Usage: (1) Call broad to establish tier structure; (2) Drill by brand to see positioning; (3) Drill by retailer to detect tier polarization; (4) Switch price_metric to validate premiumization. "
                "Example questions: Is the category trading up or down? Which brands dominate premium tiers? Where is value-tier growth concentrated? Is growth inflation-driven?"
            ),
            parameters=ToolParameter(
                properties={
                    **_get_common_filter_properties(filter_context),
                    "price_metric": _string_property(
                        "Price calculation method: 'price_per_unit' or 'price_per_scaled_volume'",
                        enum_vals=["price_per_unit", "price_per_scaled_volume"],
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_category_price_tiers,
    )


async def _exec_get_category_pack_sizes(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategoryPackSizeRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
        price_metric=args.get("price_metric", "price_per_unit"),
    )
    api_resp = await api.get_category_pack_sizes(request)
    result = {}
    charts = []
    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"
    result["summary"] = json.dumps(api_resp.summary, indent=2)
    return result


def create_get_category_pack_sizes_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category pack sizes."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_pack_sizes",
            description=(
                "Get Pack Size Overview. "
                "Returns: sales & volume by pack size band, growth by pack size, share distribution, average price by pack band. "
                "Usage: (1) Call broad to detect pack mix shifts; (2) Narrow by retailer to detect format differences; (3) Cross-check with Price Tiers to separate size vs price effects. "
                "Example questions: Is growth coming from larger packs? Are smaller packs declining? Is pack mix driving premiumization? Are retailers skewed toward certain formats?"
            ),
            parameters=ToolParameter(
                properties={
                    **_get_common_filter_properties(filter_context),
                    "price_metric": _string_property(
                        "Price calculation method: 'price_per_unit' or 'price_per_scaled_volume'",
                        enum_vals=["price_per_unit", "price_per_scaled_volume"],
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_category_pack_sizes,
    )


async def _exec_get_category_products(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategoryProductRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
        price_metric=args.get("price_metric", "price_per_unit"),
        limit=args.get("limit", 50),
    )
    api_resp = await api.get_category_products(request)
    result = {}
    charts = []
    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"
    if api_resp.coverage:
        result["coverage"] = json.dumps(api_resp.coverage, indent=2)
    result["summary"] = json.dumps(api_resp.summary, indent=2)
    return result


def create_get_category_products_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category products."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_products",
            description="Get Category Product Landscape showing individual product performance, positioning, and market share",
            parameters=ToolParameter(
                properties={
                    **_get_common_filter_properties(filter_context),
                    "price_metric": _string_property(
                        "Price calculation method: 'price_per_unit' or 'price_per_scaled_volume'",
                        enum_vals=["price_per_unit", "price_per_scaled_volume"],
                    ),
                    "limit": _integer_property(
                        "Maximum number of products to return (default: 50)"
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_category_products,
    )


async def _exec_get_category_seasonality(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategorySeasonalityRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
        granularity=args.get("granularity", "month"),
        split_by=args.get("split_by"),
    )
    api_resp = await api.get_category_seasonality(request)
    result = {}
    charts = []
    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"

    full_resp_dict = api_resp.model_dump(mode="json", exclude_none=True)
    result["summary"] = json.dumps(full_resp_dict["summary"], indent=2)
    return result


def create_get_category_seasonality_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category seasonality."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_seasonality",
            description=(
                "Get Seasonality. "
                "Returns: monthly/weekly trend curves, seasonality index, peak/trough periods, brand seasonality comparison. "
                "Usage: (1) Call broad to identify seasonal peaks; (2) Drill by brand to compare amplitude; (3) Use retailer filter to detect timing shifts. "
                "Example questions: When does the category peak? Is our brand more seasonal than competitors? Are promotions aligned with demand peaks? Are some channels counter-seasonal?"
            ),
            parameters=ToolParameter(
                properties={
                    **_get_common_filter_properties(filter_context),
                    "granularity": _string_property(
                        "Time granularity: 'month' or 'week'",
                        enum_vals=["month", "week"],
                    ),
                    "split_by": _string_property(
                        "Split analysis by: 'brand', 'retailer', 'subcategory', or 'product'",
                        enum_vals=["brand", "retailer", "subcategory", "product"],
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_category_seasonality,
    )


async def _exec_get_category_innovation(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CategoryInnovationRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
        channels=_parse_list_param(args.get("channels")),
    )
    api_resp = await api.get_category_innovation(request)

    result = {}
    charts = []
    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))
    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"

    full_resp_dict = api_resp.model_dump(mode="json", exclude_none=True)
    result["summary"] = json.dumps(full_resp_dict["summary"], indent=2)
    return result


def create_get_category_innovation_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for category innovation."""
    return Tool(
        definition=ToolInput(
            name="skai_get_category_innovation",
            description=(
                "Get Innovation & Discontinuation. "
                "Returns: % of sales from new SKUs, discontinuation rates, growth contribution of innovation, innovation by brand. "
                "Usage: (1) Call category-level to assess innovation intensity; (2) Drill by brand to compare innovation strategies; (3) Switch to discontinuation view for portfolio cleanup analysis. "
                "Example questions: Is innovation driving growth? Which brands rely most on new launches? Are we over-indexed on discontinuations? Is innovation offsetting base erosion?"
            ),
            parameters=ToolParameter(
                properties=_get_common_filter_properties(filter_context),
                required=[],
            ),
        ),
        executor=_exec_get_category_innovation,
    )


# =============================================================================
# Channel Tools
# =============================================================================


async def _exec_get_channel_landscape(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ChannelLandscapeRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        subcategories=_parse_list_param(args.get("subcategories")),
        split_by=args.get("split_by", "brand"),
        client_brand=args.get("client_brand"),
    )
    api_resp = await api.get_channel_landscape(request)

    result = {}
    charts = []
    for chart in api_resp.charts:
        if not chart.data:
            continue
        charts.append(chart.model_dump(mode="json", exclude_none=True))

    if charts:
        result["charts"] = json.dumps(charts, indent=2)
    else:
        result["charts"] = "No charts available"
    result["summary"] = json.dumps(api_resp.summary, indent=2)
    return result


def create_get_channel_landscape_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for channel landscape."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_channel_landscape",
            description=(
                "Get Channel Landscape. "
                "Returns: sales & volume by channel, channel share, growth by channel, average price by channel, contribution to total growth. "
                "Usage: (1) Start broad (category + time range) to compare channels; (2) Narrow by brand to see channel strengths; (3) Switch price_metric to detect pricing differences by channel. "
                "Example questions: Which channel is driving growth? Are we over-indexed in declining channels? Is modern trade outperforming traditional? Are prices higher in specific channels?"
            ),
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "brands": common["brands"],
                    "retailers": common["retailers"],
                    "subcategories": common["subcategories"],
                    "split_by": _string_property(
                        "Split analysis by: 'brand', 'subcategory', or 'sku' (default: brand)",
                        enum_vals=["brand", "subcategory", "sku"],
                    ),
                    "client_brand": _string_property(
                        "Brand for benchmark comparison",
                        enum_vals=filter_context.brands,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_channel_landscape,
    )


async def _exec_get_channel_assortment(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = AssortmentRequest(
        super_category=None,
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        sku_ids=_parse_list_param(args.get("sku_ids")),
    )
    api_resp = await api.get_channel_assortment(request)

    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_channel_assortment_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for channel assortment."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_channel_assortment",
            description=(
                "Get Assortment Overview. "
                "Returns: SKU count by retailer/channel, assortment breadth & depth, velocity (volume per distribution point), ACV-weighted distribution. "
                "Usage: (1) Compare distribution footprint across retailers; (2) Identify SKU gaps or overexposure; (3) Cross-check with velocity for productivity analysis. "
                "Example questions: Are we under-distributed in key retailers? Which SKUs are low velocity? Is assortment aligned with performance? Where can we rationalize SKUs?"
            ),
            parameters=ToolParameter(
                properties={
                    "brands": common["brands"],
                    "retailers": common["retailers"],
                    "sku_ids": _array_property(
                        "Filter by specific SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_channel_assortment,
    )


async def _exec_get_channel_fair_share(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ChannelFairShareRequest(
        super_category=None,
        brands=_parse_list_param(args.get("brands")),
    )
    api_resp = await api.get_channel_fair_share(request)

    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_channel_fair_share_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for promo fair share."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_channel_fair_share",
            description="Get Promo Fair Share analysis comparing market share vs promotional investment share by brand",
            parameters=ToolParameter(
                properties={
                    "brands": common["brands"],
                },
                required=[],
            ),
        ),
        executor=_exec_get_channel_fair_share,
    )


async def _exec_get_channel_intensity(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ChannelIntensityRequest(
        super_category=None,
        brands=_parse_list_param(args.get("brands")),
        by=args.get("by", "brand"),
    )
    api_resp = await api.get_channel_intensity(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_channel_intensity_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for promo intensity heatmap."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_channel_intensity",
            description=(
                "Get Promo Intensity Heatmap. "
                "Returns: promo investment, % volume on promo, % weeks on promo, discount depth, average duration, and growth by brand or retailer. "
                "Usage: (1) Size total promo pressure by brand or retailer; (2) Compare intensity before drilling deeper into ROI tools; (3) Build retailer or brand rollups for promo investment concentration. "
                "Example questions: Where is promo spend concentrated? Which retailers or brands carry the most promo intensity? Are certain brands over-reliant on promotions?"
            ),
            parameters=ToolParameter(
                properties={
                    "brands": common["brands"],
                    "by": _string_property(
                        "Group results by: 'brand' or 'retailer' (default: brand)",
                        enum_vals=["brand", "retailer"],
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_channel_intensity,
    )


async def _exec_get_channel_transparency_brand(
    agent: ExecutionAgent, args: dict
) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ChannelTransparencyRequest(
        super_category=None,
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
    )
    api_resp = await api.get_channel_transparency_brand(request)

    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_channel_transparency_brand_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for brand transparency."""
    return Tool(
        definition=ToolInput(
            name="skai_get_channel_transparency_brand",
            description=(
                "Get Promo Transparency by Brand. "
                "Returns: promo investment, % volume on promo, % weeks on promo, average discount depth, average promo duration, and growth by brand. "
                "Usage: (1) Answer average promo depth and duration by brand; (2) compare brand-level promo pressure and funding; (3) create brand tables for depth, duration, and investment before checking ROI. "
                "Example questions: What is the average promo depth and duration by brand? Which brands invest most in promotions? Which brands are promotion-heavy vs promotion-light?"
            ),
            parameters=ToolParameter(
                properties=_get_promo_filter_properties(
                    filter_context, include_promo_tactics=False
                ),
                required=[],
            ),
        ),
        executor=_exec_get_channel_transparency_brand,
    )


async def _exec_get_channel_transparency_retailer(
    agent: ExecutionAgent, args: dict
) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ChannelTransparencyRequest(
        super_category=None,
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
    )
    api_resp = await api.get_channel_transparency_retailer(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_channel_transparency_retailer_tool(
    filter_context: FilterOptions,
) -> Tool:
    """Create tool for retailer transparency."""
    return Tool(
        definition=ToolInput(
            name="skai_get_channel_transparency_retailer",
            description=(
                "Get Promo Transparency by Retailer. "
                "Returns: promo investment, % volume on promo, % weeks on promo, average discount depth, average promo duration, and growth by retailer. "
                "Usage: (1) Answer total promo investment by retailer; (2) compare retailer-level depth, duration, and promo pressure; (3) build retailer tables before checking tactic or event ROI. "
                "Example questions: What is total promo investment by retailer? Which retailers run deeper or longer events? Which retailers are most promotion-heavy?"
            ),
            parameters=ToolParameter(
                properties=_get_promo_filter_properties(
                    filter_context, include_promo_tactics=False
                ),
                required=[],
            ),
        ),
        executor=_exec_get_channel_transparency_retailer,
    )


async def _exec_get_channel_transparency_sku(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ChannelTransparencyRequest(
        super_category=None,
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
    )
    api_resp = await api.get_channel_transparency_sku(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_channel_transparency_sku_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for SKU transparency."""
    return Tool(
        definition=ToolInput(
            name="skai_get_channel_transparency_sku",
            description=(
                "Get Promo Transparency by SKU. "
                "Returns: promo investment, % volume on promo, % weeks on promo, average discount depth, average promo duration, and growth by SKU. "
                "Usage: Drill into SKU-level promo behaviour, compare SKU reliance on promotions, and identify over-promoted or under-promoted SKUs before event-level analysis. "
                "Example questions: Which SKUs are most promotion-dependent? Which SKUs receive the deepest discounts? Is promo intensity aligned with SKU performance?"
            ),
            parameters=ToolParameter(
                properties=_get_promo_filter_properties(
                    filter_context, include_promo_tactics=False
                ),
                required=[],
            ),
        ),
        executor=_exec_get_channel_transparency_sku,
    )


# =============================================================================
# Consumer Pricing Tools
# =============================================================================


async def _exec_get_brand_ladder(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = BrandLadderRequest(
        super_category=None,
        sku_ids=_parse_list_param(args.get("sku_ids")),
        brands=_parse_list_param(args.get("brands")),
        subcategories=_parse_list_param(args.get("subcategories")),
        retailers=_parse_list_param(args.get("retailers")),
    )
    api_resp = await api.get_brand_ladder(request)

    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_brand_ladder_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for brand ladder."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_brand_ladder",
            description=(
                "Get Competitive Landscape (Brand Ladder). "
                "Returns: brand share ranking, price positioning, growth ranking, share ladder visualization. "
                "Usage: (1) Call broad to establish hierarchy; (2) Filter by retailer to see localized ladders; (3) Switch price metric to test positioning consistency. "
                "Example questions: Who are the price leaders? Are we priced above our share position? Is growth concentrated at the top or fragmented? Is there white space between tiers?"
            ),
            parameters=ToolParameter(
                properties={
                    "brands": common["brands"],
                    "subcategories": common["subcategories"],
                    "retailers": common["retailers"],
                    "sku_ids": _array_property(
                        "Filter by SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_brand_ladder,
    )


### Validated tools up to here ###


async def _exec_get_price_pack_curve(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = PricePackCurveRequest(
        super_category=None,
        sku_ids=_parse_list_param(args.get("sku_ids")),
        brands=_parse_list_param(args.get("brands")),
        pack_size_ranges=_parse_list_param(args.get("pack_size_ranges")),
    )
    api_resp = await api.get_price_pack_curve(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_price_pack_curve_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for price pack curve."""
    common = _get_common_filter_properties(filter_context)
    pack_ranges = filter_context.pack_size.ranges if filter_context.pack_size else []
    return Tool(
        definition=ToolInput(
            name="skai_get_price_pack_curve",
            description=(
                "Get Price Pack Curve. "
                "Returns: price vs pack-size scatter, competitive clustering, architecture gaps, outlier SKUs. "
                "Usage: (1) Visualize price architecture; (2) Detect incoherent pack ladders; (3) Identify white space opportunities. "
                "Example questions: Is our price ladder coherent? Are large packs properly discounted? Are there price gaps in portfolio? Are we misaligned vs competitors?"
            ),
            parameters=ToolParameter(
                properties={
                    "brands": common["brands"],
                    "pack_size_ranges": _array_property(
                        "Filter by pack size ranges (comma-separated)",
                        enum_vals=pack_ranges,
                        nullable=True,
                    ),
                    "sku_ids": _array_property(
                        "Filter by SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_price_pack_curve,
    )


# =============================================================================
# Simulator Tools
# =============================================================================


async def _exec_get_simulator_base(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = SimulatorBaseRequest(
        retailers=_parse_list_param(args.get("retailers")),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        sku_ids=_parse_list_param(args.get("sku_ids")),
        owned_brand=args.get("owned_brand"),
        include_zero_volume=args.get("include_zero_volume", False),
    )
    api_resp = await api.get_simulator_base(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_simulator_base_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for simulator base data."""
    # common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_simulator_base",
            description="Get SKU base data for pricing simulator including current prices, volumes, and elasticities",
            parameters=ToolParameter(
                properties={
                    # "retailers": common["retailers"],
                    # "brands": common["brands"],
                    # "categories": common["categories"],
                    # "subcategories": common["subcategories"],
                    "sku_ids": _array_property(
                        "Filter by SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                    # "owned_brand": _string_property(
                    #     "Owned brand filter",
                    #     nullable=True,
                    # ),
                    # "include_zero_volume": _boolean_property(
                    #     "Include zero-volume SKUs (default: false)"
                    # ),
                },
                # TODO: add required properties later again
                required=[],
            ),
        ),
        executor=_exec_get_simulator_base,
    )


async def _exec_run_simulation(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    price_changes_data = _parse_json_param(args.get("price_changes", []))
    price_changes = [PriceChange(**pc) for pc in price_changes_data]

    npi_products = None
    if args.get("npi_products"):
        npi_data = _parse_json_param(args["npi_products"]) or []
        npi_products = [NPIProduct(**npi) for npi in npi_data]

    config = SimulationConfig(
        elasticity_mode=args.get("elasticity_mode", "fallback"),
        vtm_mode=args.get("vtm_mode", "market_share"),
    )

    request = SimulatorRunRequest(
        price_changes=price_changes,
        npi_products=npi_products,
        owned_brand=args.get("owned_brand"),
        config=config,
        include_charts=args.get("include_charts", False),
    )
    api_resp = await api.run_simulation(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_run_simulation_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for running simulation."""
    return Tool(
        definition=ToolInput(
            name="skai_run_simulation",
            description="Run a pricing simulation with specified price changes and see projected impact on volume, sales, and margin",
            parameters=ToolParameter(
                properties={
                    "price_changes": _string_property(
                        "JSON array of price changes: [{product_id: int, new_price: float, delisted: bool}]"
                    ),
                    "npi_products": _string_property(
                        "JSON array of new products to add: [{sku_id: str, brand: str, price: float, cost: float}]",
                        nullable=True,
                    ),
                    "owned_brand": _string_property(
                        "Name of the owned brand for analysis",
                        nullable=True,
                    ),
                    "elasticity_mode": _string_property(
                        "Elasticity mode: 'fallback', 'utility_based', or 'precomputed'"
                    ),
                    "vtm_mode": _string_property(
                        "VTM mode: 'market_share', 'aggregated_utilities', or 'utility_blend'"
                    ),
                    "include_charts": _boolean_property(
                        "Include chart data in response"
                    ),
                },
                required=["price_changes"],
            ),
        ),
        executor=_exec_run_simulation,
    )


async def _exec_list_scenarios(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ScenarioListRequest(
        status=args.get("status"),
        limit=args.get("limit", 50),
        offset=args.get("offset", 0),
    )
    api_resp = await api.list_scenarios(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_list_scenarios_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for listing scenarios."""
    return Tool(
        definition=ToolInput(
            name="skai_list_scenarios",
            description="List saved pricing simulation scenarios with optional status filter",
            parameters=ToolParameter(
                properties={
                    "status": _string_property(
                        "Filter by status: 'draft', 'saved', or 'archived'",
                        enum_vals=["draft", "saved", "archived"],
                        nullable=True,
                    ),
                    "limit": _integer_property(
                        "Maximum number of scenarios to return (default: 50)"
                    ),
                    "offset": _integer_property("Offset for pagination"),
                },
                required=[],
            ),
        ),
        executor=_exec_list_scenarios,
    )


async def _exec_create_scenario(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ScenarioCreate(
        scenario_name=args["scenario_name"],
        description=args.get("description"),
        config=_parse_json_param(args.get("config", {})),
        price_changes=_parse_json_param(args.get("price_changes", [])),
        results=_parse_json_param(args.get("results")),
        kpis=_parse_json_param(args.get("kpis")),
        waterfall_data=_parse_json_param(args.get("waterfall_data")),
    )
    api_resp = await api.create_scenario(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_create_scenario_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for creating scenario."""
    return Tool(
        definition=ToolInput(
            name="skai_create_scenario",
            description="Save a pricing simulation scenario for later retrieval",
            parameters=ToolParameter(
                properties={
                    "scenario_name": _string_property("Name for the scenario"),
                    "description": _string_property(
                        "Description of the scenario", nullable=True
                    ),
                    "config": _string_property(
                        "JSON object with simulation configuration"
                    ),
                    "price_changes": _string_property("JSON array of price changes"),
                    "results": _string_property(
                        "JSON array of simulation results", nullable=True
                    ),
                    "kpis": _string_property("JSON object with KPIs", nullable=True),
                    "waterfall_data": _string_property(
                        "JSON object with waterfall data", nullable=True
                    ),
                },
                required=["scenario_name", "price_changes"],
            ),
        ),
        executor=_exec_create_scenario,
    )


async def _exec_get_scenario(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    api_resp = await api.get_scenario(args["scenario_id"])
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_scenario_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for getting scenario."""
    return Tool(
        definition=ToolInput(
            name="skai_get_scenario",
            description="Get a saved pricing simulation scenario by ID",
            parameters=ToolParameter(
                properties={
                    "scenario_id": _integer_property("ID of the scenario to retrieve"),
                },
                required=["scenario_id"],
            ),
        ),
        executor=_exec_get_scenario,
    )


async def _exec_delete_scenario(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    await api.delete_scenario(args["scenario_id"])
    return {"deleted": True, "scenario_id": args["scenario_id"]}


def create_delete_scenario_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for deleting scenario."""
    return Tool(
        definition=ToolInput(
            name="skai_delete_scenario",
            description="Delete a saved pricing simulation scenario",
            parameters=ToolParameter(
                properties={
                    "scenario_id": _integer_property("ID of the scenario to delete"),
                },
                required=["scenario_id"],
            ),
        ),
        executor=_exec_delete_scenario,
    )


# =============================================================================
# CDT Tools
# =============================================================================


async def _exec_build_cdt(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = CDTRequest(
        retailer=args.get("retailer"),
        category=args.get("category"),
        attributes=(
            _parse_list_param(args.get("attributes"))
            or ["brand", "pack_size_range", "price_tier"]
        ),
        max_depth=args.get("max_depth", 3),
        min_gain=args.get("min_gain", 0.05),
        params=CDTParams(time_decay_half_life=None),
    )
    api_resp = await api.build_cdt(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_build_cdt_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for building CDT."""
    return Tool(
        definition=ToolInput(
            name="skai_build_cdt",
            description="Build a Consumer Decision Tree showing how consumers navigate purchase decisions by attributes like brand, pack size, and price tier",
            parameters=ToolParameter(
                properties={
                    "retailer": _string_property(
                        "Retailer to analyze",
                        enum_vals=filter_context.retailers,
                        nullable=True,
                    ),
                    "category": _string_property(
                        "Category to analyze",
                        enum_vals=filter_context.categories,
                        nullable=True,
                    ),
                    "attributes": _array_property(
                        "Attributes for tree splitting (default: brand, pack_size_range, price_tier)",
                        enum_vals=["brand", "pack_size_range", "price_tier"],
                    ),
                    "max_depth": _integer_property(
                        "Maximum tree depth (1-5, default: 3)"
                    ),
                    "min_gain": _number_property(
                        "Minimum gain threshold (default: 0.05)"
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_build_cdt,
    )


# =============================================================================
# Elasticity Tools
# =============================================================================


async def _exec_get_elasticities(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ElasticityRequest(
        retailer=args.get("retailer"),
        category=args.get("category"),
        subcategory=args.get("subcategory"),
        sku_ids=_parse_list_param(args.get("sku_ids")),
        include_excluded=args.get("include_excluded", False),
    )
    api_resp = await api.get_elasticities(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_elasticities_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for getting elasticities."""
    return Tool(
        definition=ToolInput(
            name="skai_get_elasticities",
            description="Calculate price elasticities for SKUs showing how volume responds to price changes",
            parameters=ToolParameter(
                properties={
                    "retailer": _string_property(
                        "Filter by retailer",
                        enum_vals=filter_context.retailers,
                        nullable=True,
                    ),
                    "category": _string_property(
                        "Filter by category",
                        enum_vals=filter_context.categories,
                        nullable=True,
                    ),
                    "subcategory": _string_property(
                        "Filter by subcategory",
                        enum_vals=filter_context.subcategories,
                        nullable=True,
                    ),
                    "sku_ids": _array_property(
                        "Filter by specific SKU IDs",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                    "include_excluded": _boolean_property(
                        "Include excluded models in results"
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_elasticities,
    )


# =============================================================================
# Promo Tools
# =============================================================================


async def _exec_get_promo_calendar(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = PromoRequest(
        super_category=None,
        sku_ids=_parse_list_param(args.get("sku_ids")),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
    )
    api_resp = await api.get_promo_calendar(request)

    settings = get_settings()

    if len(api_resp.data) > settings.skai_max_data_items:
        alt_resp = api_resp.large_payload_alternative()
        if agent.code_interpreter_mode is None:
            return {
                **alt_resp.summarised_data,
                "additional_info": "Large payload detected. If you want to analyse the data"
                "Call `skai_get_promo_calendar` tool with parameter values like brands, retailers, etc. multiple times.",
            }
        df = pd.DataFrame(alt_resp.dataset)
        summarised_data = alt_resp.summarised_data
        summarised_data.pop("summary")
        if agent.code_interpreter_mode == "local":
            file_path = _write_local_code_execution_dataset(
                agent.session_id,
                "promo_calendar",
                df,
            )
            return {
                **summarised_data,
                "additional_info": "Large payload detected. Use code interpreter "
                f"tool to analyse data saved in file {file_path} in CSV format",
            }
        elif agent.code_interpreter_mode == "openai":
            if agent.code_execution_container_id is None:
                raise ValueError("Code execution container ID is not set")
            dataset_bytes = df.to_csv(index=False).encode("utf-8")
            # args_str = [f"{k}={v}" for k, v in args.items() if v]
            file_name = "promo_calendar"
            file_path = await agent.llm_service.create_container_file(
                container_id=agent.code_execution_container_id,
                file_name=file_name,
                file_content=dataset_bytes,
            )

            return {
                **summarised_data,
                "additional_info": f"Large payload detected. Use code interpreter "
                f"tool to analyse data saved in file {file_path} in CSV format",
            }

    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_calendar_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for promo calendar."""
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_calendar",
            description=(
                "Get Promo Calendar Overview. "
                "Returns: event-level promo timing with SKU, brand, retailer, start/end dates, duration, discount depth, uplift, ROI, and investment. "
                "Usage: (1) Read the current promo calendar by mechanism, brand, or retailer; (2) detect overlap, clustering, whitespace, and timing gaps; (3) compare sub-category or SKU calendars when optimizing future plans. "
                "Example questions: What is the current promo calendar like by mechanism, brand, or retailer? Are promos clustered? Are brands overlapping and cannibalizing? Where are the strategic gaps in the calendar?"
            ),
            parameters=ToolParameter(
                properties={
                    **_get_promo_filter_properties(filter_context),
                    "sku_ids": _array_property(
                        "Filter by SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_promo_calendar,
    )


async def _exec_get_promo_investment_trends(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = PromoRequest(
        super_category=None,
        sku_ids=_parse_list_param(args.get("sku_ids")),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
    )
    api_resp = await api.get_promo_investment_trends(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_investment_trends_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for promo investment trends."""
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_investment_trends",
            description=(
                "Get Investment Trends & ROI Heatmap. "
                "Returns: promo investment over time by period and group, plus summary totals. "
                "Usage: (1) Answer total promo investment by month, retailer, or brand using time filters; (2) create monthly retailer and brand rollups; (3) spot under-invested or over-invested periods before deeper ROI diagnosis. "
                "Example questions: What is total promo investment by month, retailer, and brand? What is total promo investment by retailer? What is total promo investment by brand?"
            ),
            parameters=ToolParameter(
                properties={
                    **_get_promo_filter_properties(filter_context),
                    "sku_ids": _array_property(
                        "Filter by SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_promo_investment_trends,
    )


async def _exec_get_promo_heatmap(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = HeatmapRequest(
        super_category=None,
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
        x_axis=args.get("x_axis", "retailer"),
        y_axis=args.get("y_axis", "sku"),
        sku_ids=_parse_list_param(args.get("sku_ids")),
    )
    api_resp = await api.get_promo_heatmap(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_heatmap_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for promo heatmap."""
    promo_props = _get_promo_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_heatmap",
            description=(
                "Get Promo Intensity Heatmap. "
                "Returns: a two-dimensional heatmap of ROI, uplift, and investment across retailer, brand, SKU, category, subcategory, depth, duration, or time-since-last dimensions. "
                "Usage: (1) Build retailer x brand or retailer x depth matrices; (2) compare totals and hotspots across retailers; (3) support questions about where ROI or investment is concentrated before drilling into events. "
                "Example questions: Which retailers have the strongest ROI pockets? Where is promo spend concentrated? Are some depth or duration combinations consistently weaker?"
            ),
            parameters=ToolParameter(
                properties={
                    **promo_props,
                    "x_axis": _string_property(
                        "X-axis dimension: 'brand', 'sku', 'retailer', 'category', or 'subcategory' (default: retailer)",
                        enum_vals=[
                            "brand",
                            "sku",
                            "retailer",
                            "category",
                            "subcategory",
                        ],
                    ),
                    "y_axis": _string_property(
                        "Y-axis dimension: 'brand', 'sku', 'retailer', 'category', or 'subcategory' (default: sku)",
                        enum_vals=[
                            "brand",
                            "sku",
                            "retailer",
                            "category",
                            "subcategory",
                        ],
                    ),
                    "sku_ids": _array_property(
                        "Filter by SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_promo_heatmap,
    )


async def _exec_get_promo_event_scatter(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    legend = args.get("legend") or "brand"
    request = EventScatterRequest(
        super_category=None,
        sku_ids=_parse_list_param(args.get("sku_ids")),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
        roi_min=args.get("roi_min"),
        roi_max=args.get("roi_max"),
        uplift_min=args.get("uplift_min"),
        uplift_max=args.get("uplift_max"),
        legend=ScatterLegend(legend),
    )
    api_resp = await api.get_promo_event_scatter(request)

    settings = get_settings()
    if len(api_resp.data) > settings.skai_max_data_items:
        alt_resp = api_resp.large_payload_alternative()

        if agent.code_interpreter_mode is None:
            return {
                **alt_resp.summarised_data,
                "additional_info": "Large payload detected. If you want to analyse the data"
                "Call `skai_get_promo_event_scatter` tool with parameter values like brands, retailers, etc. multiple times.",
            }

        df = pd.DataFrame(alt_resp.dataset)
        summarised_data = alt_resp.summarised_data
        summarised_data.pop("summary")
        if agent.code_interpreter_mode == "local":
            file_path = _write_local_code_execution_dataset(
                agent.session_id,
                "promo_event_scatter",
                df,
            )
            return {
                **summarised_data,
                "additional_info": "Large payload detected. Use code interpreter "
                f"tool to analyse data saved in file {file_path} in CSV format",
            }
        if agent.code_interpreter_mode == "openai":
            if agent.code_execution_container_id is None:
                raise ValueError("Code execution container ID is not set")
            dataset_bytes = df.to_csv(index=False).encode("utf-8")
            # args_str = [f"{k}={v}" for k, v in args.items() if v]
            file_name = "promo_event_scatter"
            file_path = await agent.llm_service.create_container_file(
                container_id=agent.code_execution_container_id,
                file_name=file_name,
                file_content=dataset_bytes,
            )

            return {
                **summarised_data,
                "additional_info": f"Large payload detected. Use code interpreter "
                f"tool to analyse data saved in file {file_path} in CSV format",
            }

    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_event_scatter_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for event scatter."""
    promo_props = _get_promo_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_event_scatter",
            description=(
                "Get Promo Event Scatter & Tactic Effectiveness. "
                "Returns: event-level ROI, uplift, promo investment, discount depth, sales, volume, and legend splits for brand, retailer, SKU, depth, duration, or time-since-last. "
                "Usage: (1) Diagnose best and worst events; (2) compare retailers for the same depth bucket or tactic; (3) study low-ROI events as low-uplift vs high-cost quadrants; (4) identify structurally weak event patterns and top-performing events. "
                "Example questions: Are low-ROI events driven by low uplift or high cost? Does a 40% promo at Wickes outperform B&Q? What were the best promotions last year? Are deeper discounts more effective?"
            ),
            parameters=ToolParameter(
                properties={
                    **promo_props,
                    "roi_min": _number_property(
                        "Minimum ROI filter only when known", nullable=True
                    ),
                    "roi_max": _number_property(
                        "Maximum ROI filter only when known", nullable=True
                    ),
                    "uplift_min": _number_property(
                        "Minimum volume uplift filter only when known", nullable=True
                    ),
                    "uplift_max": _number_property(
                        "Maximum volume uplift filter only when known", nullable=True
                    ),
                    "legend": _string_property(
                        "Legend to get the event scatter for",
                        enum_vals=[
                            "brand",
                            "sku",
                            "retailer",
                            "depth_decile",
                            "duration",
                            "time_since_last",
                        ],
                    ),
                    "sku_ids": _array_property(
                        "Filter by SKU IDs (comma-separated)",
                        enum_vals=filter_context.sku_ids,
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_promo_event_scatter,
    )


async def _exec_get_promo_market_effectiveness(
    agent: ExecutionAgent, args: dict
) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = MarketEffectivenessRequest(
        super_category=None,
        by=args.get("by", "brand"),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
    )
    api_resp = await api.get_promo_market_effectiveness(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_market_effectiveness_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for market effectiveness."""
    promo_props = _get_promo_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_market_effectiveness",
            description=(
                "Get Promo Market Effectiveness. "
                "Returns: uplift, investment, incremental GP, ROI, and growth grouped by brand or retailer. "
                "Usage: (1) Assess category-wide or retailer-wide promo effectiveness; (2) compare whether promo is driving true incremental growth or just switching; (3) support structural over-promotion questions before drilling into events. "
                "Example questions: Is the category over-promoted? Is promo driving incremental demand or just switching? Are competitors or retailers structurally more efficient?"
            ),
            parameters=ToolParameter(
                properties={
                    "by": _string_property(
                        "Group by: 'brand' or 'retailer' (default: brand)",
                        enum_vals=["brand", "retailer"],
                    ),
                    **promo_props,
                },
                required=[],
            ),
        ),
        executor=_exec_get_promo_market_effectiveness,
    )


async def _exec_get_promo_tactic_effectiveness(
    agent: ExecutionAgent, args: dict
) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    x_axis = args.get("x_axis") or "promo_tactic"
    request = TacticEffectivenessRequest(
        super_category=None,
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
        x_axis=TacticXAxis(x_axis),
    )
    api_resp = await api.get_promo_tactic_effectiveness(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_tactic_effectiveness_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for tactic effectiveness."""
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_tactic_effectiveness",
            description=(
                "Get Tactic Effectiveness showing ROI, uplift, investment, incremental GP, and event count by promo tactic, depth, duration, or time-since-last. "
                "Usage: (1) Rank tactics by ROI or uplift; (2) compare tactic performance by retailer using filters; (3) test whether some tactics are structurally weaker across time or retailers. "
                "Example questions: What is average promo ROI by tactic? What is volume uplift per event type? Are there promo tactics with structurally lower ROI?"
            ),
            parameters=ToolParameter(
                properties={
                    **_get_promo_filter_properties(filter_context),
                    "x_axis": _string_property(
                        "X-axis dimension default promo_tactic",
                        enum_vals=[
                            "promo_tactic",
                            "depth_decile",
                            "duration",
                            "time_since_last",
                        ],
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_promo_tactic_effectiveness,
    )


async def _exec_get_promo_product_deep_dive(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ProductDeepDiveRequest(
        super_category=None,
        sku_id=args["sku_id"],
        retailer=args.get("retailer"),
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
    )
    api_resp = await api.get_promo_product_deep_dive(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_product_deep_dive_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for product deep dive."""
    promo_props = _get_promo_filter_properties(filter_context)
    promo_props.pop("retailers", None)
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_product_deep_dive",
            description=(
                "Get Product Deep-Dive showing detailed promo history and performance for a specific SKU, including event list, average ROI, average uplift, investment, depth, and duration. "
                "Usage: Use when the reasoning narrows to one SKU and one retailer or brand and you need the product's historical promo track record before making a recommendation."
            ),
            parameters=ToolParameter(
                properties={
                    "sku_id": _string_property(
                        "SKU ID to analyze",
                        enum_vals=filter_context.sku_ids,
                    ),
                    "retailer": _string_property(
                        "Optional retailer filter",
                        enum_vals=filter_context.retailers,
                        nullable=True,
                    ),
                    **promo_props,
                },
                required=["sku_id"],
            ),
        ),
        executor=_exec_get_promo_product_deep_dive,
    )


async def _exec_get_promo_discount_depth_qc(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = DiscountDepthQCRequest(
        super_category=None,
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        brands=_parse_list_param(args.get("brands")),
        retailers=_parse_list_param(args.get("retailers")),
        categories=_parse_list_param(args.get("categories")),
        subcategories=_parse_list_param(args.get("subcategories")),
        channels=_parse_list_param(args.get("channels")),
        depth_deciles=_parse_list_param(args.get("depth_deciles")),
        promo_tactics=_parse_list_param(args.get("promo_tactics")),
    )
    api_resp = await api.get_promo_discount_depth_qc(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_discount_depth_qc_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for discount depth QC."""
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_discount_depth_qc",
            description=(
                "Get Discount Depth QC showing event count, investment, average ROI, uplift, and growth by discount depth decile. "
                "Usage: (1) Compare ROI spreads across discount buckets; (2) identify optimal or weak depth bands; (3) support depth-driver analyses and discount optimization logic. "
                "Example questions: What is the ROI pattern by depth bucket? Which discount levels destroy value? What happens if we reduce depth in low-ROI events?"
            ),
            parameters=ToolParameter(
                properties=_get_promo_filter_properties(filter_context),
                required=[],
            ),
        ),
        executor=_exec_get_promo_discount_depth_qc,
    )


async def _exec_get_promo_planner(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = PromoPlannerRequest(
        sku_id=args["sku_id"],
        retailer=args.get("retailer"),
    )
    api_resp = await api.get_promo_planner(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_planner_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for promo planner."""
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_planner",
            description=(
                "Get Promo Planner recommendations for a SKU including baseline, historical promo stats, depth-performance readout, optimal depth, duration, and expected ROI. "
                "Usage: Use for SKU-level promo optimization or when testing one additional promo slot, a depth swap, or a tactic/depth recommendation for a specific SKU."
            ),
            parameters=ToolParameter(
                properties={
                    "sku_id": _string_property(
                        "SKU ID to get recommendations for",
                        enum_vals=filter_context.sku_ids,
                    ),
                    "retailer": _string_property(
                        "Optional retailer filter",
                        enum_vals=filter_context.retailers,
                        nullable=True,
                    ),
                },
                required=["sku_id"],
            ),
        ),
        executor=_exec_get_promo_planner,
    )


async def _exec_get_promo_baseline_review(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = BaselineReviewRequest(
        sku_id=args["sku_id"],
        retailer=args["retailer"],
    )
    api_resp = await api.get_promo_baseline_review(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_baseline_review_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for baseline review."""
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_baseline_review",
            description=(
                "Get Promo Baseline Review. "
                "Returns: weekly baseline volume, actual volume, volume uplift, promo investment, ROI, incremental GP, and discount depth for a SKU-retailer combination. "
                "Usage: (1) Read baseline vs uplift week by week; (2) aggregate selected SKU outputs into monthly retailer views; (3) analyze uplift seasonality and baseline erosion. "
                "Example questions: How does uplift vary by month? Is baseline eroding? Is promo driving incremental growth or only replacing base?"
            ),
            parameters=ToolParameter(
                properties={
                    "sku_id": _string_property(
                        "SKU ID to analyze",
                        enum_vals=filter_context.sku_ids,
                    ),
                    "retailer": _string_property(
                        "Retailer to analyze",
                        enum_vals=filter_context.retailers,
                    ),
                },
                required=["sku_id", "retailer"],
            ),
        ),
        executor=_exec_get_promo_baseline_review,
    )


async def _exec_get_promo_deep_dive_tactics(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = DeepDiveTacticRequest(
        sku_id=args["sku_id"],
        retailer=args["retailer"],
        group_by=args.get("group_by", "depth_decile"),
    )
    api_resp = await api.get_promo_deep_dive_tactics(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_promo_deep_dive_tactics_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for deep dive tactics."""
    return Tool(
        definition=ToolInput(
            name="skai_get_promo_deep_dive_tactics",
            description=(
                "Get SKU-level tactic deep dive showing P12 vs T12 performance grouped by depth decile, duration, or time since last event. "
                "Usage: Use after identifying an underperforming SKU event to test one lever at a time, such as changing depth, duration, or spacing between events."
            ),
            parameters=ToolParameter(
                properties={
                    "sku_id": _string_property(
                        "SKU ID to analyze",
                        enum_vals=filter_context.sku_ids,
                    ),
                    "retailer": _string_property(
                        "Retailer to analyze",
                        enum_vals=filter_context.retailers,
                    ),
                    "group_by": _string_property(
                        "Group by: 'depth_decile', 'duration', or 'time_since_last' (default: depth_decile)",
                        enum_vals=["depth_decile", "duration", "time_since_last"],
                    ),
                },
                required=["sku_id", "retailer"],
            ),
        ),
        executor=_exec_get_promo_deep_dive_tactics,
    )


# =============================================================================
# Net Pricing / B2B Tools
# =============================================================================


async def _exec_get_price_spread(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = PriceSpreadRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        group_by=args.get("group_by", "product"),
        customer_segments=_parse_list_param(args.get("customer_segments")),
        product_ids=_parse_list_param(args.get("product_ids")),
        categories=_parse_list_param(args.get("categories")),
        regions=_parse_list_param(args.get("regions")),
    )
    api_resp = await api.get_price_spread(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_price_spread_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for price spread."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_price_spread",
            description="Get Cross-Customer Price Spread showing price variance across customers for products",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "group_by": _string_property(
                        "Group by: 'product', 'category', 'region', 'customer', or 'segment'",
                        enum_vals=[
                            "product",
                            "category",
                            "region",
                            "customer",
                            "segment",
                        ],
                    ),
                    "customer_segments": _array_property(
                        "Filter by customer segments", nullable=True
                    ),
                    "product_ids": _array_property(
                        "Filter by product IDs", nullable=True
                    ),
                    "categories": common["categories"],
                    "regions": _array_property("Filter by regions", nullable=True),
                },
                required=[],
            ),
        ),
        executor=_exec_get_price_spread,
    )


async def _exec_get_pricing_evolution(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = PricingEvolutionRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        group_by=args.get("group_by", "customer"),
        customer_ids=_parse_list_param(args.get("customer_ids")),
        product_ids=_parse_list_param(args.get("product_ids")),
        customer_segments=_parse_list_param(args.get("customer_segments")),
        period_type=args.get("period_type", "quarter"),
    )
    api_resp = await api.get_pricing_evolution(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_pricing_evolution_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for pricing evolution."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_pricing_evolution",
            description="Get Customer Pricing Evolution showing how prices have changed over time with market average comparison",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "group_by": _string_property(
                        "Group by: 'product', 'category', 'region', 'customer', or 'segment'",
                        enum_vals=[
                            "product",
                            "category",
                            "region",
                            "customer",
                            "segment",
                        ],
                    ),
                    "customer_ids": _array_property(
                        "Filter by customer IDs", nullable=True
                    ),
                    "product_ids": _array_property(
                        "Filter by product IDs", nullable=True
                    ),
                    "customer_segments": _array_property(
                        "Filter by customer segments", nullable=True
                    ),
                    "period_type": _string_property(
                        "Period type: 'quarter' or 'month'",
                        enum_vals=["quarter", "month"],
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_pricing_evolution,
    )


async def _exec_get_price_outliers(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    include_severity = args.get("include_severity")
    request = PriceOutlierRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        detection_method=args.get("detection_method", "zscore"),
        zscore_threshold=args.get("zscore_threshold", "2.0"),
        percent_threshold=args.get("percent_threshold", "20.0"),
        customer_ids=_parse_list_param(args.get("customer_ids")),
        product_ids=_parse_list_param(args.get("product_ids")),
        include_severity=[Severity(include_severity)] if include_severity else None,
    )
    api_resp = await api.get_price_outliers(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_price_outliers_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for price outliers."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_price_outliers",
            description="Get Price Outliers Detection identifying transactions with unusual pricing using statistical methods",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "detection_method": _string_property(
                        "Detection method: 'zscore', 'iqr', or 'percent'",
                        enum_vals=["zscore", "iqr", "percent"],
                    ),
                    "zscore_threshold": _string_property(
                        "Z-score threshold (default: 2.0)"
                    ),
                    "percent_threshold": _string_property(
                        "Percent threshold (default: 20.0)"
                    ),
                    "customer_ids": _array_property(
                        "Filter by customer IDs", nullable=True
                    ),
                    "product_ids": _array_property(
                        "Filter by product IDs", nullable=True
                    ),
                    "include_severity": _string_property(
                        "Filter by severity: 'warning' or 'critical'",
                        enum_vals=["warning", "critical"],
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_price_outliers,
    )


# =============================================================================
# Trade Tools
# =============================================================================


async def _exec_get_gtn_waterfall(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = GTNWaterfallRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        group_by=args.get("group_by", "customer"),
        customer_ids=_parse_list_param(args.get("customer_ids")),
        channels=_parse_list_param(args.get("channels")),
        brands=_parse_list_param(args.get("brands")),
    )
    api_resp = await api.get_gtn_waterfall(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_gtn_waterfall_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for GTN waterfall."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_gtn_waterfall",
            description="Get Gross-to-Net Waterfall showing revenue leakage from gross to net across trade spend components",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "group_by": _string_property(
                        "Group by: 'customer', 'channel', 'product', or 'period'",
                        enum_vals=["customer", "channel", "product", "period"],
                    ),
                    "customer_ids": _array_property(
                        "Filter by customer IDs", nullable=True
                    ),
                    "channels": common["channels"],
                    "brands": common["brands"],
                },
                required=[],
            ),
        ),
        executor=_exec_get_gtn_waterfall,
    )


async def _exec_get_investment_drivers(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    driver_types = _parse_list_param_with_allowed_values(
        args.get("driver_types"),
        ["display", "feature", "price_cut", "tpr", "shipper", "end_cap"],
    )

    request = InvestmentDriverRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        customer_ids=_parse_list_param(args.get("customer_ids")),
        brands=_parse_list_param(args.get("brands")),
        driver_types=(
            [DriverType(driver_type) for driver_type in driver_types]
            if driver_types
            else None
        ),
    )
    api_resp = await api.get_investment_drivers(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_investment_drivers_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for investment drivers."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_investment_drivers",
            description="Get Trade Investment Drivers showing ROI by driver type (display, feature, price cut, etc.)",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "customer_ids": _array_property(
                        "Filter by customer IDs", nullable=True
                    ),
                    "brands": common["brands"],
                    "driver_types": _array_property(
                        "Filter by driver types: display, feature, price_cut, tpr, shipper, end_cap",
                        enum_vals=[
                            "display",
                            "feature",
                            "price_cut",
                            "tpr",
                            "shipper",
                            "end_cap",
                        ],
                        nullable=True,
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_investment_drivers,
    )


# =============================================================================
# Margin Tools
# =============================================================================


async def _exec_get_profit_pool(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = ProfitPoolRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        segment_type=args.get("segment_type", "customer_tier"),
        segments=_parse_list_param(args.get("segments")),
    )
    api_resp = await api.get_profit_pool(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_profit_pool_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for profit pool."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_profit_pool",
            description="Get Margin Pool Analysis showing revenue and margin distribution across segments with Pareto metrics",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "segment_type": _string_property(
                        "Segment by: 'customer_tier', 'channel', 'category', or 'region'",
                        enum_vals=["customer_tier", "channel", "category", "region"],
                    ),
                    "segments": _array_property(
                        "Filter by specific segments", nullable=True
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_profit_pool,
    )


async def _exec_get_customer_contribution(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = MarginContributionRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        customer_segments=_parse_list_param(args.get("customer_segments")),
        brands=_parse_list_param(args.get("brands")),
        limit=args.get("limit", 100),
    )
    api_resp = await api.get_customer_contribution(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_customer_contribution_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for customer contribution."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_customer_contribution",
            description="Get Customer Margin Contribution showing profitability ranking with revenue, costs, and margin by customer",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "customer_segments": _array_property(
                        "Filter by customer segments", nullable=True
                    ),
                    "brands": common["brands"],
                    "limit": _integer_property(
                        "Maximum number of results (default: 100)"
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_customer_contribution,
    )


async def _exec_get_portfolio_quadrant(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    request = PortfolioQuadrantRequest(
        start_date=args.get("start_date"),
        end_date=args.get("end_date"),
        entity_type=args.get("entity_type", "customer"),
        margin_threshold=args.get("margin_threshold"),
        growth_threshold=args.get("growth_threshold"),
    )
    api_resp = await api.get_portfolio_quadrant(request)
    return api_resp.model_dump(mode="json", exclude_none=True)


def create_get_portfolio_quadrant_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for portfolio quadrant."""
    common = _get_common_filter_properties(filter_context)
    return Tool(
        definition=ToolInput(
            name="skai_get_portfolio_quadrant",
            description="Get Portfolio Margin & Growth Quadrant classifying entities as stars, cash cows, question marks, or dogs",
            parameters=ToolParameter(
                properties={
                    "start_date": common["start_date"],
                    "end_date": common["end_date"],
                    "entity_type": _string_property(
                        "Entity type: 'customer', 'product', or 'category'",
                        enum_vals=["customer", "product", "category"],
                    ),
                    "margin_threshold": _string_property(
                        "Margin threshold for quadrant classification", nullable=True
                    ),
                    "growth_threshold": _string_property(
                        "Growth threshold for quadrant classification", nullable=True
                    ),
                },
                required=[],
            ),
        ),
        executor=_exec_get_portfolio_quadrant,
    )


# =============================================================================
# Download Tools
# =============================================================================


async def _exec_download(agent: ExecutionAgent, args: dict) -> Any:
    api = agent.skai_service
    args = await _clean_filter_args(args, api)
    sheets = _parse_json_param(args.get("sheets", {}))
    request = DownloadRequest(
        format=args.get("format", "xlsx"),
        sheets=sheets,
    )
    data = await api.download(request)
    return {
        "success": True,
        "format": "xlsx",
        "size_bytes": len(data),
        "message": "File downloaded successfully.",
    }


def create_download_tool(filter_context: FilterOptions) -> Tool:
    """Create tool for downloading data."""
    return Tool(
        definition=ToolInput(
            name="skai_download",
            description="Download data as an Excel file with specified sheets",
            parameters=ToolParameter(
                properties={
                    "format": _string_property(
                        "Download format (currently only 'xlsx' is supported)"
                    ),
                    "sheets": _string_property(
                        "JSON object mapping sheet names to arrays of row data"
                    ),
                },
                required=["sheets"],
            ),
        ),
        executor=_exec_download,
    )


# =============================================================================
# Tool Group Getters
# =============================================================================


def get_all_skai_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get all SKAI tools with their executors."""
    return [
        # Category
        create_get_category_landscape_tool(filter_context),
        create_get_category_trends_tool(filter_context),
        create_get_category_format_overview_tool(filter_context),
        create_get_category_price_tiers_tool(filter_context),
        create_get_category_pack_sizes_tool(filter_context),
        create_get_category_products_tool(filter_context),
        create_get_category_seasonality_tool(filter_context),
        create_get_category_innovation_tool(filter_context),
        # Channel
        create_get_channel_landscape_tool(filter_context),
        create_get_channel_assortment_tool(filter_context),
        create_get_channel_fair_share_tool(filter_context),
        create_get_channel_intensity_tool(filter_context),
        create_get_channel_transparency_brand_tool(filter_context),
        create_get_channel_transparency_retailer_tool(filter_context),
        create_get_channel_transparency_sku_tool(filter_context),
        # Consumer Pricing
        create_get_brand_ladder_tool(filter_context),
        create_get_price_pack_curve_tool(filter_context),
        # Simulator
        create_get_simulator_base_tool(filter_context),
        create_run_simulation_tool(filter_context),
        create_list_scenarios_tool(filter_context),
        create_create_scenario_tool(filter_context),
        create_get_scenario_tool(filter_context),
        create_delete_scenario_tool(filter_context),
        # CDT
        create_build_cdt_tool(filter_context),
        # Elasticity
        create_get_elasticities_tool(filter_context),
        # Promo
        create_get_promo_calendar_tool(filter_context),
        create_get_promo_investment_trends_tool(filter_context),
        create_get_promo_heatmap_tool(filter_context),
        create_get_promo_event_scatter_tool(filter_context),
        create_get_promo_market_effectiveness_tool(filter_context),
        create_get_promo_tactic_effectiveness_tool(filter_context),
        create_get_promo_product_deep_dive_tool(filter_context),
        create_get_promo_discount_depth_qc_tool(filter_context),
        create_get_promo_planner_tool(filter_context),
        create_get_promo_baseline_review_tool(filter_context),
        create_get_promo_deep_dive_tactics_tool(filter_context),
        # Net Pricing / B2B
        create_get_price_spread_tool(filter_context),
        create_get_pricing_evolution_tool(filter_context),
        create_get_price_outliers_tool(filter_context),
        # Trade
        create_get_gtn_waterfall_tool(filter_context),
        create_get_investment_drivers_tool(filter_context),
        # Margin
        create_get_profit_pool_tool(filter_context),
        create_get_customer_contribution_tool(filter_context),
        create_get_portfolio_quadrant_tool(filter_context),
        # Downloads
        create_download_tool(filter_context),
    ]


def get_category_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get category-related tools with their executors."""
    return [
        create_get_category_landscape_tool(filter_context),
        create_get_category_trends_tool(filter_context),
        create_get_category_format_overview_tool(filter_context),
        create_get_category_price_tiers_tool(filter_context),
        create_get_category_pack_sizes_tool(filter_context),
        create_get_category_products_tool(filter_context),
        create_get_category_seasonality_tool(filter_context),
        create_get_category_innovation_tool(filter_context),
    ]


def get_channel_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get channel-related tools with their executors."""
    return [
        create_get_channel_landscape_tool(filter_context),
        create_get_channel_assortment_tool(filter_context),
        create_get_channel_fair_share_tool(filter_context),
        create_get_channel_intensity_tool(filter_context),
        create_get_channel_transparency_brand_tool(filter_context),
        create_get_channel_transparency_retailer_tool(filter_context),
        create_get_channel_transparency_sku_tool(filter_context),
    ]


def get_pricing_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get pricing-related tools (consumer pricing, simulator, CDT, elasticity)."""
    return [
        create_get_brand_ladder_tool(filter_context),
        create_get_price_pack_curve_tool(filter_context),
        create_get_simulator_base_tool(filter_context),
        create_run_simulation_tool(filter_context),
        create_list_scenarios_tool(filter_context),
        create_create_scenario_tool(filter_context),
        create_get_scenario_tool(filter_context),
        create_delete_scenario_tool(filter_context),
        create_build_cdt_tool(filter_context),
        create_get_elasticities_tool(filter_context),
    ]


def get_pricing_data_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get pricing data tools with their executors."""
    return [
        create_get_brand_ladder_tool(filter_context),
        create_get_price_pack_curve_tool(filter_context),
    ]


def get_pricing_simulation_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get pricing simulation tools with their executors."""
    return [
        create_get_simulator_base_tool(filter_context),
        create_run_simulation_tool(filter_context),
        create_list_scenarios_tool(filter_context),
        create_create_scenario_tool(filter_context),
        create_get_scenario_tool(filter_context),
        create_delete_scenario_tool(filter_context),
        create_build_cdt_tool(filter_context),
        create_get_elasticities_tool(filter_context),
    ]


def get_promo_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get promo-related tools with their executors."""
    return [
        create_get_promo_calendar_tool(filter_context),
        create_get_promo_investment_trends_tool(filter_context),
        create_get_promo_heatmap_tool(filter_context),
        create_get_promo_event_scatter_tool(filter_context),
        create_get_promo_market_effectiveness_tool(filter_context),
        create_get_promo_tactic_effectiveness_tool(filter_context),
        create_get_promo_product_deep_dive_tool(filter_context),
        create_get_promo_discount_depth_qc_tool(filter_context),
        create_get_promo_planner_tool(filter_context),
        create_get_promo_baseline_review_tool(filter_context),
        create_get_promo_deep_dive_tactics_tool(filter_context),
    ]


def get_margin_tools(filter_context: FilterOptions) -> list[Tool]:
    """Get margin and trade-related tools with their executors."""
    return [
        create_get_price_spread_tool(filter_context),
        create_get_pricing_evolution_tool(filter_context),
        create_get_price_outliers_tool(filter_context),
        create_get_gtn_waterfall_tool(filter_context),
        create_get_investment_drivers_tool(filter_context),
        create_get_profit_pool_tool(filter_context),
        create_get_customer_contribution_tool(filter_context),
        create_get_portfolio_quadrant_tool(filter_context),
    ]


# =============================================================================
# Prompt Generation Utilities
# =============================================================================


def format_tools_for_prompt(tools: list[Tool], include_filter_tool: bool = True) -> str:
    """Generate a numbered tool list for agent prompts from Tool objects.

    This is the single source of truth — agent prompts should call this
    instead of manually listing tool descriptions.

    Args:
        tools: List of Tool objects (from get_category_tools(), etc.)
        include_filter_tool: Whether to include skai_get_filter_values in numbering.

    Returns:
        Formatted string like:
        0. **skai_get_filter_values**: Get available filter values ...
        1. **skai_get_category_landscape**: Category Landscape — returns ...
    """
    lines = []
    idx = 0
    for tool in tools:
        name = tool.definition.name
        desc = tool.definition.description
        if name == "skai_get_filter_values" and not include_filter_tool:
            continue
        lines.append(f"{idx}. **{name}**: {desc}")
        idx += 1
    return "\n\n".join(lines)


def format_agent_summary(agent_name: str, tools: list[Tool]) -> str:
    """Generate a concise summary of an agent's capabilities for the orchestrator.

    Args:
        agent_name: e.g. "category", "channel", "pricing", "promo", "margin"
        tools: The tools available to this agent.

    Returns:
        A one-line summary listing tool names (excluding filter tool).
    """
    tool_names = [
        t.definition.name
        for t in tools
        if t.definition.name != "skai_get_filter_values"
    ]
    return ", ".join(tool_names)


AGENT_TOOL_REGISTRY: dict[str, Callable[[FilterOptions], list[Tool]]] = {
    "category": get_category_tools,
    "channel": get_channel_tools,
    "pricing": get_pricing_tools,
    "promo": get_promo_tools,
    "margin": get_margin_tools,
    "pricing_data": get_pricing_data_tools,
    "pricing_simulation": get_pricing_simulation_tools,
}


def get_agent_tools_from_registry(
    filter_context: FilterOptions, domain: str
) -> list[Tool]:
    """Build agent tool registry with filter_context for schema enums."""
    return AGENT_TOOL_REGISTRY[domain](filter_context)


OrchestratorHandoffTool = generate_hand_back()
