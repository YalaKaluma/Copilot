"""Modular filtered SKAI v2 client."""

import httpx
from services.skai_api_v2.resources.filters import FiltersResource
from services.skai_api_v2.resources.promo import PromoResource
from services.skai_api_v2.transport import SkaiApiV2Transport


class SkaiApiV2Client:
    """Standalone client for the filtered SKAI v2 API surface."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        auth_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = SkaiApiV2Transport(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            auth_token=auth_token,
            extra_headers=extra_headers,
            transport=transport,
        )
        self.filters = FiltersResource(self._transport)
        self.promo = PromoResource(self._transport)

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> "SkaiApiV2Client":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
