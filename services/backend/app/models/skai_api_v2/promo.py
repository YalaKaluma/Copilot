"""Promo request and response types for the filtered SKAI v2 client."""

from models.skai_api_v2.generated import (
    GetHeatmapApiV1PromoHeatmapGetParametersQuery as PromoHeatmapRequest,
    PromoHeatmapCell,
    PromoHeatmapDim,
    PromoHeatmapResponse,
    PromoHeatmapSummary,
)

__all__ = [
    "PromoHeatmapCell",
    "PromoHeatmapDim",
    "PromoHeatmapRequest",
    "PromoHeatmapResponse",
    "PromoHeatmapSummary",
]
