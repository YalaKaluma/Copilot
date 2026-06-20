from models.skai_api.autogen import FilterValuesResponse as FilterValuesResponseV1
from models.skai_api_v2.filters import FilterValuesResponse as FilterValuesResponseV2

# -------------------------------------------------------------------
# FILTER CONTEXT HELPER
# -------------------------------------------------------------------


def format_filter_context(
    filter_values: FilterValuesResponseV1 | FilterValuesResponseV2,
) -> str:
    """Format filter values into a concise context string.

    Args:
        filter_values: Filter values response from SKAI API

    Returns:
        Formatted string for prompt injection
    """
    parts = []
    filters = filter_values.filters

    if super_categories := getattr(filters, "super_categories", None):
        parts.append(f"**Super Categories**: {', '.join(super_categories)}")

    if brands := filters.brands:
        brand_list = brands[:20]
        brand_str = ", ".join(brand_list)
        if len(brands) > 20:
            brand_str += f" ... and {len(brands) - 20} more"
        parts.append(f"**Brands** ({len(brands)} total): {brand_str}")

    if categories := filters.categories:
        parts.append(f"**Categories**: {', '.join(categories)}")

    if subcategories := filters.subcategories:
        subcat_list = subcategories[:15]
        subcat_str = ", ".join(subcat_list)
        if len(subcategories) > 15:
            subcat_str += f" ... and {len(subcategories) - 15} more"
        parts.append(f"**Subcategories** ({len(subcategories)} total): {subcat_str}")

    if retailers := filters.retailers:
        parts.append(f"**Retailers**: {', '.join(retailers)}")

    if channels := filters.channels:
        parts.append(f"**Channels**: {', '.join(channels)}")

    if price_tiers := filters.price_tiers:
        parts.append(f"**Price Tiers**: {', '.join(price_tiers)}")

    return "\n".join(parts) if parts else "No filter data available."
