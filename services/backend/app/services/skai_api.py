"""SKAI API service for interacting with the SKAI analytics platform.

This service provides typed async methods for all SKAI API endpoints,
handling authentication, request serialization, and response parsing.

Usage:
    from services.skai_api import SKAIApi, get_skai_api

    # In a router with dependency injection
    @router.get("/data")
    async def get_data(skai: SKAIApiDep):
        response = await skai.get_category_landscape(request)
        return response

    # Or create directly
    api = SKAIApi(base_url="https://api.skai.example.com", api_key="...")
    response = await api.health()
"""

from functools import lru_cache
from async_lru import alru_cache
from typing import Annotated, Any, TypeVar
from urllib.parse import quote_plus, urlencode

import httpx
from fastapi import Depends
from pydantic import BaseModel

from core.config import get_settings
from core.logging import get_logger

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
    EventScatterResponsePatched,
    HeatmapRequest,
    MarketEffectivenessRequest,
    PricePackCurveRequest,
    ProductDeepDiveRequest,
    PromoCalendarResponsePatched,
    PromoPlannerRequest,
    PromoRequest,
    ScenarioCreateResponse,
    ScenarioListRequest,
    SimulatorBaseRequest,
    TacticEffectivenessRequest,
)
from models.skai_api import autogen as skai_api_models
from schemas.base import CamelCaseModel

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class SKAIApiError(Exception):
    """Exception raised for SKAI API errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: dict | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class SKAIApi:
    """Async client for the SKAI analytics API.

    Provides typed methods for all SKAI API endpoints with automatic
    request serialization and response parsing.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        auth_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        """Initialize the SKAI API client.

        Args:
            base_url: Base URL for the SKAI API (e.g., "https://api.skai.example.com")
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            auth_token: Optional bearer token for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_token = auth_token
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            headers = dict(self.extra_headers)
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "SKAIApi":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    def _serialize_params(
        self, request: CamelCaseModel | None = None
    ) -> dict[str, Any]:
        """Serialize a request model to query parameters.

        Handles date serialization and list parameters. Omits empty lists
        so the API is not given empty filter params (which can return no data).
        """
        if request is None:
            return {}

        params: dict[str, Any] = {}
        for key, value in request.model_dump(exclude_none=True, mode="json").items():
            if isinstance(value, list):
                # Skip empty lists - API may treat empty filter as "match nothing"
                if not value:
                    continue
                # Keep list to serialize as repeated query params
                params[key] = [str(v) for v in value]
            else:
                params[key] = value
        return params

    async def _request(
        self,
        method: str,
        path: str,
        response_model: type[T],
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> T:
        """Make an API request and parse the response.

        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            path: API path (e.g., "/api/v1/health")
            response_model: Pydantic model to parse response into
            params: Optional query parameters
            json_body: Optional JSON body for POST/PATCH requests

        Returns:
            Parsed response model

        Raises:
            SKAIApiError: If the request fails
        """
        client = await self._get_client()

        # Build query string with + for spaces (application/x-www-form-urlencoded)
        # so APIs that expect + rather than %20 work correctly.
        url = path
        if params:
            serialized_params: dict[str, Any] = {}
            for key, value in params.items():
                if isinstance(value, list):
                    serialized_params[key] = [str(v) for v in value]
                else:
                    serialized_params[key] = str(value)
            query_string = urlencode(
                serialized_params,
                doseq=True,
                quote_via=quote_plus,
            )
            url = f"{path}?{query_string}"
            params = None

        try:
            logger.debug("SKAI API %s %s", method, url)
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
            )
            logger.debug("SKAI API %s %s -> %s", method, url, response.status_code)
            response.raise_for_status()
            return response_model.model_validate(response.json())

        except httpx.HTTPStatusError as e:
            error_body = None
            try:
                error_body = e.response.json()
            except Exception:
                pass
            logger.error(
                f"SKAI API error: {e.response.status_code} - {e.response.text}"
            )
            raise SKAIApiError(
                message=f"SKAI API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
                response_body=error_body,
            ) from e
        except httpx.RequestError as e:
            logger.error(f"SKAI API request error: {e}")
            raise SKAIApiError(f"SKAI API request failed: {e}") from e

    async def _request_bytes(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> bytes:
        """Make an API request and return raw bytes (for file downloads).

        Args:
            method: HTTP method
            path: API path
            params: Optional query parameters
            json_body: Optional JSON body

        Returns:
            Raw response bytes

        Raises:
            SKAIApiError: If the request fails
        """
        client = await self._get_client()

        # Build query string with + for spaces (application/x-www-form-urlencoded)
        url = path
        if params:
            query_string = urlencode(
                {k: str(v) for k, v in params.items()},
                quote_via=quote_plus,
            )
            url = f"{path}?{query_string}"
            params = None

        try:
            response = await client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
            )
            response.raise_for_status()
            return response.content

        except httpx.HTTPStatusError as e:
            logger.error(
                f"SKAI API error: {e.response.status_code} - {e.response.text}"
            )
            raise SKAIApiError(
                message=f"SKAI API request failed: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            logger.error(f"SKAI API request error: {e}")
            raise SKAIApiError(f"SKAI API request failed: {e}") from e

    # =========================================================================
    # Health Endpoint
    # =========================================================================

    async def health(self) -> skai_api_models.HealthResponse:
        """Check API health status.

        GET /api/v1/health
        """
        return await self._request(
            "GET", "/api/v1/health", skai_api_models.HealthResponse
        )

    # =========================================================================
    # Config Endpoints
    # =========================================================================

    async def get_config(self, category: str) -> skai_api_models.ConfigResponse:
        """Get configuration for a category.

        GET /api/v1/config/{category}

        Args:
            category: Configuration category to retrieve
        """
        return await self._request(
            "GET", f"/api/v1/config/{category}", skai_api_models.ConfigResponse
        )

    async def patch_config(
        self, category: str, request: dict[str, Any]
    ) -> skai_api_models.ConfigResponse:
        """Update configuration for a category.

        PATCH /api/v1/config/{category}

        Args:
            category: Configuration category to update
            request: Configuration patch request
        """
        return await self._request(
            "PATCH",
            f"/api/v1/config/{category}",
            skai_api_models.ConfigResponse,
            json_body=request,
        )

    # =========================================================================
    # Admin Endpoints
    # =========================================================================

    async def seed_config(self) -> skai_api_models.SeedResponse:
        """Seed configuration data.

        POST /api/v1/admin/config/seed
        """
        return await self._request(
            "POST", "/api/v1/admin/config/seed", skai_api_models.SeedResponse
        )

    # =========================================================================
    # Filter Endpoints
    # =========================================================================

    async def get_filter_values(self) -> skai_api_models.FilterValuesResponse:
        """Get available filter values for analytics.

        GET /api/v1/filter-values
        """
        return await self._request(
            "GET",
            "/api/v1/filter-values",
            skai_api_models.FilterValuesResponse,
        )

    async def get_filter_values_related(
        self, request: skai_api_models.RelatedFiltersRequest
    ) -> skai_api_models.FilterValuesResponse:
        """Get available filter values for analytics.

        POST /api/v1/filter-values/related

        Args:
            request: Optional filter request parameters
        """
        return await self._request(
            "POST",
            "/api/v1/filter-values/related",
            skai_api_models.FilterValuesResponse,
            json_body=request.model_dump(exclude_none=True, mode="json"),
        )

    # =========================================================================
    # Category Endpoints
    # =========================================================================

    async def get_category_landscape(
        self, request: skai_api_models.CategoryLandscapeRequest
    ) -> skai_api_models.CategoryLandscapeResponse:
        """Get Category Landscape analytics.

        GET /api/v1/category/landscape

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/landscape",
            skai_api_models.CategoryLandscapeResponse,
            params=self._serialize_params(request),
        )

    async def get_category_trends(
        self, request: skai_api_models.CategoryTrendsRequest
    ) -> skai_api_models.CategoryTrendsResponse:
        """Get Category Trends analytics.

        GET /api/v1/category/trends

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/trends",
            skai_api_models.CategoryTrendsResponse,
            params=self._serialize_params(request),
        )

    async def get_category_format_overview(
        self, request: skai_api_models.CategoryFormatRequest
    ) -> skai_api_models.CategoryFormatResponse:
        """Get Category Format Overview analytics.

        GET /api/v1/category/format-overview

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/format-overview",
            skai_api_models.CategoryFormatResponse,
            params=self._serialize_params(request),
        )

    async def get_category_price_tiers(
        self, request: skai_api_models.CategoryPriceTiersRequest
    ) -> skai_api_models.CategoryPriceTiersResponse:
        """Get Category Price Tiers analytics.

        GET /api/v1/category/price-tiers

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/price-tiers",
            skai_api_models.CategoryPriceTiersResponse,
            params=self._serialize_params(request),
        )

    async def get_category_pack_sizes(
        self, request: skai_api_models.CategoryPackSizeRequest
    ) -> skai_api_models.CategoryPackSizeResponse:
        """Get Category Pack Size Overview.

        GET /api/v1/category/pack-sizes

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/pack-sizes",
            skai_api_models.CategoryPackSizeResponse,
            params=self._serialize_params(request),
        )

    async def get_category_products(
        self, request: skai_api_models.CategoryProductRequest
    ) -> skai_api_models.CategoryProductResponse:
        """Get Category Product Landscape.

        GET /api/v1/category/products

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/products",
            skai_api_models.CategoryProductResponse,
            params=self._serialize_params(request),
        )

    async def get_category_seasonality(
        self, request: skai_api_models.CategorySeasonalityRequest
    ) -> skai_api_models.CategorySeasonalityResponse:
        """Get Category Seasonality analytics.

        GET /api/v1/category/seasonality

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/seasonality",
            skai_api_models.CategorySeasonalityResponse,
            params=self._serialize_params(request),
        )

    async def get_category_innovation(
        self, request: skai_api_models.CategoryInnovationRequest
    ) -> skai_api_models.CategoryInnovationResponse:
        """Get Innovation & Discontinuation Tracking.

        GET /api/v1/category/innovation

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/category/innovation",
            skai_api_models.CategoryInnovationResponse,
            params=self._serialize_params(request),
        )

    # =========================================================================
    # Channel Endpoints
    # =========================================================================

    async def get_channel_landscape(
        self, request: skai_api_models.ChannelLandscapeRequest
    ) -> skai_api_models.ChannelLandscapeResponse:
        """Get Channel Landscape analytics.

        GET /api/v1/channel/landscape

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/channel/landscape",
            skai_api_models.ChannelLandscapeResponse,
            params=self._serialize_params(request),
        )

    async def get_channel_assortment(
        self, request: AssortmentRequest
    ) -> skai_api_models.AssortmentResponse:
        """Get Assortment Overview.

        GET /api/v1/channel/assortment

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/channel/assortment",
            skai_api_models.AssortmentResponse,
            params=self._serialize_params(request),
        )

    async def get_channel_fair_share(
        self, request: ChannelFairShareRequest
    ) -> skai_api_models.FairShareResponse:
        """Get Promo Fair Share.

        GET /api/v1/channel/fair-share

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/channel/fair-share",
            skai_api_models.FairShareResponse,
            params=self._serialize_params(request),
        )

    async def get_channel_intensity(
        self, request: ChannelIntensityRequest
    ) -> skai_api_models.IntensityResponse:
        """Get Promo Intensity.

        GET /api/v1/channel/intensity

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/channel/intensity",
            skai_api_models.IntensityResponse,
            params=self._serialize_params(request),
        )

    async def get_channel_transparency_brand(
        self, request: ChannelTransparencyRequest
    ) -> skai_api_models.TransparencyResponse:
        """Get Brand Transparency.

        GET /api/v1/channel/transparency/brand

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/channel/transparency/brand",
            skai_api_models.TransparencyResponse,
            params=self._serialize_params(request),
        )

    async def get_channel_transparency_retailer(
        self, request: ChannelTransparencyRequest
    ) -> skai_api_models.TransparencyResponse:
        """Get Retailer Transparency.

        GET /api/v1/channel/transparency/retailer

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/channel/transparency/retailer",
            skai_api_models.TransparencyResponse,
            params=self._serialize_params(request),
        )

    async def get_channel_transparency_sku(
        self, request: ChannelTransparencyRequest
    ) -> skai_api_models.TransparencyResponse:
        """Get SKU Transparency.

        GET /api/v1/channel/transparency/sku

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/channel/transparency/sku",
            skai_api_models.TransparencyResponse,
            params=self._serialize_params(request),
        )

    # =========================================================================
    # Consumer Pricing Endpoints
    # =========================================================================

    async def get_brand_ladder(
        self, request: BrandLadderRequest
    ) -> skai_api_models.BrandLadderResponse:
        """Get Brand Ladder pricing analysis.

        GET /api/v1/pricing/brand-ladder

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/pricing/brand-ladder",
            skai_api_models.BrandLadderResponse,
            params=self._serialize_params(request),
        )

    async def get_price_pack_curve(
        self, request: PricePackCurveRequest
    ) -> skai_api_models.PricePackResponse:
        """Get Price Pack Curve analysis.

        GET /api/v1/pricing/price-pack-curve

        Args:
            request: Filter and analysis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/pricing/price-pack-curve",
            skai_api_models.PricePackResponse,
            params=self._serialize_params(request),
        )

    # =========================================================================
    # Simulator Endpoints
    # =========================================================================

    async def get_simulator_base(
        self, request: SimulatorBaseRequest
    ) -> skai_api_models.SimulatorRunResponse:
        """Get SKU base data for simulator.

        GET /api/v1/pricing/simulator/base

        Args:
            request: Filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/pricing/simulator/base",
            skai_api_models.SimulatorRunResponse,
            params=self._serialize_params(request),
        )

    async def run_simulation(
        self, request: skai_api_models.SimulatorRunRequest
    ) -> skai_api_models.SimulatorRunResponse:
        """Run pricing simulation.

        POST /api/v1/pricing/simulator/run

        Args:
            request: Simulation configuration and price changes
        """
        return await self._request(
            "POST",
            "/api/v1/pricing/simulator/run",
            skai_api_models.SimulatorRunResponse,
            json_body=request.model_dump(exclude_none=True, mode="json"),
        )

    async def list_scenarios(
        self, request: ScenarioListRequest
    ) -> skai_api_models.ScenarioListResponse:
        """List saved scenarios.

        GET /api/v1/pricing/simulator/scenarios

        Args:
            request: Filter and pagination parameters
        """
        return await self._request(
            "GET",
            "/api/v1/pricing/simulator/scenarios",
            skai_api_models.ScenarioListResponse,
            params=self._serialize_params(request),
        )

    async def create_scenario(
        self, request: skai_api_models.ScenarioCreate
    ) -> ScenarioCreateResponse:
        """Create a new scenario.

        POST /api/v1/pricing/simulator/scenarios

        Args:
            request: Scenario creation data
        """
        return await self._request(
            "POST",
            "/api/v1/pricing/simulator/scenarios",
            ScenarioCreateResponse,
            json_body=request.model_dump(exclude_none=True, mode="json"),
        )

    async def get_scenario(self, scenario_id: int) -> skai_api_models.ScenarioDetail:
        """Get a scenario by ID.

        GET /api/v1/pricing/simulator/scenarios/{scenario_id}

        Args:
            scenario_id: ID of the scenario to retrieve
        """
        return await self._request(
            "GET",
            f"/api/v1/pricing/simulator/scenarios/{scenario_id}",
            skai_api_models.ScenarioDetail,
        )

    async def delete_scenario(self, scenario_id: int) -> None:
        """Delete a scenario.

        DELETE /api/v1/pricing/simulator/scenarios/{scenario_id}

        Args:
            scenario_id: ID of the scenario to delete
        """
        client = await self._get_client()
        try:
            response = await client.delete(
                f"/api/v1/pricing/simulator/scenarios/{scenario_id}"
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise SKAIApiError(
                message=f"Failed to delete scenario: {e.response.status_code}",
                status_code=e.response.status_code,
            ) from e

    # =========================================================================
    # CDT Endpoints
    # =========================================================================

    async def build_cdt(
        self, request: skai_api_models.CDTRequest
    ) -> skai_api_models.CDTResponse:
        """Build Consumer Decision Tree.

        POST /api/v1/pricing/cdt/build

        Args:
            request: CDT configuration and filters
        """
        return await self._request(
            "POST",
            "/api/v1/pricing/cdt/build",
            skai_api_models.CDTResponse,
            json_body=request.model_dump(exclude_none=True, mode="json"),
        )

    # =========================================================================
    # Elasticity Endpoints
    # =========================================================================

    async def get_elasticities(
        self, request: skai_api_models.ElasticityRequest
    ) -> skai_api_models.ElasticityResponse:
        """Get Price Elasticities.

        POST /api/v1/pricing/elasticity

        Args:
            request: Elasticity calculation parameters
        """
        return await self._request(
            "POST",
            "/api/v1/pricing/elasticity",
            skai_api_models.ElasticityResponse,
            json_body=request.model_dump(exclude_none=True),
        )

    # =========================================================================
    # Promo Endpoints
    # =========================================================================

    async def get_promo_calendar(
        self, request: PromoRequest
    ) -> PromoCalendarResponsePatched:
        """Get Promo Calendar.

        GET /api/v1/promo/calendar

        Args:
            request: Filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/calendar",
            PromoCalendarResponsePatched,
            params=self._serialize_params(request),
        )

    async def get_promo_investment_trends(
        self, request: PromoRequest
    ) -> skai_api_models.PromoInvestmentResponse:
        """Get Promo Investment Trends.

        GET /api/v1/promo/investment-trends

        Args:
            request: Filter and grouping parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/investment-trends",
            skai_api_models.PromoInvestmentResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_heatmap(
        self, request: HeatmapRequest
    ) -> skai_api_models.HeatmapResponse:
        """Get Promo Heatmap.

        GET /api/v1/promo/heatmap

        Args:
            request: Filter and axis parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/heatmap",
            skai_api_models.HeatmapResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_event_scatter(
        self, request: EventScatterRequest
    ) -> EventScatterResponsePatched:
        """Get Event Scatter (ROI vs Depth).

        GET /api/v1/promo/event-scatter

        Args:
            request: Filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/event-scatter",
            EventScatterResponsePatched,
            params=self._serialize_params(request),
        )

    async def get_promo_market_effectiveness(
        self, request: MarketEffectivenessRequest
    ) -> skai_api_models.MarketEffectivenessResponse:
        """Get Market Effectiveness (Investment vs Return by brand/retailer).

        GET /api/v1/promo/market-effectiveness

        Args:
            request: Filter and grouping parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/market-effectiveness",
            skai_api_models.MarketEffectivenessResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_tactic_effectiveness(
        self, request: TacticEffectivenessRequest
    ) -> skai_api_models.TacticEffectivenessResponse:
        """Get Tactic Effectiveness (ROI per tactic type).

        GET /api/v1/promo/tactic-effectiveness

        Args:
            request: Filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/tactic-effectiveness",
            skai_api_models.TacticEffectivenessResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_product_deep_dive(
        self, request: ProductDeepDiveRequest
    ) -> skai_api_models.ProductDeepDiveResponse:
        """Get Product Deep-Dive (SKU-level promo history).

        GET /api/v1/promo/product-deep-dive

        Args:
            request: SKU and filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/product-deep-dive",
            skai_api_models.ProductDeepDiveResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_discount_depth_qc(
        self, request: DiscountDepthQCRequest
    ) -> skai_api_models.DiscountDepthQCResponse:
        """Get Discount Depth QC (ROI by discount decile).

        GET /api/v1/promo/discount-depth-qc

        Args:
            request: Filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/discount-depth-qc",
            skai_api_models.DiscountDepthQCResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_planner(
        self, request: PromoPlannerRequest
    ) -> skai_api_models.PromoPlannerResponse:
        """Get Promo Planner (SKU-level recommendations).

        GET /api/v1/promo/planner

        Args:
            request: SKU and filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/planner",
            skai_api_models.PromoPlannerResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_baseline_review(
        self, request: BaselineReviewRequest
    ) -> skai_api_models.BaselineReviewResponse:
        """Get Baseline Review (Weekly volume decomposition for SKU-retailer).

        GET /api/v1/promo/product-deep-dive/baseline

        Args:
            request: SKU and retailer parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/product-deep-dive/baseline",
            skai_api_models.BaselineReviewResponse,
            params=self._serialize_params(request),
        )

    async def get_promo_deep_dive_tactics(
        self, request: DeepDiveTacticRequest
    ) -> skai_api_models.DeepDiveTacticResponse:
        """Get Tactic Effectiveness for deep dive (Performance by depth/duration/timing).

        GET /api/v1/promo/product-deep-dive/tactics

        Args:
            request: SKU, retailer, and grouping parameters
        """
        return await self._request(
            "GET",
            "/api/v1/promo/product-deep-dive/tactics",
            skai_api_models.DeepDiveTacticResponse,
            params=self._serialize_params(request),
        )

    # =========================================================================
    # Net Pricing / B2B Endpoints
    # =========================================================================

    async def get_price_spread(
        self, request: skai_api_models.PriceSpreadRequest
    ) -> skai_api_models.PriceSpreadResponse:
        """Get Cross-Customer Price Spread.

        GET /api/v1/b2b/price-spread

        Args:
            request: Filter and grouping parameters
        """
        return await self._request(
            "GET",
            "/api/v1/b2b/price-spread",
            skai_api_models.PriceSpreadResponse,
            params=self._serialize_params(request),
        )

    async def get_pricing_evolution(
        self, request: skai_api_models.PricingEvolutionRequest
    ) -> skai_api_models.PricingEvolutionResponse:
        """Get Customer Pricing Evolution.

        GET /api/v1/b2b/pricing-evolution

        Args:
            request: Filter and grouping parameters
        """
        return await self._request(
            "GET",
            "/api/v1/b2b/pricing-evolution",
            skai_api_models.PricingEvolutionResponse,
            params=self._serialize_params(request),
        )

    async def get_price_outliers(
        self, request: skai_api_models.PriceOutlierRequest
    ) -> skai_api_models.PriceOutlierResponse:
        """Get Price Outliers Detection.

        GET /api/v1/b2b/price-outliers

        Args:
            request: Filter and detection parameters
        """
        return await self._request(
            "GET",
            "/api/v1/b2b/price-outliers",
            skai_api_models.PriceOutlierResponse,
            params=self._serialize_params(request),
        )

    # =========================================================================
    # Trade Endpoints
    # =========================================================================

    async def get_gtn_waterfall(
        self, request: skai_api_models.GTNWaterfallRequest
    ) -> skai_api_models.GTNWaterfallResponse:
        """Get Gross-to-Net Waterfall.

        GET /api/v1/trade/gtn-waterfall

        Args:
            request: Filter and grouping parameters
        """
        return await self._request(
            "GET",
            "/api/v1/trade/gtn-waterfall",
            skai_api_models.GTNWaterfallResponse,
            params=self._serialize_params(request),
        )

    async def get_investment_drivers(
        self, request: skai_api_models.InvestmentDriverRequest
    ) -> skai_api_models.InvestmentDriverResponse:
        """Get Trade Investment Drivers.

        GET /api/v1/trade/investment-drivers

        Args:
            request: Filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/trade/investment-drivers",
            skai_api_models.InvestmentDriverResponse,
            params=self._serialize_params(request),
        )

    # =========================================================================
    # Margin Endpoints
    # =========================================================================

    async def get_profit_pool(
        self, request: skai_api_models.ProfitPoolRequest
    ) -> skai_api_models.ProfitPoolResponse:
        """Get Margin Pool Analysis.

        GET /api/v1/margin/profit-pool

        Args:
            request: Filter and segmentation parameters
        """
        return await self._request(
            "GET",
            "/api/v1/margin/profit-pool",
            skai_api_models.ProfitPoolResponse,
            params=self._serialize_params(request),
        )

    async def get_customer_contribution(
        self, request: skai_api_models.MarginContributionRequest
    ) -> skai_api_models.MarginContributionResponse:
        """Get Customer Margin Contribution.

        GET /api/v1/margin/customer-contribution

        Args:
            request: Filter parameters
        """
        return await self._request(
            "GET",
            "/api/v1/margin/customer-contribution",
            skai_api_models.MarginContributionResponse,
            params=self._serialize_params(request),
        )

    async def get_portfolio_quadrant(
        self, request: skai_api_models.PortfolioQuadrantRequest
    ) -> skai_api_models.PortfolioQuadrantResponse:
        """Get Portfolio Margin & Growth Quadrant.

        GET /api/v1/margin/portfolio-quadrant

        Args:
            request: Filter and threshold parameters
        """
        return await self._request(
            "GET",
            "/api/v1/margin/portfolio-quadrant",
            skai_api_models.PortfolioQuadrantResponse,
            params=self._serialize_params(request),
        )

    # =========================================================================
    # Downloads Endpoint
    # =========================================================================

    async def download(self, request: skai_api_models.DownloadRequest) -> bytes:
        """Download data as file.

        POST /api/v1/downloads

        Args:
            request: Download configuration with sheet data

        Returns:
            Raw file bytes (xlsx format)
        """
        return await self._request_bytes(
            "POST",
            "/api/v1/downloads",
            json_body=request.model_dump(exclude_none=True, mode="json"),
        )


