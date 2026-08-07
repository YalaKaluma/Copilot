# SKAI pricing ladder and simulator

`get_price_ladder` calls `GET /api/v1/pricing/brand-ladder`. It supports brand,
subcategory, retailer, and SKU filters and returns brand prices, volume, sales,
and sales-value share.

`get_simulator_base` calls `GET /api/v1/pricing/simulator/base`. Use it to inspect
available simulator products and current prices.

`run_price_simulation` first retrieves simulator base data and then calls
`POST /api/v1/pricing/simulator/run`. Provide `price_change_pct` for a relative
change across the selected SKU scope, or `new_price` for one explicitly selected
SKU. Simulation outputs are projections driven by elasticity and volume-transfer
assumptions; they are not guaranteed forecasts.
