from enum import Enum
import json
from typing import Annotated, Any
import pandas as pd

from pydantic import BaseModel, Field
from schemas.base import CamelCaseModel
from models.skai_api.autogen import (
    EventScatterResponse,
    HeatmapAxis,
    PromoCalendarResponse,
    ScatterLegend,
    TacticGroupBy,
    TacticXAxis,
)


class AssortmentRequest(CamelCaseModel):
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the assortment for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the assortment for"),
    ]
    retailers: Annotated[
        list[str] | None,
        Field(None, description="The retailers to get the assortment for"),
    ]
    sku_ids: Annotated[
        list[str] | None, Field(None, description="The SKUs to get the assortment for")
    ]


class ChannelFairShareRequest(CamelCaseModel):
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the fair share for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the fair share for"),
    ]


class ChannelIntensityBy(str, Enum):
    brand = "brand"
    retailer = "retailer"


class ChannelIntensityRequest(CamelCaseModel):
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the intensity for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the intensity for"),
    ]
    by: Annotated[
        ChannelIntensityBy,
        Field(ChannelIntensityBy.brand, description="The by to get the intensity for"),
    ]


class ChannelTransparencyRequest(CamelCaseModel):
    start_date: Annotated[
        str | None,
        Field(None, description="The start date to get the transparency for"),
    ]
    end_date: Annotated[
        str | None,
        Field(None, description="The end date to get the transparency for"),
    ]
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the transparency for"),
    ]
    subcategories: Annotated[
        list[str] | None,
        Field(None, description="The subcategories to get the transparency for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the transparency for"),
    ]
    retailers: Annotated[
        list[str] | None,
        Field(None, description="The retailers to get the transparency for"),
    ]
    categories: Annotated[
        list[str] | None,
        Field(None, description="The categories to get the transparency for"),
    ]
    channels: Annotated[
        list[str] | None,
        Field(None, description="The channels to get the transparency for"),
    ]
    depth_deciles: Annotated[
        list[str] | None,
        Field(None, description="The depth deciles to get the transparency for"),
    ]


class BrandLadderRequest(CamelCaseModel):
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the brand ladder for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the brand ladder for"),
    ]
    retailers: Annotated[
        list[str] | None,
        Field(None, description="The retailers to get the brand ladder for"),
    ]
    sku_ids: Annotated[
        list[str] | None,
        Field(None, description="The SKUs to get the brand ladder for"),
    ]
    subcategories: Annotated[
        list[str] | None,
        Field(None, description="The subcategories to get the brand ladder for"),
    ]


class PricePackCurveRequest(CamelCaseModel):
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the price pack curve for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the price pack curve for"),
    ]
    sku_ids: Annotated[
        list[str] | None,
        Field(None, description="The SKUs to get the price pack curve for"),
    ]
    pack_size_ranges: Annotated[
        list[str] | None,
        Field(None, description="The pack size ranges to get the price pack curve for"),
    ]


class SimulatorBaseRequest(CamelCaseModel):
    retailers: Annotated[
        list[str] | None,
        Field(None, description="The retailers to get the simulator base for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the simulator base for"),
    ]
    categories: Annotated[
        list[str] | None,
        Field(None, description="The categories to get the simulator base for"),
    ]
    subcategories: Annotated[
        list[str] | None,
        Field(None, description="The subcategories to get the simulator base for"),
    ]
    sku_ids: Annotated[
        list[str] | None,
        Field(None, description="The SKUs to get the simulator base for"),
    ]
    owned_brand: Annotated[
        str | None,
        Field(None, description="The owned brand to get the simulator base for"),
    ]
    include_zero_volume: Annotated[
        bool,
        Field(
            False, description="The include zero volume to get the simulator base for"
        ),
    ]


class ScenarioListRequest(CamelCaseModel):
    status: Annotated[
        str | None,
        Field(None, description="The status to get the scenario list for"),
    ]
    limit: Annotated[
        int,
        Field(50, description="The limit to get the scenario list for"),
    ]
    offset: Annotated[
        int,
        Field(0, description="The offset to get the scenario list for"),
    ]


