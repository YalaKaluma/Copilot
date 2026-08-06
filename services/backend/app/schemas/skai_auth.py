"""Schemas for SKAI authentication endpoints."""

from datetime import datetime

from pydantic import Field

from .base import BaseResponse, CamelCaseModel


class SkaiLoginRequest(CamelCaseModel):
    """Request body for SKAI login."""

    username: str = Field(..., description="SKAI username (email)")
    password: str = Field(..., description="SKAI password", min_length=1)


class SkaiLoginResponse(BaseResponse):
    """Response body for SKAI login."""

    connected: bool = Field(..., description="Whether SKAI is connected")
    skai_username: str | None = Field(
        default=None, description="SKAI username used for login"
    )
    expires_at: datetime | None = Field(
        default=None, description="Token expiration time"
    )


class SkaiRefreshResponse(BaseResponse):
    """Response body for SKAI token refresh."""

    connected: bool = Field(..., description="Whether SKAI is connected")
    expires_at: datetime | None = Field(
        default=None, description="Token expiration time"
    )


class SkaiDisconnectResponse(BaseResponse):
    """Response body for SKAI disconnect."""

    connected: bool = Field(default=False, description="Whether SKAI is connected")


class SkaiStatusResponse(BaseResponse):
    """Response body for SKAI connection status."""

    connected: bool = Field(..., description="Whether SKAI is connected")
    skai_username: str | None = Field(
        default=None, description="SKAI username used for login"
    )
    expires_at: datetime | None = Field(
        default=None, description="Token expiration time"
    )


class SkaiTenantsResponse(BaseResponse):
    """Tenant codes granted to the authenticated SKAI account."""

    tenants: list[str] = Field(default_factory=list)
