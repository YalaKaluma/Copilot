"""Shared transport utilities for the filtered SKAI v2 client."""

from typing import Any, Mapping, TypeVar
from urllib.parse import quote_plus, urlencode

import httpx
from pydantic import BaseModel

from services.skai_api_v2.exceptions import SkaiApiV2Error

T = TypeVar("T", bound=BaseModel)


class SkaiApiV2Transport:
    """HTTP transport with shared auth, serialization, and error handling."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        auth_token: str | None = None,
        timeout: float = 30.0,
        extra_headers: dict[str, str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_token = auth_token
        self.timeout = timeout
        self.extra_headers = extra_headers or {}
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
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
                transport=self._transport,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "SkaiApiV2Transport":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _serialize_payload(
        self,
        payload: BaseModel | Mapping[str, Any] | None = None,
        *,
        by_alias: bool = False,
    ) -> dict[str, Any]:
        if payload is None:
            return {}

        if isinstance(payload, BaseModel):
            source = payload.model_dump(
                exclude_none=True,
                mode="json",
                by_alias=by_alias,
            )
        else:
            source = {key: value for key, value in payload.items() if value is not None}

        serialized: dict[str, Any] = {}
        for key, value in source.items():
            if isinstance(value, list):
                if not value:
                    continue
                serialized[key] = [str(item) for item in value]
            else:
                serialized[key] = value
        return serialized

    async def request_model(
        self,
        method: str,
        path: str,
        response_model: type[T],
        *,
        query: BaseModel | Mapping[str, Any] | None = None,
        json_body: BaseModel | Mapping[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> T:
        client = await self._get_client()

        url = path
        query_params = self._serialize_payload(query)
        if query_params:
            prepared_params: dict[str, Any] = {}
            for key, value in query_params.items():
                if isinstance(value, list):
                    prepared_params[key] = [str(item) for item in value]
                else:
                    prepared_params[key] = str(value)
            query_string = urlencode(
                prepared_params,
                doseq=True,
                quote_via=quote_plus,
            )
            url = f"{path}?{query_string}"

        request_json: dict[str, Any] | None = None
        if json_body is not None:
            request_json = self._serialize_payload(json_body, by_alias=True)

        try:
            response = await client.request(
                method=method,
                url=url,
                json=request_json,
                headers=extra_headers,
            )
            response.raise_for_status()
            return response_model.model_validate(response.json())
        except httpx.HTTPStatusError as exc:
            error_body = None
            try:
                error_body = exc.response.json()
            except Exception:
                pass
            raise SkaiApiV2Error(
                message=f"SKAI API v2 request failed: {exc.response.status_code}",
                status_code=exc.response.status_code,
                response_body=error_body,
            ) from exc
        except httpx.RequestError as exc:
            raise SkaiApiV2Error(f"SKAI API v2 request failed: {exc}") from exc
