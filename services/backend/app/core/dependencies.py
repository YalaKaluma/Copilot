"""FastAPI dependency injection setup.

Provides common dependencies for authentication, database sessions, and services.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from core.config import get_settings
from core.logging import get_logger
from packages.db import get_db
from core.model_registry import ModelRegistry, get_model_registry
from services.user_service import UserService, get_user_service
from services.clerk_service import ClerkService, get_clerk_service
from services.llm import LLMService, get_llm_service
from services.orchestrator_service import OrchestratorService, get_orchestrator_service
from services.conversation_service import ConversationService, get_conversation_service
from services.project_service import ProjectService, get_project_service
from services.template_service import TemplateService, get_template_service
from services.skai_auth_service import (
    SkaiAuthService,
    SkaiAuthError,
    get_skai_auth_service,
)
from services.skai_api import SKAIApi
from services.skai_api_v2.client import SkaiApiV2Client

logger = get_logger(__name__)


# Helper functions for token detection
def _is_jwt_token(token: str) -> bool:
    """Check if token is in JWT format (3 segments separated by dots)."""
    return len(token.split(".")) == 3


def _is_testing_token(token: str) -> bool:
    """Check if token is a Clerk testing token (timestamp-token_string format)."""
    return "-" in token and not _is_jwt_token(token) and token.split("-")[0].isdigit()


def _is_dev_token(token: str) -> bool:
    """Check if token is a dev token (created by our dev endpoint)."""
    try:
        # Dev tokens are JWTs with iss="dev-token-generator"
        if not _is_jwt_token(token):
            return False

        # Decode without verification to check issuer
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("iss") == "dev-token-generator"
    except Exception:
        return False


# Security scheme for Swagger UI
security = HTTPBearer(
    description="JWT token. In dev: use /api/dev/auth/token. Format: 'Bearer <token>'"
)


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify authentication token from Authorization header.

    Supports multiple token types:
    1. Clerk JWT tokens (production)
    2. Clerk testing tokens (development)
    3. Dev tokens from /api/dev/auth/token (development)

    Args:
        credentials: HTTP Bearer credentials from Authorization header
        db: Database session for user lookup

    Returns:
        dict: Token payload with user information

    Raises:
        HTTPException: If token is invalid or missing
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the token from credentials
    token = credentials.credentials

    settings = get_settings()
    clerk_service = get_clerk_service()

    # Detect token type
    is_jwt = _is_jwt_token(token)
    is_testing = _is_testing_token(token)
    is_dev = _is_dev_token(token)

    logger.debug(f"Token type - JWT: {is_jwt}, Testing: {is_testing}, Dev: {is_dev}")

    # Handle dev tokens (only in development)
    if is_dev and settings.env == "development":
        try:
            # Verify dev token
            dev_secret = settings.clerk_secret_key or "dev_secret_key_for_testing_only"
            payload = jwt.decode(token, dev_secret, algorithms=["HS256"])

            logger.info(f"Dev token verified for user: {payload.get('sub')}")

            # Get or create user
            user_service = get_user_service()
            user = await user_service.create_or_get_user(
                clerk_user_id=payload.get("sub", "dev_user"), db=db
            )

            return {
                "type": "dev",
                "user_id": payload.get("sub", "dev_user"),
                "email": payload.get("email", "dev@example.com"),
                "user": user,
                "jwt_payload": payload,
            }

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dev token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid dev token: {e}")
            # Continue to try other methods

    # Handle Clerk testing tokens (only in development)
    if is_testing and settings.env == "development":
        logger.info("Accepted Clerk testing token for development")

        # Create or get testing user
        testing_user_id = "testing_token_user"
        user_service = get_user_service()
        user = await user_service.create_or_get_user(testing_user_id, db)

        return {
            "type": "testing",
            "user_id": testing_user_id,
            "user": user,
            "jwt_payload": {"sub": testing_user_id, "testing": True},
        }

    # Handle Clerk JWT tokens
    if is_jwt and clerk_service.is_configured():
        jwt_payload = await clerk_service.verify_jwt(token)
        if jwt_payload:
            clerk_user_id = jwt_payload.get("sub")
            if clerk_user_id:
                # Get or create user
                user_service = get_user_service()
                user = await user_service.create_or_get_user(clerk_user_id, db)

                logger.info(f"Clerk JWT verified for user: {clerk_user_id}")
                return {
                    "type": "clerk",
                    "user_id": clerk_user_id,
                    "user": user,
                    "jwt_payload": jwt_payload,
                }

    # If we're in debug mode and no valid token found, allow mock auth
    if settings.debug:
        logger.warning("Using mock authentication in debug mode")

        # Get or create mock user
        mock_user_id = "mock_user_123"
        user_service = get_user_service()
        user = await user_service.create_or_get_user(mock_user_id, db)

        return {
            "type": "mock",
            "user_id": mock_user_id,
            "email": "mock@example.com",
            "user": user,
        }

    # No valid authentication found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Type aliases for dependency injection
DatabaseDep = Annotated[AsyncSession, Depends(get_db)]
AuthTokenDep = Annotated[dict, Depends(verify_clerk_token)]
SettingsDep = Annotated[object, Depends(get_settings)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
LLMServiceDep = Annotated[LLMService, Depends(get_llm_service)]
ModelRegistryDep = Annotated[ModelRegistry, Depends(get_model_registry)]
ClerkServiceDep = Annotated[ClerkService, Depends(get_clerk_service)]
OrchestratorServiceDep = Annotated[
    OrchestratorService, Depends(get_orchestrator_service)
]
SkaiAuthServiceDep = Annotated[SkaiAuthService, Depends(get_skai_auth_service)]
ConversationServiceDep = Annotated[
    ConversationService, Depends(get_conversation_service)
]
ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]
TemplateServiceDep = Annotated[TemplateService, Depends(get_template_service)]


def _build_skai_extra_headers() -> dict[str, str]:
    settings = get_settings()
    extra_headers: dict[str, str] = {}
    if settings.skai_api_origin:
        extra_headers["Origin"] = settings.skai_api_origin
    if settings.skai_api_referer:
        extra_headers["Referer"] = settings.skai_api_referer
    if settings.skai_api_user_agent:
        extra_headers["User-Agent"] = settings.skai_api_user_agent
    return extra_headers


async def _get_user_skai_token(
    auth: dict = Depends(verify_clerk_token),
    db: AsyncSession = Depends(get_db),
    skai_auth_service: SkaiAuthService = Depends(get_skai_auth_service),
) -> str:
    """Get a valid user-scoped SKAI token for the current request."""

    user = auth.get("user")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in token",
        )

    try:
        token = await skai_auth_service.get_valid_id_token(user.id, db)
    except SkaiAuthError as e:
        error_code = (
            "SKAI_AUTH_REQUIRED"
            if e.status_code == status.HTTP_401_UNAUTHORIZED
            else (
                "SKAI_AUTH_RATE_LIMITED"
                if e.status_code == status.HTTP_429_TOO_MANY_REQUESTS
                else "SKAI_AUTH_ERROR"
            )
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=str(e),
            headers={"X-Error-Code": error_code},
        )
    return token


async def get_skai_api_for_user(
    auth: dict = Depends(verify_clerk_token),
    db: AsyncSession = Depends(get_db),
    skai_auth_service: SkaiAuthService = Depends(get_skai_auth_service),
) -> SKAIApi:
    """Get a SKAI API client configured with the current user's token.

    Fetches a valid token eagerly and passes it as a static auth_token.
    Cognito tokens last ~1 hour which is sufficient for any single request
    lifecycle including SSE streaming sessions.
    """
    token = await _get_user_skai_token(auth, db, skai_auth_service)

    settings = get_settings()
    return SKAIApi(
        base_url=settings.skai_api_url,
        api_key=settings.skai_api_key,
        extra_headers=_build_skai_extra_headers(),
        auth_token=token,
    )


SkaiApiUserDep = Annotated[SKAIApi, Depends(get_skai_api_for_user)]


async def get_skai_api_v2_for_user(
    auth: dict = Depends(verify_clerk_token),
    db: AsyncSession = Depends(get_db),
    skai_auth_service: SkaiAuthService = Depends(get_skai_auth_service),
) -> SkaiApiV2Client:
    """Get a SKAI API v2 client configured with the current user's token."""
    token = await _get_user_skai_token(auth, db, skai_auth_service)

    settings = get_settings()
    return SkaiApiV2Client(
        base_url=settings.skai_api_v2_url or settings.skai_api_url,
        api_key=settings.skai_api_key,
        extra_headers=_build_skai_extra_headers(),
        auth_token=token,
    )
