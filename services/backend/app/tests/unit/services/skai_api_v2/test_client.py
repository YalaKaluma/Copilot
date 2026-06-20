"""Unit tests for the filtered SKAI v2 client."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from models.skai_api_v2.filters import (
    FilterMetadata,
    FilterOptions,
    FilterValuesResponse,
    FilterValuesResponse as FilterValuesResponseFromModule,
    RelatedFiltersRequest,
)
from models.skai_api_v2.promo import (
    PromoHeatmapCell,
    PromoHeatmapDim,
    PromoHeatmapRequest,
    PromoHeatmapRequest as PromoHeatmapRequestFromModule,
    PromoHeatmapResponse,
    PromoHeatmapSummary,
)
from services.skai_api_v2.client import SkaiApiV2Client
from services.skai_api_v2.exceptions import SkaiApiV2Error


def _build_filter_values_payload() -> dict:
    return {
        "filters": {
            "brands": ["Brand A", "Brand B"],
            "categories": ["Category A"],
            "retailers": ["Retailer A"],
            "channels": ["Online"],
            "price_tiers": ["Premium"],
            "sku_ids": ["SKU001"],
        },
        "metadata": {
            "tenant_id": 42,
            "last_updated": "2026-06-04T09:15:00Z",
            "data_range": {
                "min_date": "2025-01-01",
                "max_date": "2026-05-31",
            },
        },
    }


def _build_heatmap_payload() -> dict:
    return {
        "data": [
            {
                "x_value": "Brand A",
                "y_value": "Retailer A",
                "investment": "12.34",
                "incremental_gp": "5.67",
                "total_sales": "120.00",
                "roi_pct": 0.46,
                "uplift_pct": 0.12,
                "sales_uplift_pct": 0.15,
                "n_promo_weeks": 4,
            }
        ],
        "summary": {
            "x_dim_kind": "brand",
            "y_dim_kind": "retailer",
            "cell_count": 1,
            "total_investment": "12.34",
            "total_incremental_gp": "5.67",
            "total_sales": "120.00",
            "overall_roi_pct": 0.46,
            "overall_uplift_pct": 0.12,
            "overall_sales_uplift_pct": 0.15,
            "n_promo_weeks": 4,
            "currency": "EUR",
        },
    }


def _build_client(handler) -> SkaiApiV2Client:
    return SkaiApiV2Client(
        base_url="https://example.test",
        api_key="test-api-key",
        auth_token="test-bearer-token",
        extra_headers={
            "Origin": "https://client.test",
            "Referer": "https://client.test/",
            "User-Agent": "skai-v2-test",
        },
        transport=httpx.MockTransport(handler),
    )


class TestSkaiApiV2Client:
    @pytest.mark.asyncio
    async def test_get_filter_values_parses_response_and_sends_headers(self):
        payload = _build_filter_values_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/api/v1/filter-values"
            assert request.headers["X-API-Key"] == "test-api-key"
            assert request.headers["Authorization"] == "Bearer test-bearer-token"
            assert request.headers["Origin"] == "https://client.test"
            assert request.headers["Referer"] == "https://client.test/"
            assert request.headers["User-Agent"] == "skai-v2-test"
            return httpx.Response(200, json=payload)

        async with _build_client(handler) as client:
            response = await client.filters.get_values()

        assert isinstance(response, FilterValuesResponse)
        assert response.filters.brands == ["Brand A", "Brand B"]
        assert response.metadata.tenant_id == 42
        assert response.metadata.data_range.min_date == date(2025, 1, 1)

    @pytest.mark.asyncio
    async def test_get_related_serializes_request_body(self):
        payload = _build_filter_values_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/api/v1/filter-values/related"
            assert json.loads(request.content.decode()) == {
                "brands": ["Brand A"],
                "retailers": ["Retailer A"],
                "priceTiers": ["Premium"],
            }
            return httpx.Response(200, json=payload)

        request = RelatedFiltersRequest(
            brands=["Brand A"],
            retailers=["Retailer A"],
            price_tiers=["Premium"],
        )

        async with _build_client(handler) as client:
            response = await client.filters.get_related(request)

        assert response.filters.categories == ["Category A"]

    @pytest.mark.asyncio
    async def test_get_heatmap_serializes_repeated_query_params_and_omits_empty_lists(
        self,
    ):
        payload = _build_heatmap_payload()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/api/v1/promo/heatmap"
            params = request.url.params
            assert params.get("x_dim_kind") == "brand"
            assert params.get("y_dim_kind") == "retailer"
            assert params.get("market") == "BE"
            assert params.get("start_date") == "2026-01-01"
            assert params.get("end_date") == "2026-03-31"
            assert params.get_list("brands") == ["Brand A", "Brand B"]
            assert params.get_list("depth_deciles") == ["10-20%", "20-30%"]
            assert "retailers" not in params
            assert "sku_ids" not in params
            return httpx.Response(200, json=payload)

        request = PromoHeatmapRequest(
            x_dim_kind=PromoHeatmapDim.brand,
            y_dim_kind=PromoHeatmapDim.retailer,
            market="BE",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 3, 31),
            brands=["Brand A", "Brand B"],
            retailers=[],
            sku_ids=[],
            depth_deciles=["10-20%", "20-30%"],
        )

        async with _build_client(handler) as client:
            response = await client.promo.get_heatmap(request)

        assert isinstance(response, PromoHeatmapResponse)
        assert response.summary.x_dim_kind == PromoHeatmapDim.brand.value
        assert response.data is not None
        assert response.data[0].investment is not None
        assert response.data[0].investment.root == "12.34"

    @pytest.mark.asyncio
    async def test_non_2xx_responses_raise_typed_error(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(502, json={"detail": "upstream unavailable"})

        async with _build_client(handler) as client:
            with pytest.raises(SkaiApiV2Error) as exc_info:
                await client.filters.get_values()

        assert exc_info.value.status_code == 502
        assert exc_info.value.response_body == {"detail": "upstream unavailable"}


class TestSkaiApiV2PublicExports:
    def test_domain_modules_export_stable_public_types(self):
        assert FilterValuesResponseFromModule is FilterValuesResponse
        assert PromoHeatmapRequestFromModule is PromoHeatmapRequest

        filter_request = RelatedFiltersRequest(brands=["Brand A"])
        heatmap_request = PromoHeatmapRequest()
        filter_response = FilterValuesResponse.model_validate(
            _build_filter_values_payload()
        )
        heatmap_response = PromoHeatmapResponse.model_validate(_build_heatmap_payload())

        assert isinstance(filter_request, RelatedFiltersRequest)
        assert isinstance(heatmap_request, PromoHeatmapRequest)
        assert isinstance(filter_response.metadata, FilterMetadata)
        assert isinstance(filter_response.filters, FilterOptions)
        assert isinstance(heatmap_response.summary, PromoHeatmapSummary)
        assert heatmap_response.data is not None
        assert isinstance(heatmap_response.data[0], PromoHeatmapCell)
