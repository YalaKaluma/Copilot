"""Unit tests for SKAI auth error handling."""

from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError

from services.skai_auth_service import SkaiAuthError, SkaiAuthService


class TestSkaiAuthServiceErrors:
    """Validate SKAI auth failures are mapped to user-safe errors."""

    @pytest.mark.asyncio
    async def test_login_maps_incorrect_credentials_to_401(self, mocker):
        service = SkaiAuthService(SimpleNamespace(skai_token_type="id"))
        mock_db = mocker.AsyncMock()

        def raise_incorrect_username_password(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "NotAuthorizedException",
                        "Message": "Incorrect username or password.",
                    }
                },
                "RespondToAuthChallenge",
            )

        fake_authenticator = SimpleNamespace(
            authenticate=raise_incorrect_username_password
        )
        mocker.patch.object(
            service, "_get_authenticator", return_value=fake_authenticator
        )

        with pytest.raises(SkaiAuthError) as exc_info:
            await service.login(
                user_id="user-1",
                username="user@example.com",
                password="bad-password",
                db=mock_db,
            )

        assert exc_info.value.status_code == 401
        assert str(exc_info.value) == "Incorrect SKAI username or password."

    @pytest.mark.asyncio
    async def test_refresh_maps_expired_refresh_token_to_401(self, mocker):
        service = SkaiAuthService(SimpleNamespace(skai_token_type="id"))
        mock_db = mocker.AsyncMock()
        credential = SimpleNamespace(
            refresh_token="expired-token",
            skai_username="user@example.com",
        )

        def raise_expired_refresh_token(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "NotAuthorizedException",
                        "Message": "Refresh Token has expired",
                    }
                },
                "InitiateAuth",
            )

        fake_authenticator = SimpleNamespace(refresh=raise_expired_refresh_token)
        mocker.patch.object(
            service, "_get_authenticator", return_value=fake_authenticator
        )

        with pytest.raises(SkaiAuthError) as exc_info:
            await service.refresh_tokens(credential=credential, db=mock_db)

        assert exc_info.value.status_code == 401
        assert str(exc_info.value) == (
            "Your SKAI session expired. Please reconnect your SKAI account."
        )

    @pytest.mark.asyncio
    async def test_get_valid_id_token_requires_connected_skai_account(self, mocker):
        service = SkaiAuthService(
            SimpleNamespace(
                env="production",
                skai_token=None,
                skai_token_refresh_margin_seconds=300,
            )
        )
        mock_db = mocker.AsyncMock()
        mocker.patch.object(service, "_get_credential", return_value=None)

        with pytest.raises(SkaiAuthError) as exc_info:
            await service.get_valid_id_token("user-1", mock_db)

        assert exc_info.value.status_code == 401
        assert str(exc_info.value) == "SKAI account not connected"