# =============================================================================
# Dependency Injection
# =============================================================================


@lru_cache(maxsize=1)
def _get_skai_settings() -> tuple[str, str | None, str | None, dict[str, str]]:
    """Get SKAI API settings. Cached for performance."""
    settings = get_settings()
    base_url = settings.skai_api_url
    api_key = settings.skai_api_key
    auth_token = settings.skai_token
    extra_headers: dict[str, str] = {}
    if settings.skai_api_origin:
        extra_headers["Origin"] = settings.skai_api_origin
    if settings.skai_api_referer:
        extra_headers["Referer"] = settings.skai_api_referer
    if settings.skai_api_user_agent:
        extra_headers["User-Agent"] = settings.skai_api_user_agent
    return base_url, api_key, auth_token, extra_headers


def get_skai_api() -> SKAIApi:
    """Get SKAI API instance for dependency injection.

    Returns:
        SKAIApi instance configured from settings
    """
    base_url, api_key, auth_token, extra_headers = _get_skai_settings()
    return SKAIApi(
        base_url=base_url,
        api_key=api_key,
        auth_token=auth_token,
        extra_headers=extra_headers,
    )


# Type alias for dependency injection
SKAIApiDep = Annotated[SKAIApi, Depends(get_skai_api)]


@alru_cache(maxsize=8, ttl=60 * 60 * 24)
async def get_filter_options(skai: SKAIApi) -> skai_api_models.FilterValuesResponse:
    """Get filter options from SKAI API."""

    return await skai.get_filter_values()


__all__ = [
    "SKAIApi",
    "SKAIApiError",
    "SKAIApiDep",
    "get_skai_api",
    "get_filter_options",
]
