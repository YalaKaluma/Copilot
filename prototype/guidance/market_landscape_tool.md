# `get_market_landscape`

Use this tool for a broad fact base on market/category performance. It can
return market totals, entity sales-value share, year-over-year sales growth and
average price, grouped by a selected dimension.

Use it for questions such as:

- Which brands or subcategories are gaining or losing share?
- Which brand is growing fastest year over year?
- Where is category growth coming from?
- Is average price increasing, and is the market showing signs of premiumization?
- How does performance differ across the endpoint's supported product dimensions?

Available grouping values are `brand`, `category`, `sub_category`,
`manufacturer`, `segment`, `sub_segment`, `pack_size_range`, and `price_tier`.

Retailer is a filter rather than a grouping value. Cross-retailer comparisons
are supported by calling the endpoint once for each valid retailer group and
comparing the returned brand share, growth, or normalized price results.

Use `price_per_unit` for unit-price comparisons and
`price_per_scaled_volume` when different product sizes must be normalized.

Do not use this endpoint for promotion ROI, event effectiveness, seasonality,
price elasticity, causal explanations or simulations. A change in average price
may reflect price, mix, distribution or scope changes; do not label it
premiumization without supporting share/mix evidence.

When the user asks for the "fastest-growing brand" without specifying a growth
basis, use `split_by=brand` and rank the returned brands by year-over-year sales
growth. This is the default business interpretation and does not require a
clarifying question.

For brand whitespace, analyze several product cuts—category, subcategory,
segment, subsegment, pack-size range, and price tier where relevant—rather than
expecting one grouping to reveal the opportunity. Look for large or fast-growing
spaces in which the selected brand underperforms relative to its overall
position. Filtering by retailer may provide additional evidence about where the
gap is concentrated.
