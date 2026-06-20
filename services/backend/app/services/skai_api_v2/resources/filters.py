"""Filter endpoints for the filtered SKAI v2 client."""

from models.skai_api_v2.filters import FilterValuesResponse, RelatedFiltersRequest
from services.skai_api_v2.transport import SkaiApiV2Transport


class FiltersResource:
    """Filter endpoint methods."""

    def __init__(self, transport: SkaiApiV2Transport) -> None:
        self._transport = transport

    async def get_values(self) -> FilterValuesResponse:
        return await self._transport.request_model(
            "GET",
            "/api/v1/filter-values",
            FilterValuesResponse,
        )

    async def get_related(self, request: RelatedFiltersRequest) -> FilterValuesResponse:
        return await self._transport.request_model(
            "POST",
            "/api/v1/filter-values/related",
            FilterValuesResponse,
            json_body=request,
        )
