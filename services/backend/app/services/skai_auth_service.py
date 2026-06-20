"""SKAI Cognito authentication service for per-user tokens."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import boto3
import jwt
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings, get_settings
from packages.db.models.skai_credential import SkaiCredential

N_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74"
    "020BBEA63B139B22514A08798E3404DDEF9519B3CD3A431B302B0A6DF25F14374"
    "FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7EDEE"
    "386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598D"
    "A48361C55D39A69163FA8FD24CF5F83655D23DCA3AD961C62F356208552BB9ED5"
    "29077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3BE39E7"
    "72C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF695581718399549"
    "7CEA956AE515D2261898FA051015728E5A8AAAC42DAD33170D04507A33A85521A"
    "BDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7ABF5AE8C"
    "DB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733"
    "EC86A64521F2B18177B200CBBE117577A615D6C770988C0BAD946E208E24FA074"
    "E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF"
)
G_HEX = "2"
INFO_BITS = b"Caldera Derived Key"


class SkaiAuthError(Exception):
    """Raised when SKAI authentication fails or is misconfigured."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _map_cognito_client_error(exc: ClientError) -> SkaiAuthError:
    """Map Cognito client errors to user-facing SKAI auth errors."""
    error = exc.response.get("Error", {})
    code = str(error.get("Code", ""))
    message = str(error.get("Message", "Authentication failed"))
    normalized = message.lower()

    if code == "NotAuthorizedException":
        if "refresh token has expired" in normalized:
            return SkaiAuthError(
                "Your SKAI session expired. Please reconnect your SKAI account.",
                status_code=401,
            )
        if "incorrect username or password" in normalized:
            return SkaiAuthError(
                "Incorrect SKAI username or password.",
                status_code=401,
            )
        return SkaiAuthError(
            "SKAI authorization failed. Please sign in again.",
            status_code=401,
        )

    if code in {"UserNotFoundException", "PasswordResetRequiredException"}:
        return SkaiAuthError(
            "SKAI login requires attention. Please verify credentials and sign in again.",
            status_code=401,
        )

    if code == "TooManyRequestsException":
        return SkaiAuthError(
            "Too many SKAI login attempts. Please try again shortly.",
            status_code=429,
        )

    return SkaiAuthError(f"SKAI authentication failed: {message}")


def _pad_hex(hex_str: str) -> str:
    if len(hex_str) % 2 == 1:
        hex_str = f"0{hex_str}"
    elif hex_str[0] in "89ABCDEFabcdef":
        hex_str = f"00{hex_str}"
    return hex_str


def _hex_to_bytes(hex_str: str) -> bytes:
    return binascii.unhexlify(_pad_hex(hex_str))


def _hash_sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _hex_hash(hex_str: str) -> bytes:
    return _hash_sha256(_hex_to_bytes(hex_str))


def _compute_hkdf(ikm: bytes, salt: bytes) -> bytes:
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    t = b""
    okm = b""
    for i in range(1, 3):
        t = hmac.new(prk, t + INFO_BITS + bytes([i]), hashlib.sha256).digest()
        okm += t
    return okm[:16]


def _utc_timestamp() -> str:
    now = datetime.now(UTC)
    # Match Cognito/Amplify format: "Tue Feb 3 10:46:52 UTC 2026"
    return f"{now:%a} {now:%b} {now.day} {now:%H:%M:%S} UTC {now:%Y}"


@dataclass
class CognitoTokens:
    id_token: str | None
    access_token: str | None
    refresh_token: str | None
    expires_in: int


