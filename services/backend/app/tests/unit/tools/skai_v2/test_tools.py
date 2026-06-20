from __future__ import annotations

from typing import Any, cast
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.skai_api_v2.filters import FilterOptions, FilterValuesResponse
from models.skai_api_v2.promo import (
    PromoHeatmapDim,
    PromoHeatmapRequest,
    PromoHeatmapResponse,
)
from services.skai_api import SKAIApi
from services.skai_api_v2.client import SkaiApiV2Client
from tools.skai.tools import AGENT_TOOL_REGISTRY
from tools.skai_v2 import promo as promo_tools
from tools.skai_v2.filters import SUPPORTED_FILTER_FIELDS, create_get_filter_values_tool
from tools.skai_v2.tools import get_skai_promo_tools


def _build_filter_values_response() -> FilterValuesResponse:
    return FilterValuesResponse.model_validate(
        {
            "filters": {
                "superCategories": ["Paint"],
                "brands": ["Brand A", "Brand B"],
                "categories": ["Category A"],
                "subcategories": ["Subcategory A"],
                "retailers": ["Retailer A"],
                "channels": ["Online"],
                "priceTiers": ["Premium"],
                "packSizeRangeValues": ["0-5L"],
                "skuIds": ["SKU001"],
            },
            "metadata": {
                "tenantId": 42,
                "lastUpdated": "2026-06-04T09:15:00Z",
                "dataRange": {
                    "minDate": "2025-01-01",
                    "maxDate": "2026-05-31",
                },
            },
        }
    )


def _build_heatmap_response(cell_count: int) -> PromoHeatmapResponse:
    rows = [
        {
            "xValue": f"Brand {index}",
            "yValue": f"Retailer {index}",
            "investment": f"{index + 10}.00",
            "incrementalGp": f"{index + 5}.00",
            "totalSales": f"{index + 100}.00",
            "roiPct": 0.4,
            "upliftPct": 0.1,
            "salesUpliftPct": 0.12,
            "nPromoWeeks": 4,
        }
        for index in range(cell_count)
    ]
    return PromoHeatmapResponse.model_validate(
        {
            "data": rows,
            "summary": {
                "xDimKind": "brand",
                "yDimKind": "retailer",
                "cellCount": cell_count,
                "totalInvestment": "100.00",
                "totalIncrementalGp": "50.00",
                "totalSales": "300.00",
                "overallRoiPct": 0.4,
                "overallUpliftPct": 0.1,
                "overallSalesUpliftPct": 0.12,
                "nPromoWeeks": 12,
                "currency": "EUR",
            },
        }
    )


def _build_v2_client(filter_response=None, heatmap_response=None) -> SkaiApiV2Client:
    client = SkaiApiV2Client(base_url="https://example.test")
    cast(Any, client).filters = SimpleNamespace(
        get_values=AsyncMock(return_value=filter_response),
        get_related=AsyncMock(return_value=filter_response),
    )
    cast(Any, client).promo = SimpleNamespace(
        get_heatmap=AsyncMock(return_value=heatmap_response),
    )
    return client


def _build_agent(skai_service):
    return SimpleNamespace(
        session_id="session-123",
        skai_service=skai_service,
        llm_service=SimpleNamespace(),
    )


class TestSkaiV2FilterTool:
    @pytest.fixture
    def fake_client(self):
        return _build_v2_client(filter_response=_build_filter_values_response())

    @pytest.mark.asyncio
    async def test_filter_tool_uses_get_values_when_no_args(self, fake_client):
        result = await create_get_filter_values_tool().executor(
            _build_agent(fake_client),
            {},
        )

        fake_client.filters.get_values.assert_awaited_once_with()
        fake_client.filters.get_related.assert_not_called()
        assert result["metadata"]["tenant_id"] == 42
        assert result["filters"]["brands"] == ["Brand A", "Brand B"]

    @pytest.mark.asyncio
    async def test_filter_tool_uses_related_endpoint_when_filter_args_present(
        self,
        fake_client,
    ):
        await create_get_filter_values_tool().executor(
            _build_agent(fake_client),
            {"brands": ["Brand A"], "retailers": "Retailer A"},
        )

        fake_client.filters.get_values.assert_not_called()
        fake_client.filters.get_related.assert_awaited_once()
        request = fake_client.filters.get_related.await_args.args[0]
        assert request.brands == ["Brand A"]
        assert request.retailers == ["Retailer A"]

    def test_filter_tool_schema_only_exposes_supported_v2_filter_params(self):
        tool = create_get_filter_values_tool(FilterOptions(brands=["Brand A"]))

        assert set(tool.definition.parameters.properties) == set(
            SUPPORTED_FILTER_FIELDS
        )
        assert tool.definition.parameters.properties["brands"].items.enum == ["Brand A"]

    @pytest.mark.asyncio
    async def test_filter_tool_rejects_v1_skai_service(self):
        agent = _build_agent(SKAIApi(base_url="https://example.test"))

        with pytest.raises(TypeError, match="SkaiApiV2Client"):
            await create_get_filter_values_tool().executor(agent, {})