class ScenarioCreateResponse(CamelCaseModel):
    scenario_id: Annotated[
        int,
        Field(
            None, description="The scenario id to get the scenario create response for"
        ),
    ]


class PromoRequestBase(CamelCaseModel):
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the promo for"),
    ]
    start_date: Annotated[
        str | None,
        Field(None, description="The start date to get the promo for"),
    ]
    end_date: Annotated[
        str | None,
        Field(None, description="The end date to get the promo for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the promo for"),
    ]
    retailers: Annotated[
        list[str] | None,
        Field(None, description="The retailers to get the promo for"),
    ]
    categories: Annotated[
        list[str] | None,
        Field(None, description="The categories to get the promo for"),
    ]
    subcategories: Annotated[
        list[str] | None,
        Field(None, description="The subcategories to get the promo for"),
    ]
    channels: Annotated[
        list[str] | None,
        Field(None, description="The channels to get the promo for"),
    ]
    depth_deciles: Annotated[
        list[str] | None,
        Field(None, description="The depth deciles to get the promo for"),
    ]
    promo_tactics: Annotated[
        list[str] | None,
        Field(None, description="The promo tactics to get the promo for"),
    ]


class PromoRequest(PromoRequestBase):
    sku_ids: Annotated[
        list[str] | None,
        Field(None, description="The SKUs to get the promo for"),
    ]


class HeatmapRequest(PromoRequest):
    x_axis: Annotated[
        HeatmapAxis,
        Field(HeatmapAxis.retailer, description="The x axis to get the heatmap for"),
    ]
    y_axis: Annotated[
        HeatmapAxis,
        Field(HeatmapAxis.sku, description="The y axis to get the heatmap for"),
    ]


class EventScatterRequest(PromoRequest):
    roi_min: Annotated[
        float | None,
        Field(None, description="The roi min to get the event scatter for"),
    ]
    roi_max: Annotated[
        float | None,
        Field(None, description="The roi max to get the event scatter for"),
    ]
    uplift_min: Annotated[
        float | None,
        Field(None, description="The uplift min to get the event scatter for"),
    ]
    uplift_max: Annotated[
        float | None,
        Field(None, description="The uplift max to get the event scatter for"),
    ]
    legend: Annotated[
        ScatterLegend,
        Field(
            ScatterLegend.brand, description="The legend to get the event scatter for"
        ),
    ]


class MarketEffectivenessBy(str, Enum):
    brand = "brand"
    retailer = "retailer"


class MarketEffectivenessRequest(PromoRequestBase):
    by: Annotated[
        MarketEffectivenessBy,
        Field(
            MarketEffectivenessBy.brand,
            description="The by to get the market effectiveness for",
        ),
    ]


class TacticEffectivenessRequest(PromoRequestBase):
    x_axis: Annotated[
        TacticXAxis,
        Field(
            TacticXAxis.promo_tactic,
            description="The x axis to get the tactic effectiveness for",
        ),
    ]


class ProductDeepDiveRequest(CamelCaseModel):
    sku_id: Annotated[
        str,
        Field(None, description="The SKU ID to get the product deep dive for"),
    ]
    retailer: Annotated[
        str | None,
        Field(None, description="The retailer to get the product deep dive for"),
    ]
    start_date: Annotated[
        str | None,
        Field(None, description="The start date to get the product deep dive for"),
    ]
    end_date: Annotated[
        str | None,
        Field(None, description="The end date to get the product deep dive for"),
    ]
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the product deep dive for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the product deep dive for"),
    ]
    categories: Annotated[
        list[str] | None,
        Field(None, description="The categories to get the product deep dive for"),
    ]
    subcategories: Annotated[
        list[str] | None,
        Field(None, description="The subcategories to get the product deep dive for"),
    ]
    channels: Annotated[
        list[str] | None,
        Field(None, description="The channels to get the product deep dive for"),
    ]
    depth_deciles: Annotated[
        list[str] | None,
        Field(None, description="The depth deciles to get the product deep dive for"),
    ]
    promo_tactics: Annotated[
        list[str] | None,
        Field(None, description="The promo tactics to get the product deep dive for"),
    ]


