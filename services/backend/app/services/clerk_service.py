# type: ignore
# TODO: fix type errors later

"""Clerk authentication service.

Handles Clerk JWT verification using the official Clerk SDK.
Based on Temasek-POC implementation with improvements.
"""

import asyncio
from datetime import datetime, timedelta, UTC
from typing import Any, cast

import httpx
import jwt
from clerk_backend_api import Clerk
from clerk_backend_api.models import ClerkError
from clerk_backend_api.security import AuthenticateRequestOptions
from fastapi import Depends

from core.config import Settings, get_settings
from core.logging import get_logger

logger = get_logger(__name__)


class ClerkService:
    """Service for Clerk authentication operations."""

    def __init__(self):
        """Initialize Clerk service."""
        self._clerk_client: Clerk | None = None
        self._initialized = False
        # JWKS caching for fallback manual verification
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_expiry: datetime | None = None
        self._jwks_cache_lock = asyncio.Lock()

    def _get_clerk_client(self) -> Clerk | None:
        """Get Clerk client instance (lazy loaded)."""
        if not self._initialized:
            settings = get_settings()

            if not settings.clerk_secret_key:
                logger.warning("Clerk secret key not configured")
                self._initialized = True  # Prevent repeated warnings
                return None

            try:
                self._clerk_client = Clerk(bearer_auth=settings.clerk_secret_key)
                self._initialized = True
                logger.info("Clerk client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Clerk client: {e}")
                self._initialized = True  # Prevent repeated attempts
                return None

        return self._clerk_client

    def is_configured(self) -> bool:
        """Check if Clerk service is properly configured."""
        return self._get_clerk_client() is not None

    async def _get_jwks_data(self) -> dict[str, Any] | None:
        """Get JWKS data with caching (5 minute cache)."""
        async with self._jwks_cache_lock:
            # Check if cache is valid
            now = datetime.now(UTC)
            if (
                self._jwks_cache is not None
                and self._jwks_cache_expiry is not None
                and now < self._jwks_cache_expiry
            ):
                logger.debug("Using cached JWKS data")
                return self._jwks_cache

            # Fetch fresh JWKS data
            try:
                # Get Clerk domain from environment or use default
                settings = get_settings()
                clerk_domain = getattr(
                    settings, "clerk_domain", "YOUR_DOMAIN.clerk.accounts.dev"
                )
                jwks_url = f"https://{clerk_domain}/.well-known/jwks.json"

                logger.debug(f"Fetching JWKS from: {jwks_url}")

                async with httpx.AsyncClient() as client:
                    response = await client.get(jwks_url, timeout=10.0)
                    if response.status_code != 200:
                        logger.error(
                            f"Failed to fetch JWKS: HTTP {response.status_code}"
                        )
                        return None

                    jwks_data = response.json()

                # Cache for 5 minutes
                self._jwks_cache = jwks_data
                self._jwks_cache_expiry = now + timedelta(minutes=5)
                logger.debug("JWKS data cached for 5 minutes")

                return jwks_data

            except Exception as e:
                logger.error(f"Error fetching JWKS data: {e}")
                return None

    async def verify_jwt(self, token: str) -> dict[str, Any] | None:
        """Verify a Clerk JWT token using the official SDK method.

        Args:
            token: The JWT token to verify

        Returns:
            Decoded JWT payload with user info if valid, None otherwise
        """
        logger.debug(f"Verifying JWT token: {token[:20]}...")

        clerk = self._get_clerk_client()
        if not clerk:
            logger.warning("Clerk client not available - missing CLERK_SECRET_KEY?")
            return None

        try:
            # Create a mock HTTP request with the authorization header
            # This is needed for the SDK's authenticate_request method
            mock_request = httpx.Request(
                method="GET",
                url="http://localhost",
                headers={"Authorization": f"Bearer {token}"},
            )

            # Try to use Clerk's built-in authentication method
            try:
                logger.debug("Using Clerk SDK authenticate_request method...")

                request_state = clerk.authenticate_request(
                    mock_request,
                    AuthenticateRequestOptions(
                        # Add authorized parties if needed
                        # authorized_parties=["http://localhost:3000"]
                    ),
                )

                if request_state.is_signed_in:
                    # this will be a dict when signed in based on pydantic validations
                    state_payload = cast(dict[str, Any], request_state.payload)
                    logger.info(
                        f"Successfully verified Clerk JWT for user: {state_payload.get('sub')}"
                    )
                    return request_state.payload
                else:
                    logger.warning(
                        f"Clerk JWT verification failed: {request_state.reason}"
                    )
                    return None

            except (ImportError, AttributeError) as e:
                logger.warning(
                    f"Clerk SDK authenticate_request not available ({e}), falling back to manual verification"
                )
                # Fall back to manual verification
                return await self._verify_jwt_manual(token)

        except Exception as e:
            logger.error(f"Error verifying Clerk JWT: {e}")
            return None

    async def _verify_jwt_manual(self, token: str) -> dict[str, Any] | None:
        """Fallback manual JWT verification method using PyJWT."""
        logger.info("Using manual JWT verification")

        try:
            # Get JWKS data
            jwks_data = await self._get_jwks_data()
            if not jwks_data:
                logger.error("Failed to get JWKS data")
                return None

            keys = jwks_data.get("keys", [])

            if not keys:
                logger.error("No JWKS keys found")
                return None

            # Decode the token header to get the key ID
            try:
                token_header = jwt.get_unverified_header(token)
                expected_kid = token_header.get("kid")
                logger.debug(f"JWT token expects key ID: {expected_kid}")
            except Exception as e:
                logger.warning(f"Could not decode JWT header: {e}")
                expected_kid = None

            # Try each key until one works
            for key_data in keys:
                try:
                    # Skip if not the expected key
                    if expected_kid and key_data.get("kid") != expected_kid:
                        continue

                    key_id = key_data.get("kid")
                    logger.debug(f"Trying JWKS key ID: {key_id}")

                    # Convert JWKS key to PEM format for PyJWT
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)

                    # Decode and verify the JWT
                    payload = jwt.decode(
                        token,
                        public_key,
                        algorithms=["RS256"],
                        options={"verify_aud": False},  # Clerk uses azp instead of aud
                    )

                    # Verify authorized parties (azp) if present
                    settings = get_settings()
                    if settings.env == "production":
                        azp = payload.get("azp")
                        allowed_origins = [
                            "http://localhost:3000",
                            "https://yourdomain.com",
                        ]
                        if azp and azp not in allowed_origins:
                            logger.warning(f"Unauthorized party: {azp}")
                            continue

                    logger.info(
                        f"Successfully verified JWT manually for user: {payload.get('sub')}"
                    )
                    return payload

                except jwt.ExpiredSignatureError:
                    logger.warning("Token has expired")
                    return None
                except jwt.InvalidTokenError as e:
                    logger.debug(f"Token verification failed with key {key_id}: {e}")
                    continue
                except Exception as e:
                    logger.debug(f"Error with key {key_id}: {e}")
                    continue

            logger.warning("No valid key found for JWT verification")
            return None

        except Exception as e:
            logger.error(f"Error in manual JWT verification: {e}")
            return None

    async def create_testing_token(self) -> dict | None:
        """Create a Clerk testing token for development.

        Uses Clerk's official testing tokens API.

        Returns:
            Token data with token string and expiration
        """
        clerk = self._get_clerk_client()
        if not clerk:
            logger.error("Clerk client not available")
            return None

        try:
            # Use Clerk's testing tokens API
            testing_token = clerk.testing_tokens.create()

            if not testing_token or not testing_token.token:
                logger.error("Failed to generate testing token")
                return None

            logger.info(
                f"Generated testing token (expires at: {testing_token.expires_at})"
            )

            return {
                "token": testing_token.token,
                "expires_at": testing_token.expires_at,
            }

        except ClerkError as e:
            logger.error(f"Clerk API error creating testing token: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating testing token: {e}")
            return None


def get_clerk_service(settings: Settings = Depends(get_settings)) -> ClerkService:
    """Create Clerk service instance with dependency injection.

    FastAPI will cache this per request, so we don't create multiple instances
    within the same request context.

    Args:
        settings: Application settings injected by FastAPI

    Returns:
        ClerkService instance configured with current settings
    """
    return ClerkService()
