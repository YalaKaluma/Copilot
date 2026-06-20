"""Promo endpoints for the filtered SKAI v2 client."""

from models.skai_api_v2.promo import PromoHeatmapRequest, PromoHeatmapResponse
from services.skai_api_v2.transport import SkaiApiV2Transport


class PromoResource:
    """Promo endpoint methods."""

    def __init__(self, transport: SkaiApiV2Transport) -> None:
        self._transport = transport

    async def get_heatmap(self, request: PromoHeatmapRequest) -> PromoHeatmapResponse:
        return await self._transport.request_model(
            "GET",
            "/api/v1/promo/heatmap",
            PromoHeatmapResponse,
            query=request,
        )
