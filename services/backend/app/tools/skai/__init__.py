"""SKAI tools package.

Provides Tool objects that combine ToolInput definitions with their
executor functions for seamless LLM function calling.

Usage:
    from tools.skai import get_category_tools, Tool
    from services.skai_api import SKAIApi

    # Get category tools
    tools = get_category_tools()

    # Use tool definition for LLM
    for tool in tools:
        print(tool.definition.model_dump())  # Schema for LLM

    # Execute a tool
    api = SKAIApi(base_url="...", api_key="...")
    result = await tools[0].execute(api, {"brands": "Brand A"})
"""

from .tools import (
    # Tool class
    # Filters
    create_get_filter_values_tool,
    # Category
    create_get_category_landscape_tool,
    create_get_category_trends_tool,
    create_get_category_format_overview_tool,
    create_get_category_price_tiers_tool,
    create_get_category_pack_sizes_tool,
    create_get_category_products_tool,
    create_get_category_seasonality_tool,
    create_get_category_innovation_tool,
    # Channel
    create_get_channel_landscape_tool,
    create_get_channel_assortment_tool,
    create_get_channel_fair_share_tool,
    create_get_channel_intensity_tool,
    create_get_channel_transparency_brand_tool,
    create_get_channel_transparency_retailer_tool,
    create_get_channel_transparency_sku_tool,
    # Consumer Pricing
    create_get_brand_ladder_tool,
    create_get_price_pack_curve_tool,
    # Simulator
    create_get_simulator_base_tool,
    create_run_simulation_tool,
    create_list_scenarios_tool,
    create_create_scenario_tool,
    create_get_scenario_tool,
    create_delete_scenario_tool,
    # CDT
    create_build_cdt_tool,
    # Elasticity
    create_get_elasticities_tool,
    # Promo
    create_get_promo_calendar_tool,
    create_get_promo_investment_trends_tool,
    create_get_promo_heatmap_tool,
    create_get_promo_event_scatter_tool,
    create_get_promo_market_effectiveness_tool,
    create_get_promo_tactic_effectiveness_tool,
    create_get_promo_product_deep_dive_tool,
    create_get_promo_discount_depth_qc_tool,
    create_get_promo_planner_tool,
    create_get_promo_baseline_review_tool,
    create_get_promo_deep_dive_tactics_tool,
    # Net Pricing / B2B
    create_get_price_spread_tool,
    create_get_pricing_evolution_tool,
    create_get_price_outliers_tool,
    # Trade
    create_get_gtn_waterfall_tool,
    create_get_investment_drivers_tool,
    # Margin
    create_get_profit_pool_tool,
    create_get_customer_contribution_tool,
    create_get_portfolio_quadrant_tool,
    # Downloads
    create_download_tool,
    # Utility - Get tool groups
    get_all_skai_tools,
    get_category_tools,
    get_channel_tools,
    get_pricing_tools,
    get_promo_tools,
    get_margin_tools,
)
from models.copilot.base import Tool

__all__ = [
    # Tool class
    "Tool",
    # Filters
    "create_get_filter_values_tool",
    # Category
    "create_get_category_landscape_tool",
    "create_get_category_trends_tool",
    "create_get_category_format_overview_tool",
    "create_get_category_price_tiers_tool",
    "create_get_category_pack_sizes_tool",
    "create_get_category_products_tool",
    "create_get_category_seasonality_tool",
    "create_get_category_innovation_tool",
    # Channel
    "create_get_channel_landscape_tool",
    "create_get_channel_assortment_tool",
    "create_get_channel_fair_share_tool",
    "create_get_channel_intensity_tool",
    "create_get_channel_transparency_brand_tool",
    "create_get_channel_transparency_retailer_tool",
    "create_get_channel_transparency_sku_tool",
    # Consumer Pricing
    "create_get_brand_ladder_tool",
    "create_get_price_pack_curve_tool",
    # Simulator
    "create_get_simulator_base_tool",
    "create_run_simulation_tool",
    "create_list_scenarios_tool",
    "create_create_scenario_tool",
    "create_get_scenario_tool",
    "create_delete_scenario_tool",
    # CDT
    "create_build_cdt_tool",
    # Elasticity
    "create_get_elasticities_tool",
    # Promo
    "create_get_promo_calendar_tool",
    "create_get_promo_investment_trends_tool",
    "create_get_promo_heatmap_tool",
    "create_get_promo_event_scatter_tool",
    "create_get_promo_market_effectiveness_tool",
    "create_get_promo_tactic_effectiveness_tool",
    "create_get_promo_product_deep_dive_tool",
    "create_get_promo_discount_depth_qc_tool",
    "create_get_promo_planner_tool",
    "create_get_promo_baseline_review_tool",
    "create_get_promo_deep_dive_tactics_tool",
    # Net Pricing / B2B
    "create_get_price_spread_tool",
    "create_get_pricing_evolution_tool",
    "create_get_price_outliers_tool",
    # Trade
    "create_get_gtn_waterfall_tool",
    "create_get_investment_drivers_tool",
    # Margin
    "create_get_profit_pool_tool",
    "create_get_customer_contribution_tool",
    "create_get_portfolio_quadrant_tool",
    # Downloads
    "create_download_tool",
    # Utility - Get tool groups
    "get_all_skai_tools",
    "get_category_tools",
    "get_channel_tools",
    "get_pricing_tools",
    "get_promo_tools",
    "get_margin_tools",
]
