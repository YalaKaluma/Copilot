from models.copilot.base import Tool
from models.skai_api_v2.filters import FilterOptions
from tools.skai_v2.promo import create_get_promo_heatmap_tool


def get_skai_promo_tools(
    filter_context: FilterOptions | None = None,
) -> list[Tool]:
    return [
        create_get_promo_heatmap_tool(filter_context),
    ]
