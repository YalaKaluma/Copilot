"""SKAI authentication endpoints for per-user Cognito tokens."""

import base64
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from core.dependencies import (
    AuthTokenDep,
    DatabaseDep,
    SkaiAuthServiceDep,
    _get_user_skai_token,
)
from schemas.skai_auth import (
    SkaiDisconnectResponse,
    SkaiLoginRequest,
    SkaiLoginResponse,
    SkaiRefreshResponse,
    SkaiStatusResponse,
    SkaiTenantsResponse,
)
from services.skai_auth_service import SkaiAuthError

router = APIRouter(tags=["SKAI Auth"])


def _tenant_codes_from_token(token: str) -> list[str]:
    try:
        payload_part = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(payload_part + "==="))
        groups = payload.get("cognito:groups") or []
        return sorted(
            group
            for group in groups
            if isinstance(group, str) and not group.endswith("_admin")
        )
    except (IndexError, ValueError, TypeError, json.JSONDecodeError):
        return []


@router.get(
    "/skai/auth/tenants",
    response_model=SkaiTenantsResponse,
    summary="List SKAI tenants available to the connected account",
)
async def skai_tenants(
    token: Annotated[str, Depends(_get_user_skai_token)],
) -> SkaiTenantsResponse:
    return SkaiTenantsResponse(
        success=True,
        message="SKAI tenants loaded",
        tenants=_tenant_codes_from_token(token),
    )


@router.get(
    "/skai/auth/status",
    response_model=SkaiStatusResponse,
    summary="Check SKAI connection status",
)
async def skai_status(
    auth: AuthTokenDep,
    db: DatabaseDep,
    skai_auth_service: SkaiAuthServiceDep,
) -> SkaiStatusResponse:
    user = auth.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in token",
        )

    credential = await skai_auth_service.get_credentials(user.id, db)
    if credential is None:
        return SkaiStatusResponse(
            success=True,
            message="SKAI not connected",
            connected=False,
        )

    try:
        # Validate token proactively so stale credentials are surfaced before
        # orchestrator requests fail.
        await skai_auth_service.get_valid_id_token(user.id, db)
    except SkaiAuthError as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            try:
                await skai_auth_service.disconnect(user.id, db)
            except SkaiAuthError:
                pass
        return SkaiStatusResponse(
            success=True,
            message=(
                "SKAI session expired. Please reconnect."
                if e.status_code == status.HTTP_401_UNAUTHORIZED
                else str(e)
            ),
            connected=False,
        )

    credential = await skai_auth_service.get_credentials(user.id, db)

    if not credential:
        return SkaiStatusResponse(
            success=True,
            message="SKAI not connected",
            connected=False,
        )

    return SkaiStatusResponse(
        success=True,
        message="SKAI connected",
        connected=True,
        skai_username=credential.skai_username,
        expires_at=credential.expires_at,
    )


@router.post(
    "/skai/auth/login",
    response_model=SkaiLoginResponse,
    summary="Log in to SKAI and store tokens",
)
async def skai_login(
    request: SkaiLoginRequest,
    auth: AuthTokenDep,
    db: DatabaseDep,
    skai_auth_service: SkaiAuthServiceDep,
) -> SkaiLoginResponse:
    user = auth.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in token",
        )

    try:
        credential = await skai_auth_service.login(
            user_id=user.id,
            username=request.username,
            password=request.password,
            db=db,
        )
    except SkaiAuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )

    return SkaiLoginResponse(
        success=True,
        message="SKAI login successful",
        connected=True,
        skai_username=credential.skai_username,
        expires_at=credential.expires_at,
    )


@router.post(
    "/skai/auth/refresh",
    response_model=SkaiRefreshResponse,
    summary="Refresh stored SKAI token",
)
async def skai_refresh(
    auth: AuthTokenDep,
    db: DatabaseDep,
    skai_auth_service: SkaiAuthServiceDep,
) -> SkaiRefreshResponse:
    user = auth.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in token",
        )

    try:
        credential = await skai_auth_service.refresh_for_user(user.id, db)
    except SkaiAuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )

    return SkaiRefreshResponse(
        success=True,
        message="SKAI token refreshed",
        connected=True,
        expires_at=credential.expires_at,
    )


@router.delete(
    "/skai/auth/disconnect",
    response_model=SkaiDisconnectResponse,
    summary="Disconnect SKAI account and remove stored tokens",
)
async def skai_disconnect(
    auth: AuthTokenDep,
    db: DatabaseDep,
    skai_auth_service: SkaiAuthServiceDep,
) -> SkaiDisconnectResponse:
    user = auth.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in token",
        )

    try:
        await skai_auth_service.disconnect(user.id, db)
    except SkaiAuthError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
        )

    return SkaiDisconnectResponse(
        success=True,
        message="SKAI account disconnected",
        connected=False,
    )
