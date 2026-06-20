"""FastAPI Application with Dependency Injection and Best Practices."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import APIRouter, FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse

from core.config import get_settings
from core.database import init_database
from core.exception_handlers import setup_exception_handlers
from core.logging import get_logger
from packages.db import close_database
from core.openapi import custom_openapi, OPENAPI_TAGS
from middleware.cors import setup_cors_middleware
from middleware.logging import setup_logging_middleware
from routers import (
    health,
    users,
    orchestrator,
    feedback,
    skai,
    skai_auth,
    conversations,
    projects,
    templates,
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting FastAPI Backend...")
    settings = get_settings()

    # Initialize database
    try:
        if settings.database_url:
            logger.info("Initializing database connection...")
            await init_database()
            logger.info("✅ Database initialized successfully")
        else:
            logger.warning("⚠️ No DATABASE_URL configured - running without database")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        # Allow app to start without database for development
        if settings.env == "production":
            raise

    # Services are now initialized via dependency injection on first use
    logger.info("✅ Services configured for dependency injection")

    # Log Langfuse status
    from packages.langfuse import log_status as langfuse_log_status

    langfuse_log_status()

    yield

    # Shutdown
    logger.info("Shutting down FastAPI Backend...")
    await close_database()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Full Stack Template API",
        description="Production-ready backend with OpenAI integration, Clerk auth, Neon PostgreSQL, and best practices",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_tags=OPENAPI_TAGS,
    )

    # Middleware
    setup_cors_middleware(app)
    setup_logging_middleware(app)

    if settings.env == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

    # Exception handlers
    setup_exception_handlers(app)

    # Create API router with /api prefix
    api_router = APIRouter(prefix="/api")

    # Add all routes under /api
    api_router.include_router(health.router)
    api_router.include_router(users.router, prefix="/users")
    api_router.include_router(orchestrator.router, prefix="/orchestrator")
    api_router.include_router(feedback.router, prefix="/orchestrator")
    api_router.include_router(skai.router)
    api_router.include_router(skai_auth.router)
    api_router.include_router(conversations.router)
    api_router.include_router(projects.router)
    api_router.include_router(templates.router)
    # Add development routes if in development mode
    if settings.env == "development" or settings.env == "staging":
        from routers import prompt_optimizer

        api_router.include_router(prompt_optimizer.router)
        logger.info("✅ Prompt optimizer routes enabled at /api/prompt-optimizer")

    # Mount the API router
    app.include_router(api_router)

    # Root redirect to docs
    @app.get("/", include_in_schema=False)
    async def root():
        """Redirect root to API documentation."""
        return RedirectResponse(url="/docs")

    # Set custom OpenAPI schema
    app.openapi = lambda: custom_openapi(app)

    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        loop="asyncio",
    )
