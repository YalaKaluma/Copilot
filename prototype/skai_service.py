"""Small, synchronous client for the SKAI Growth API surface used by the prototype."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx


class SkaiError(RuntimeError):
    """A user-readable error returned by SKAI."""


@dataclass
class SkaiGrowthService:
    base_url: str
    market_base_url: str | None = None
    tenant_code: str | None = None
    token: str | None = None
    api_key: str | None = None
    origin: str | None = None
    referer: str | None = None
    timeout: float = 45.0
    _client: httpx.Client = field(init=False, repr=False)
    _market_client: httpx.Client = field(init=False, repr=False)
    _response_cache: dict[str, dict[str, Any]] = field(
        init=False, repr=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        if self.origin:
            headers["Origin"] = self.origin
        if self.referer:
            headers["Referer"] = self.referer
        if self.tenant_code:
            headers["X-Tenant-Code"] = self.tenant_code
        self._client = httpx.Client(
            base_url=self.base_url.rstrip("/"),
            headers=headers,
            timeout=self.timeout,
        )
        self._market_client = httpx.Client(
            base_url=(self.market_base_url or self.base_url).rstrip("/"),
            headers=headers,
            timeout=self.timeout,
        )

    def close(self) -> None:
        self._client.close()
        self._market_client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        market_api: bool = False,
    ) -> dict[str, Any]:
        try:
            client = self._market_client if market_api else self._client
            response = client.request(
                method,
                path,
                params=params,
                json=json_body,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise SkaiError("SKAI returned an unexpected response.")
            return payload
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise SkaiError(
                f"SKAI returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except (httpx.RequestError, ValueError) as exc:
            raise SkaiError(f"Could not call SKAI: {exc}") from exc

    def get_filter_values(self) -> dict[str, Any]:
        """Return valid brands, categories, retailers, channels, and other filters."""
        return self._request("GET", "/api/v1/filter-values")

    def get_promo_heatmap(self, **filters: Any) -> dict[str, Any]:
        """Return promo performance for two selected dimensions."""
        params = {
            key: value
            for key, value in filters.items()
            if value is not None and value != [] and value != ""
        }
        return self._request("GET", "/api/v1/promo/heatmap", params=params)

    def get_market_landscape(self, **filters: Any) -> dict[str, Any]:
        """Return market/category size, share, growth and price positioning."""
        if "split_by" in filters:
            filters["x_dimension"] = filters.pop("split_by")
        if "retailers" in filters:
            filters["retailer_groups"] = filters.pop("retailers")
        price_metric = filters.pop("price_metric", None)
        if price_metric:
            filters["unit_mode"] = (
                "per_kg"
                if price_metric == "price_per_scaled_volume"
                else "per_pack"
            )
        params = {
            key: value
            for key, value in filters.items()
            if value is not None and value != [] and value != ""
        }
        return self._cached_pricing_get(
            "/api/v1/pricing/market-landscape", params
        )

    def get_price_ladder(self, **filters: Any) -> dict[str, Any]:
        """Return brand price positioning, share, sales, and volume."""
        params = {
            key: value
            for key, value in filters.items()
            if value is not None and value != [] and value != ""
        }
        return self._cached_pricing_get("/api/v1/pricing/price-ladder", params)

    def get_price_pack_curve(self, **filters: Any) -> dict[str, Any]:
        """Return pack-size price architecture, gaps, and competitive clusters."""
        params = {
            key: value
            for key, value in filters.items()
            if value is not None and value != [] and value != ""
        }
        return self._cached_pricing_get(
            "/api/v1/pricing/price-pack-curve", params
        )

    def _cached_pricing_get(
        self, path: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Reuse identical read-only pricing evidence during a perimeter scan."""
        cache_key = f"{path}:{json.dumps(params, sort_keys=True, default=str)}"
        if cache_key not in self._response_cache:
            self._response_cache[cache_key] = self._request(
                "GET", path, params=params, market_api=True
            )
        return self._response_cache[cache_key]

    def get_simulator_base(self, **filters: Any) -> dict[str, Any]:
        """Return the SKU/product IDs and current values required to simulate."""
        if "retailers" in filters:
            filters["retailer_groups"] = filters.pop("retailers")
        params = {
            key: value
            for key, value in filters.items()
            if value is not None and value != [] and value != ""
        }
        return self._request(
            "GET",
            "/api/v1/pricing/simulator/base",
            params=params,
            market_api=True,
        )

    def run_price_simulation(
        self, payload: dict[str, Any], **filters: Any
    ) -> dict[str, Any]:
        """Run a pricing scenario using product IDs resolved from base data."""
        if "retailers" in filters:
            filters["retailer_groups"] = filters.pop("retailers")
        params = {
            key: value
            for key, value in filters.items()
            if value is not None and value != [] and value != ""
        }
        return self._request(
            "POST",
            "/api/v1/pricing/simulator/run",
            params=params,
            json_body=payload,
            market_api=True,
        )