class DiscountDepthQCRequest(CamelCaseModel):
    super_category: Annotated[
        str | None,
        Field(None, description="The super category to get the discount depth qc for"),
    ]
    start_date: Annotated[
        str | None,
        Field(None, description="The start date to get the discount depth qc for"),
    ]
    end_date: Annotated[
        str | None,
        Field(None, description="The end date to get the discount depth qc for"),
    ]
    brands: Annotated[
        list[str] | None,
        Field(None, description="The brands to get the discount depth qc for"),
    ]
    retailers: Annotated[
        list[str] | None,
        Field(None, description="The retailers to get the discount depth qc for"),
    ]
    categories: Annotated[
        list[str] | None,
        Field(None, description="The categories to get the discount depth qc for"),
    ]
    subcategories: Annotated[
        list[str] | None,
        Field(None, description="The subcategories to get the discount depth qc for"),
    ]
    channels: Annotated[
        list[str] | None,
        Field(None, description="The channels to get the discount depth qc for"),
    ]
    depth_deciles: Annotated[
        list[str] | None,
        Field(None, description="The depth deciles to get the discount depth qc for"),
    ]
    promo_tactics: Annotated[
        list[str] | None,
        Field(None, description="The promo tactics to get the discount depth qc for"),
    ]


class PromoPlannerBase(CamelCaseModel):
    sku_id: Annotated[
        str,
        Field(..., description="The SKU ID to get the promo planner for"),
    ]


class PromoPlannerRequest(PromoPlannerBase):
    retailer: Annotated[
        str | None,
        Field(None, description="The retailer to get the promo planner for"),
    ]


class BaselineReviewRequest(PromoPlannerBase):
    retailer: Annotated[
        str,
        Field(..., description="The retailer to get the baseline review for"),
    ]


class DeepDiveTacticRequest(PromoPlannerBase):
    retailer: Annotated[
        str | None,
        Field(None, description="The retailer to get the deep dive tactic for"),
    ]
    group_by: Annotated[
        TacticGroupBy,
        Field(
            TacticGroupBy.depth_decile,
            description="The group by to get the deep dive tactic for",
        ),
    ]


class LargePayloadAltResponse(BaseModel):
    summarised_data: Annotated[
        dict[str, Any], Field(..., description="The summarised data")
    ]
    dataset: Annotated[list[dict[str, Any]], Field(..., description="The dataset")]