class TestSkaiV2HeatmapTool:
    @pytest.mark.asyncio
    async def test_heatmap_translates_axes_to_v2_request(self, monkeypatch):
        fake_client = _build_v2_client(
            heatmap_response=_build_heatmap_response(cell_count=1)
        )
        monkeypatch.setattr(
            "tools.skai_v2.promo.get_settings",
            lambda: SimpleNamespace(skai_max_data_items=10),
        )

        await promo_tools.create_get_promo_heatmap_tool().executor(
            _build_agent(fake_client),
            {"x_axis": "brand", "y_axis": "retailer", "brands": "Brand A,Brand B"},
        )

        request = fake_client.promo.get_heatmap.await_args.args[0]
        assert isinstance(request, PromoHeatmapRequest)
        assert request.x_dim_kind == PromoHeatmapDim.brand.value
        assert request.y_dim_kind == PromoHeatmapDim.retailer.value
        assert request.brands == ["Brand A", "Brand B"]

    @pytest.mark.asyncio
    async def test_heatmap_returns_raw_payload_below_threshold(self, monkeypatch):
        fake_client = _build_v2_client(
            heatmap_response=_build_heatmap_response(cell_count=1)
        )
        monkeypatch.setattr(
            "tools.skai_v2.promo.get_settings",
            lambda: SimpleNamespace(skai_max_data_items=10),
        )

        result = await promo_tools.create_get_promo_heatmap_tool().executor(
            _build_agent(fake_client),
            {"x_axis": "brand", "y_axis": "retailer"},
        )

        assert result["summary"]["cell_count"] == 1
        assert result["data"][0]["x_value"] == "Brand 0"

    @pytest.mark.asyncio
    async def test_heatmap_large_payload_without_code_interpreter(self, monkeypatch):
        fake_client = _build_v2_client(
            heatmap_response=_build_heatmap_response(cell_count=3)
        )
        monkeypatch.setattr(
            "tools.skai_v2.promo.get_settings",
            lambda: SimpleNamespace(skai_max_data_items=2),
        )
        monkeypatch.setattr(
            "tools.skai_v2.promo.write_local_code_execution_dataset",
            lambda session_id, file_name, df: "/tmp/promo_heatmap_v2.csv",
        )

        result = await promo_tools.create_get_promo_heatmap_tool().executor(
            _build_agent(fake_client),
            {"x_axis": "brand", "y_axis": "retailer"},
        )

        assert result["summary"]["cell_count"] == 3
        assert result["available_x_values"] == ["Brand 0", "Brand 1", "Brand 2"]
        assert result["additional_info"].endswith(
            "/tmp/promo_heatmap_v2.csv in CSV format"
        )

    @pytest.mark.asyncio
    async def test_heatmap_large_payload_exports_local_csv(self, monkeypatch):
        fake_client = _build_v2_client(
            heatmap_response=_build_heatmap_response(cell_count=3)
        )
        monkeypatch.setattr(
            "tools.skai_v2.promo.get_settings",
            lambda: SimpleNamespace(skai_max_data_items=2),
        )
        monkeypatch.setattr(
            "tools.skai_v2.promo.write_local_code_execution_dataset",
            lambda session_id, file_name, df: "/tmp/promo_heatmap_v2.csv",
        )

        result = await promo_tools.create_get_promo_heatmap_tool().executor(
            _build_agent(fake_client),
            {"x_axis": "brand", "y_axis": "retailer"},
        )

        assert result["additional_info"].endswith(
            "/tmp/promo_heatmap_v2.csv in CSV format"
        )

    def test_heatmap_tool_uses_v2_filter_enums(self):
        filter_context = FilterOptions(
            brands=["Brand A"],
            retailers=["Retailer A"],
            sku_ids=["SKU001"],
        )

        tool = promo_tools.create_get_promo_heatmap_tool(filter_context)
        properties = tool.definition.parameters.properties

        assert properties["x_axis"].enum == [axis.value for axis in PromoHeatmapDim]
        assert properties["brands"].items.enum == ["Brand A"]
        assert properties["retailers"].items.enum == ["Retailer A"]
        assert properties["sku_ids"].items.enum == ["SKU001"]

    @pytest.mark.asyncio
    async def test_heatmap_rejects_v1_skai_service(self):
        agent = _build_agent(SKAIApi(base_url="https://example.test"))

        with pytest.raises(TypeError, match="SkaiApiV2Client"):
            await promo_tools.create_get_promo_heatmap_tool().executor(
                agent,
                {"x_axis": "brand", "y_axis": "retailer"},
            )


class TestSkaiV2Isolation:
    def test_v2_tools_are_not_registered_in_existing_registry(self):
        assert "v9-dev" not in AGENT_TOOL_REGISTRY
        assert "skai_v2" not in AGENT_TOOL_REGISTRY

    def test_v2_helpers_are_not_reexported_from_existing_skai_package(self):
        import tools.skai as skai_package

        assert not hasattr(skai_package, "get_skai_v2_tools")
        assert not hasattr(skai_package, "create_get_promo_heatmap_v2_tool")

    def test_get_skai_promo_tools_returns_only_heatmap_tool(self):
        tools = get_skai_promo_tools()

        assert [tool.definition.name for tool in tools] == [
            "skai_get_promo_heatmap",
        ]
