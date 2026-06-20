"""Application configuration using Pydantic Settings"""

from datetime import datetime
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    env: str = Field(default="development", description="Environment")
    debug: bool = Field(default=False, description="Debug mode")
    port: int = Field(default=8080, description="Server port", alias="PORT")
    backend_port: int = Field(
        default=8080, description="Backend port (deprecated, use port)"
    )

    # Database
    database_url: str | None = Field(default=None, description="PostgreSQL URL")

    # CORS - stored as string, converted to list
    cors_origins: str = Field(
        default="http://localhost:3000", description="Comma-separated CORS origins"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Clerk Authentication
    clerk_secret_key: str | None = Field(default=None, description="Clerk secret key")
    clerk_webhook_secret: str | None = Field(
        default=None, description="Clerk webhook secret"
    )

    # LLM Providers
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(
        default=None, description="Anthropic API key for Claude models"
    )
    gemini_api_key: str | None = Field(
        default=None, description="Google Gemini API key"
    )

    # Langfuse - LLM Observability (optional)
    langfuse_public_key: str | None = Field(
        default=None, description="Langfuse public key"
    )
    langfuse_secret_key: str | None = Field(
        default=None, description="Langfuse secret key"
    )
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", description="Langfuse host URL"
    )

    # Storage Configuration
    storage_provider: str = Field(
        default="gcp", description="Storage provider (gcp, aws, azure)"
    )
    gcp_project_id: str | None = Field(default=None, description="GCP project ID")
    gcs_bucket_name: str = Field(default="test-bucket", description="GCS bucket name")
    storage_env_prefix: str | None = Field(
        default=None, description="Storage environment prefix"
    )

    # SKAI API Configuration
    skai_api_url: str = Field(
        default="http://localhost:8000", description="SKAI API base URL"
    )
    skai_api_v2_url: str | None = Field(
        default=None,
        description="SKAI API v2 base URL. Defaults to skai_api_url when unset.",
    )
    skai_api_key: str | None = Field(
        default=None, description="SKAI API key for authentication"
    )
    skai_token: str | None = Field(
        default=None, description="SKAI bearer token for authentication"
    )
    skai_api_origin: str | None = Field(
        default=None, description="Origin header for SKAI API requests"
    )
    skai_api_referer: str | None = Field(
        default=None, description="Referer header for SKAI API requests"
    )
    skai_api_user_agent: str | None = Field(
        default=None, description="User-Agent header for SKAI API requests"
    )
    skai_token_type: str = Field(
        default="id",
        description="Which Cognito token to use for SKAI API: id or access",
    )
    skai_token_refresh_margin_seconds: int = Field(
        default=300,
        description="Refresh SKAI token if expiring within this many seconds",
    )
    skai_cognito_region: str | None = Field(
        default=None, description="AWS region for SKAI Cognito user pool"
    )
    skai_cognito_user_pool_id: str | None = Field(
        default=None, description="SKAI Cognito User Pool ID"
    )
    skai_cognito_client_id: str | None = Field(
        default=None, description="SKAI Cognito App Client ID"
    )
    skai_cognito_client_secret: str | None = Field(
        default=None, description="SKAI Cognito App Client Secret (optional)"
    )
    skai_user_name: str | None = Field(
        default=None,
        description="SKAI username for eval/script auth (e.g. evaluations)",
    )
    skai_password: str | None = Field(
        default=None, description="SKAI password for eval/script auth"
    )

    # Copilot versioning (config/versions/{id}.yaml)
    skai_copilot_version: str = Field(
        default="v9-dev",
        description="Active copilot version id (e.g. v1, v2); loads from config/versions/{id}.yaml",
    )
    timestamp_override: str | None = Field(
        default="2025-12-22",  # TODO: remove this once we have a different dataset
        description="Override the timestamp for the copilot run",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    # TODO: this should be dynamic based on model context window, etc
    skai_max_data_items: int = Field(
        default=100,
        description=("Max data items before truncating and adding detailed summary"),
    )

    def get_cors_origins(self) -> list[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.env == "development"

    @property
    def timestamp(self) -> str:
        """Get the timestamp for the copilot run."""
        return self.timestamp_override or datetime.now().date().isoformat()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_storage_bucket_name() -> str:
    """Get the storage bucket name from settings."""
    return get_settings().gcs_bucket_name