class CognitoSrpAuthenticator:
    """Implements USER_SRP_AUTH for AWS Cognito."""

    def __init__(
        self,
        *,
        user_pool_id: str,
        client_id: str,
        region: str,
        client_secret: str | None = None,
    ) -> None:
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.region = region
        self.client_secret = client_secret
        self.pool_name = user_pool_id.split("_", 1)[1]
        self._client = boto3.client("cognito-idp", region_name=region)

        self._n = int(N_HEX, 16)
        self._g = int(G_HEX, 16)
        self._k = int.from_bytes(_hex_hash(_pad_hex(N_HEX) + _pad_hex(G_HEX)), "big")

    def _generate_a(self) -> int:
        while True:
            a = int.from_bytes(os.urandom(128), "big") % self._n
            if a % self._n != 0:
                return a

    def _secret_hash(self, username: str) -> str:
        if not self.client_secret:
            return ""
        msg = f"{username}{self.client_id}".encode("utf-8")
        dig = hmac.new(self.client_secret.encode("utf-8"), msg, hashlib.sha256).digest()
        return base64.b64encode(dig).decode("utf-8")

    def _compute_signature(
        self,
        *,
        username: str,
        password: str,
        salt_hex: str,
        srp_b_hex: str,
        secret_block: str,
        a: int,
        a_pub: int,
        timestamp: str,
    ) -> str:
        b = int(srp_b_hex, 16)
        if b % self._n == 0:
            raise SkaiAuthError("Invalid SRP_B value from Cognito")

        u = int.from_bytes(
            _hex_hash(_pad_hex(format(a_pub, "x")) + _pad_hex(srp_b_hex)), "big"
        )
        if u == 0:
            raise SkaiAuthError("Invalid SRP_U value")

        user_id_hash = _hash_sha256(
            f"{self.pool_name}{username}:{password}".encode("utf-8")
        )
        salt_bytes = _hex_to_bytes(salt_hex)
        x = int.from_bytes(_hash_sha256(salt_bytes + user_id_hash), "big")

        g_mod_pow_x = pow(self._g, x, self._n)
        int_value = (b - self._k * g_mod_pow_x) % self._n
        s = pow(int_value, a + u * x, self._n)

        hkdf = _compute_hkdf(
            _hex_to_bytes(format(s, "x")), _hex_to_bytes(format(u, "x"))
        )

        secret_block_bytes = base64.b64decode(secret_block)
        msg = (
            f"{self.pool_name}{username}".encode("utf-8")
            + secret_block_bytes
            + timestamp.encode("utf-8")
        )
        signature = hmac.new(hkdf, msg, hashlib.sha256).digest()
        return base64.b64encode(signature).decode("utf-8")

    def authenticate(self, username: str, password: str) -> CognitoTokens:
        a = self._generate_a()
        a_pub = pow(self._g, a, self._n)
        srp_a = _pad_hex(format(a_pub, "x"))

        auth_params = {"USERNAME": username, "SRP_A": srp_a}
        if self.client_secret:
            auth_params["SECRET_HASH"] = self._secret_hash(username)

        init_response = self._client.initiate_auth(
            ClientId=self.client_id,
            AuthFlow="USER_SRP_AUTH",
            AuthParameters=auth_params,
        )

        if init_response.get("ChallengeName") != "PASSWORD_VERIFIER":
            raise SkaiAuthError(
                f"Unsupported Cognito challenge: {init_response.get('ChallengeName')}"
            )

        challenge_params = init_response.get("ChallengeParameters", {})
        user_id_for_srp = challenge_params.get("USER_ID_FOR_SRP") or username
        salt_hex = challenge_params.get("SALT")
        srp_b_hex = challenge_params.get("SRP_B")
        secret_block = challenge_params.get("SECRET_BLOCK")

        if not salt_hex or not srp_b_hex or not secret_block:
            raise SkaiAuthError("Missing SRP challenge parameters from Cognito")

        timestamp = _utc_timestamp()
        signature = self._compute_signature(
            username=user_id_for_srp,
            password=password,
            salt_hex=salt_hex,
            srp_b_hex=srp_b_hex,
            secret_block=secret_block,
            a=a,
            a_pub=a_pub,
            timestamp=timestamp,
        )

        challenge_responses = {
            "USERNAME": user_id_for_srp,
            "PASSWORD_CLAIM_SECRET_BLOCK": secret_block,
            "TIMESTAMP": timestamp,
            "PASSWORD_CLAIM_SIGNATURE": signature,
        }
        if self.client_secret:
            challenge_responses["SECRET_HASH"] = self._secret_hash(username)

        auth_response = self._client.respond_to_auth_challenge(
            ClientId=self.client_id,
            ChallengeName="PASSWORD_VERIFIER",
            ChallengeResponses=challenge_responses,
        )

        result = auth_response.get("AuthenticationResult")
        if not result:
            raise SkaiAuthError(
                "Authentication failed or requires additional challenge"
            )

        return CognitoTokens(
            id_token=result.get("IdToken"),
            access_token=result.get("AccessToken"),
            refresh_token=result.get("RefreshToken"),
            expires_in=int(result.get("ExpiresIn", 3600)),
        )

    def refresh(self, refresh_token: str, username: str | None = None) -> CognitoTokens:
        auth_params = {"REFRESH_TOKEN": refresh_token}
        if self.client_secret:
            if not username:
                raise SkaiAuthError("Username required for refresh with client secret")
            auth_params["SECRET_HASH"] = self._secret_hash(username)

        response = self._client.initiate_auth(
            ClientId=self.client_id,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters=auth_params,
        )

        result = response.get("AuthenticationResult")
        if not result:
            raise SkaiAuthError("Failed to refresh Cognito tokens")

        return CognitoTokens(
            id_token=result.get("IdToken"),
            access_token=result.get("AccessToken"),
            refresh_token=None,
            expires_in=int(result.get("ExpiresIn", 3600)),
        )


