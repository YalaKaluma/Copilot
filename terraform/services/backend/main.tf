# Backend Service Infrastructure
# Deploys: Artifact Registry + GCS Bucket + Cloud Run + Migration Job

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"
    }
  }

  # State storage in GCS bucket (configured via backend-config in CI/CD)
  backend "gcs" {
    prefix = "terraform/services/backend"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  service_name   = "${var.app_name}-backend-${var.environment}"
  sanitized_name = lower(replace(local.service_name, "_", "-"))

  # Generate unique bucket suffix
  bucket_suffix = substr(md5("${var.project_id}-${var.app_name}"), 0, 4)
  bucket_name   = "${var.app_name}-${var.environment}-${local.bucket_suffix}"

  sandbox_enabled = var.sandbox_image_url != ""
}

# Note: Artifact Registry is created by the build step via gcloud CLI
# This avoids state management conflicts with Terraform


# ─────────────────────────────────────────────────────────────────────────────
# GCS Storage Bucket
# ─────────────────────────────────────────────────────────────────────────────

module "storage" {
  source = "../../modules/gcs"

  name         = local.bucket_name
  project_id   = var.project_id
  region       = var.region
  cors_origins = var.cors_origins

  force_destroy            = var.environment != "prod"
  public_access_prevention = "enforced"

  labels = {
    environment = var.environment
    service     = "backend"
  }
}

# ─────────────────────────────────────────────────────────────────────────────
# Cloud Run Service
# ─────────────────────────────────────────────────────────────────────────────

module "cloud_run" {
  source = "../../modules/cloud-run"

  name       = local.service_name
  project_id = var.project_id
  region     = var.region
  image_url  = var.image_url
  port       = var.backend_port

  cpu_limit             = var.cpu_limit
  memory_limit          = var.memory_limit
  min_instances         = var.min_instances
  max_instances         = var.max_instances
  container_concurrency = var.container_concurrency
  timeout_seconds       = var.timeout_seconds
  cpu_idle              = true

  allow_public_access = true

  volumes = local.sandbox_enabled ? [
    {
      name = "sandbox-data"
      empty_dir = {
        medium     = "MEMORY"
        size_limit = "512Mi"
      }
    }
  ] : []

  volume_mounts = local.sandbox_enabled ? [
    {
      name       = "sandbox-data"
      mount_path = "/sandbox"
    }
  ] : []

  additional_containers = local.sandbox_enabled ? [
    {
      name       = "sandbox-executor"
      image      = var.sandbox_image_url
      cpu_limit  = "1"
      memory_limit = "1Gi"
      cpu_idle   = true
      startup_cpu_boost = false
      volume_mounts = [
        {
          name       = "sandbox-data"
          mount_path = "/sandbox"
        }
      ]
    }
  ] : []

  env_vars = merge(
    {
      ENV              = var.env
      DEBUG            = var.debug
      BACKEND_PORT     = tostring(var.backend_port)
      GCP_PROJECT_ID   = var.project_id
      STORAGE_PROVIDER = "gcp"
      GCS_BUCKET_NAME  = module.storage.name
      CORS_ORIGINS     = join(",", var.cors_origins)
      LOG_LEVEL        = var.log_level
      PYTHON_SANDBOX_SHARED_DIR = "/sandbox"
      # Migrations are enforced via dedicated Cloud Run Job in CI/CD.
      RUN_DB_MIGRATIONS_ON_STARTUP = "false"
    },
    # Only include optional vars if they're set
    var.database_url != "" ? { DATABASE_URL = var.database_url } : {},
    var.openai_api_key != "" ? { OPENAI_API_KEY = var.openai_api_key } : {},
    var.anthropic_api_key != "" ? { ANTHROPIC_API_KEY = var.anthropic_api_key } : {},
    var.gemini_api_key != "" ? { GEMINI_API_KEY = var.gemini_api_key } : {},
    var.skai_api_url != "" ? { SKAI_API_URL = var.skai_api_url } : {},
    var.skai_api_key != "" ? { SKAI_API_KEY = var.skai_api_key } : {},
    var.skai_api_origin != "" ? { SKAI_API_ORIGIN = var.skai_api_origin } : {},
    var.skai_api_referer != "" ? { SKAI_API_REFERER = var.skai_api_referer } : {},
    var.skai_api_user_agent != "" ? { SKAI_API_USER_AGENT = var.skai_api_user_agent } : {},
    var.skai_token_type != "" ? { SKAI_TOKEN_TYPE = var.skai_token_type } : {},
    var.skai_token_refresh_margin_seconds > 0 ? { SKAI_TOKEN_REFRESH_MARGIN_SECONDS = tostring(var.skai_token_refresh_margin_seconds) } : {},
    var.clerk_secret_key != "" ? { CLERK_SECRET_KEY = var.clerk_secret_key } : {},
    var.clerk_webhook_secret != "" ? { CLERK_WEBHOOK_SECRET = var.clerk_webhook_secret } : {},
    var.google_service_account_json != "" ? { GOOGLE_SERVICE_ACCOUNT_JSON = var.google_service_account_json } : {},
    # Langfuse - LLM Observability (optional)
    var.langfuse_public_key != "" ? { LANGFUSE_PUBLIC_KEY = var.langfuse_public_key } : {},
    var.langfuse_secret_key != "" ? { LANGFUSE_SECRET_KEY = var.langfuse_secret_key } : {},
    var.langfuse_public_key != "" ? { LANGFUSE_HOST = var.langfuse_host } : {},
    var.langfuse_tracing_environment != "" ? { LANGFUSE_TRACING_ENVIRONMENT = var.langfuse_tracing_environment } : {},
    # SKAI Cognito config
    var.skai_cognito_region != "" ? { SKAI_COGNITO_REGION = var.skai_cognito_region } : {},
    var.skai_cognito_user_pool_id != "" ? { SKAI_COGNITO_USER_POOL_ID = var.skai_cognito_user_pool_id } : {},
    var.skai_cognito_client_id != "" ? { SKAI_COGNITO_CLIENT_ID = var.skai_cognito_client_id } : {},
    var.skai_cognito_client_secret != "" ? { SKAI_COGNITO_CLIENT_SECRET = var.skai_cognito_client_secret } : {},
    var.extra_env_vars,
  )

  startup_probe = {
    path                  = "/api/health"
    initial_delay_seconds = 5
    timeout_seconds       = 5
    period_seconds        = 10
    # Allow extra startup time for entrypoint migrations on cold DB/network paths.
    failure_threshold = 30 # Total: 5 + (30 * 10) = 305 seconds
  }

  startup_cpu_boost = true
}

# ─────────────────────────────────────────────────────────────────────────────
# Database Migration Job
# ─────────────────────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_job" "migration" {
  count    = var.database_url != "" ? 1 : 0
  name     = "${module.cloud_run.service_name}-migration"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image       = var.image_url
        command     = ["/bin/sh"]
        args        = ["-c", ".venv/bin/alembic -c /packages/db/alembic.ini upgrade head"]
        working_dir = "/app"

        env {
          name  = "DATABASE_URL"
          value = var.database_url
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      timeout     = "300s"
      max_retries = 2
    }
  }

  depends_on = [module.cloud_run]
}