class PromoCalendarResponsePatched(PromoCalendarResponse):
    """Patched PromoCalendarResponse to add summary field."""

    def large_payload_alternative(self) -> LargePayloadAltResponse:
        """Summary of the promo calendar."""

        data = self.data

        if not data:
            return LargePayloadAltResponse(
                summarised_data={"summary": "No promo events found"}, dataset=[]
            )

        rows = [item.model_dump(mode="json", exclude_none=True) for item in data]
        df = pd.DataFrame(rows)
        if df.empty:
            return LargePayloadAltResponse(
                summarised_data={"summary": "No promo events found"}, dataset=[]
            )

        group_cols = ["retailer", "brand", "start_date", "duration_weeks"]
        for col in [*group_cols, "sku_id"]:
            if col not in df.columns:
                df[col] = None

        numeric_cols = df.select_dtypes(include="number").columns
        numeric_cols = [col for col in numeric_cols if col != "event_id"]

        sku_counts = df.groupby(group_cols, dropna=False)["sku_id"].nunique(dropna=True)

        if numeric_cols:
            numeric_stats = df.groupby(group_cols, dropna=False)[numeric_cols].agg(
                ["min", "median", "max"]
            )
            numeric_stats.columns = [
                f"{metric}_{stat.replace('median', 'p50')}"
                for metric, stat in zip(
                    numeric_stats.columns.get_level_values(0),
                    numeric_stats.columns.get_level_values(1),
                )
            ]
            summary = (
                sku_counts.to_frame(name="sku_count")
                .join(numeric_stats)
                .reset_index()
                .sort_values(group_cols, ascending=True)
            )
        else:
            summary = (
                sku_counts.to_frame(name="sku_count")
                .reset_index()
                .sort_values(group_cols, ascending=True)
            )

        summary = summary.where(pd.notna(summary), None)

        # Build {"group_key": {"metric": {stats}}} JSON (group = retailer|brand|start_date|duration_weeks)
        result: dict[str, dict[str, Any]] = {}
        for _, row in summary.iterrows():
            key = "|".join(str(row[c]) for c in group_cols)
            result[key] = {}
            for col in summary.columns:
                if col in group_cols:
                    continue
                if col.endswith("_min") or col.endswith("_p50") or col.endswith("_max"):
                    metric, stat = col.rsplit("_", 1)
                    if metric not in result[key]:
                        result[key][metric] = {}
                    result[key][metric][stat] = row[col]
                else:
                    result[key][col] = {"value": row[col]}
        columns_in_raw_data = df.columns.tolist()
        available_brands = df["brand"].unique().tolist()
        available_retailers = df["retailer"].unique().tolist()
        summarised_data = {
            "summary": json.dumps(result),
            "columns_in_raw_data": columns_in_raw_data,
            "available_brands": available_brands,
            "available_retailers": available_retailers,
        }

        return LargePayloadAltResponse(summarised_data=summarised_data, dataset=rows)


class EventScatterResponsePatched(EventScatterResponse):
    """Patched EventScatterResponse to add summary field."""

    def large_payload_alternative(self) -> LargePayloadAltResponse:
        """Summary of the event scatter."""

        data = self.data

        if not data:
            return LargePayloadAltResponse(
                summarised_data={"summary": "No event scatter data found"}, dataset=[]
            )

        rows = [item.model_dump(mode="json", exclude_none=True) for item in data]
        df = pd.DataFrame(rows)
        if df.empty:
            return LargePayloadAltResponse(
                summarised_data={"summary": "No event scatter data found"}, dataset=[]
            )

        numeric_cols = df.select_dtypes(include="number").columns
        numeric_cols = [col for col in numeric_cols if col != "event_id"]

        if numeric_cols:
            numeric_stats = df.groupby("brand", dropna=False)[numeric_cols].agg(
                ["min", "median", "max"]
            )
            numeric_stats.columns = [
                f"{metric}_{stat.replace('median', 'p50')}"
                for metric, stat in zip(
                    numeric_stats.columns.get_level_values(0),
                    numeric_stats.columns.get_level_values(1),
                )
            ]
            summary = numeric_stats.reset_index().sort_values("brand", ascending=True)
        else:
            summary = (
                df.groupby("brand", dropna=False)
                .size()
                .reset_index(name="count")
                .sort_values("brand", ascending=True)
            )

        summary = summary.where(pd.notna(summary), None)

        # Build {"brand": {"metric": {stats}}} JSON
        result: dict[str, dict[str, Any]] = {}
        for _, row in summary.iterrows():
            brand = row["brand"]
            result[brand] = {}
            for col in summary.columns:
                if col == "brand":
                    continue
                if col.endswith("_min") or col.endswith("_p50") or col.endswith("_max"):
                    metric, stat = col.rsplit("_", 1)
                    if metric not in result[brand]:
                        result[brand][metric] = {}
                    result[brand][metric][stat] = row[col]
                else:
                    result[brand][col] = {"value": row[col]}
        columns_in_raw_data = df.columns.tolist()
        available_brands = df["brand"].unique().tolist()
        summarised_data = {
            "summary": json.dumps(result),
            "columns_in_raw_data": columns_in_raw_data,
            "available_brands": available_brands,
        }

        return LargePayloadAltResponse(summarised_data=summarised_data, dataset=rows)