class SkaiAuthService:
    """Service to manage SKAI Cognito login and token refresh."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._auth: CognitoSrpAuthenticator | None = None

    def _get_cognito_auth(self) -> CognitoSrpAuthenticator:
        if (
            self.settings.skai_cognito_region
            and self.settings.skai_cognito_user_pool_id
            and self.settings.skai_cognito_client_id
        ):
            return CognitoSrpAuthenticator(
                user_pool_id=self.settings.skai_cognito_user_pool_id,
                client_id=self.settings.skai_cognito_client_id,
                region=self.settings.skai_cognito_region,
                client_secret=self.settings.skai_cognito_client_secret,
            )

        missing = []
        if not self.settings.skai_cognito_region:
            missing.append("SKAI_COGNITO_REGION")
        if not self.settings.skai_cognito_user_pool_id:
            missing.append("SKAI_COGNITO_USER_POOL_ID")
        if not self.settings.skai_cognito_client_id:
            missing.append("SKAI_COGNITO_CLIENT_ID")
        raise SkaiAuthError("Missing SKAI Cognito configuration: " + ", ".join(missing))

    def _get_authenticator(self) -> CognitoSrpAuthenticator:
        if self._auth is None:
            self._auth = self._get_cognito_auth()

        return self._auth

    def _select_token(self, tokens: CognitoTokens) -> str | None:
        token_type = self.settings.skai_token_type.lower()
        if token_type == "id":
            return tokens.id_token
        if token_type == "access":
            return tokens.access_token
        raise SkaiAuthError(
            f"Unsupported SKAI token type: {self.settings.skai_token_type}"
        )

    async def _get_credential(self, user_id, db: AsyncSession) -> SkaiCredential | None:
        stmt = select(SkaiCredential).where(SkaiCredential.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_credentials(self, user_id, db: AsyncSession) -> SkaiCredential | None:
        return await self._get_credential(user_id, db)

    async def _authenticate_username_password(
        self, username: str, password: str
    ) -> CognitoTokens:
        """Same auth flow as POST /skai/auth/login: Cognito USER_SRP_AUTH.

        Used by login() and get_token_for_credentials() so both paths are identical.
        """
        authenticator = self._get_authenticator()
        try:
            return await asyncio.to_thread(
                authenticator.authenticate, username, password
            )
        except ClientError as exc:
            raise _map_cognito_client_error(exc) from exc

    async def login(
        self,
        *,
        user_id,
        username: str,
        password: str,
        db: AsyncSession,
    ) -> SkaiCredential:
        tokens = await self._authenticate_username_password(username, password)
        selected_token = self._select_token(tokens)
        if not selected_token:
            raise SkaiAuthError("Cognito did not return the requested token type")
        if not tokens.refresh_token:
            raise SkaiAuthError("Cognito did not return a refresh token")

        expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in)

        credential = await self._get_credential(user_id, db)
        if credential is None:
            credential = SkaiCredential(
                user_id=user_id,
                skai_username=username,
                refresh_token=tokens.refresh_token,
                id_token=selected_token,
                expires_at=expires_at,
                last_refreshed_at=datetime.now(UTC),
            )
            db.add(credential)
        else:
            credential.skai_username = username
            credential.refresh_token = tokens.refresh_token
            credential.id_token = selected_token
            credential.expires_at = expires_at
            credential.last_refreshed_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(credential)
        return credential

    async def get_token_for_credentials(self, username: str, password: str) -> str:
        """Same as POST /skai/auth/login: authenticate and return token (no DB).

        Uses _authenticate_username_password so the flow is identical to the FE login.
        """
        tokens = await self._authenticate_username_password(username, password)
        selected = self._select_token(tokens)
        if not selected:
            raise SkaiAuthError("Cognito did not return the requested token type")
        return selected

    def _infer_expires_at(self, token: str) -> datetime | None:
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            if exp:
                return datetime.fromtimestamp(exp, UTC)
        except Exception:
            return None
        return None

    async def refresh_tokens(
        self, *, credential: SkaiCredential, db: AsyncSession
    ) -> SkaiCredential:
        authenticator = self._get_authenticator()
        try:
            tokens = await asyncio.to_thread(
                authenticator.refresh,
                credential.refresh_token,
                credential.skai_username,
            )
        except ClientError as exc:
            raise _map_cognito_client_error(exc) from exc

        selected_token = self._select_token(tokens)
        if not selected_token:
            raise SkaiAuthError("Cognito did not return the requested token type")

        credential.id_token = selected_token
        credential.expires_at = datetime.now(UTC) + timedelta(seconds=tokens.expires_in)
        credential.last_refreshed_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(credential)
        return credential

    async def disconnect(self, user_id, db: AsyncSession) -> None:
        credential = await self._get_credential(user_id, db)
        if credential is None:
            raise SkaiAuthError("SKAI account not connected")
        await db.delete(credential)
        await db.commit()

    async def refresh_for_user(self, user_id, db: AsyncSession) -> SkaiCredential:
        credential = await self._get_credential(user_id, db)
        if credential is None:
            raise SkaiAuthError("SKAI account not connected", status_code=401)
        return await self.refresh_tokens(credential=credential, db=db)

    async def get_valid_id_token(self, user_id, db: AsyncSession) -> str:
        now = datetime.now(UTC)
        refresh_margin = timedelta(
            seconds=self.settings.skai_token_refresh_margin_seconds
        )
        credential = await self._get_credential(user_id, db)
        if credential is None:
            if self.settings.env == "development" and self.settings.skai_token:
                fallback_token = self.settings.skai_token
                fallback_exp = self._infer_expires_at(fallback_token)
                if fallback_exp and fallback_exp <= now + refresh_margin:
                    raise SkaiAuthError(
                        "Configured development SKAI_TOKEN is expired; reconnect SKAI or update SKAI_TOKEN.",
                        status_code=401,
                    )
                return fallback_token
            raise SkaiAuthError("SKAI account not connected", status_code=401)

        token = credential.id_token
        expires_at = credential.expires_at
        if token and not expires_at:
            expires_at = self._infer_expires_at(token)
            if expires_at:
                credential.expires_at = expires_at
                await db.commit()

        if token and expires_at and expires_at > now + refresh_margin:
            return token

        credential = await self.refresh_tokens(credential=credential, db=db)
        if not credential.id_token:
            raise SkaiAuthError("Failed to refresh SKAI token")
        return credential.id_token


@lru_cache(maxsize=1)
def get_skai_auth_service() -> SkaiAuthService:
    return SkaiAuthService(get_settings())
