"""CORS middleware configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


def setup_cors_middleware(app: FastAPI) -> None:
    """Configure CORS middleware.

    SECURITY NOTE: Default allows all origins (*) for ease of development.
    For production, set CORS_ORIGINS in GitHub variables to specific domains:
    Example: CORS_ORIGINS=https://your-app.com,https://staging.your-app.com
    """
    settings = get_settings()

    # Parse origins from settings
    origins_str = settings.cors_origins
    origins: list[str]
    if isinstance(origins_str, str):
        origins = [origin.strip() for origin in origins_str.split(",")]
    else:
        origins = origins_str if isinstance(origins_str, list) else [origins_str]

    # Log warning if using wildcard in production
    if "*" in origins and settings.env == "production":
        logger.warning(
            "⚠️  CORS is configured with wildcard (*) origins in production. "
            "This is less secure. Please set CORS_ORIGINS in GitHub variables "
            "to specific allowed domains for better security."
        )

    # If origins includes "*", we need to handle it specially
    # Note: Wildcard doesn't work with credentials, but Clerk uses Bearer tokens
    # which don't require credentials=true
    if "*" in origins:
        # Use a more permissive CORS policy without credentials
        # This is safe with Clerk since it uses Authorization headers, not cookies
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,  # Not needed for Bearer token auth
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )
    else:
        # Use specific origins - can use credentials for cookie-based auth if needed
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,  # Can enable for cookie auth if needed
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Error-Code", "WWW-Authenticate"],
        )
