"""Custom OpenAPI configuration for enhanced documentation."""

import os
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def custom_openapi(app: FastAPI) -> dict[str, Any]:
    """Generate custom OpenAPI schema with enhanced configuration.

    Adds:
    - Security schemes for authentication
    - Better organization with tags
    - Contact and license information
    - Enhanced descriptions
    """
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )

    # Update the auto-generated HTTPBearer security scheme with better description
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    if "securitySchemes" not in openapi_schema["components"]:
        openapi_schema["components"]["securitySchemes"] = {}

    # Update the HTTPBearer scheme if it exists, otherwise create it
    openapi_schema["components"]["securitySchemes"]["HTTPBearer"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "JWT token. In dev: use /api/dev/auth/token. Format: 'Bearer <token>'",
    }

    # Add servers for different environments
    servers = []

    # Check if running on Cloud Run - it sets K_SERVICE env var
    if os.getenv("K_SERVICE"):
        # On Cloud Run, we can't easily determine the exact URL
        # But we can provide a placeholder that users can update
        servers.append(
            {
                "url": "/",
                "description": "Current server (relative URL)",
            }
        )
    else:
        # Local development
        servers.append(
            {
                "url": "http://localhost:8080",
                "description": "Local development server",
            }
        )

    openapi_schema["servers"] = servers

    # Cache the schema
    app.openapi_schema = openapi_schema
    return app.openapi_schema


# Tag metadata for better organization
OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "Health check endpoints for monitoring and readiness",
    },
    {
        "name": "Users",
        "description": "User management and profile operations",
    },
    {
        "name": "OpenAI",
        "description": "AI chat, text generation, and model management",
    },
    {
        "name": "Webhooks",
        "description": "Clerk webhook integration for user sync",
    },
    {
        "name": "SKAI Auth",
        "description": "SKAI Cognito login and token refresh for per-user access",
    },
    {
        "name": "Development",
        "description": "Development tools for testing (only available in dev mode)",
    },
]
