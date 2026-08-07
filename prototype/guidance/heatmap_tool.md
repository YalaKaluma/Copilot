# `get_promo_heatmap`

Use this tool to retrieve a two-dimensional view of promotion performance.

Typical uses:

- Retailer × brand: compare efficiency and investment pockets.
- Retailer × SKU: locate granular strong and weak combinations.
- Discount depth × duration: compare promotional mechanics.
- Channel × brand: compare channel-level performance patterns.

Potential returned measures include investment, incremental gross profit, sales,
ROI, uplift and promotion-week counts. Their presence depends on the API response;
never assume every measure is populated.

The endpoint is appropriate for concentration and cross-sectional comparison. It
is not a substitute for calendar, event-ranking, trend, baseline-review or
simulation endpoints.

For an ideal or optimal discount-depth question, place `discount_depth` on one
axis and `retailer`, `brand`, or `duration` on the other. Keep `depth_bin` empty
unless the user explicitly requested particular brackets, so every available
depth band is returned. The application retries once with the axes swapped if
SKAI returns only an `unknown` depth bucket.
