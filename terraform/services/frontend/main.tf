# Frontend Service Infrastructure
# Deploys: Artifact Registry + Cloud Run

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
    prefix = "terraform/services/frontend"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  service_name   = "${var.app_name}-frontend-${var.environment}"
  sanitized_name = lower(replace(local.service_name, "_", "-"))
}

# Note: Artifact Registry is created by the build step via gcloud CLI
# This avoids state management conflicts with Terraform

# ─────────────────────────────────────────────────────────────────────────────
# Cloud Run Service
# ─────────────────────────────────────────────────────────────────────────────

module "cloud_run" {
  source = "../../modules/cloud-run"

  name       = local.service_name
  project_id = var.project_id
  region     = var.region
  image_url  = var.image_url
  port       = 80

  cpu_limit             = var.cpu_limit
  memory_limit          = var.memory_limit
  min_instances         = var.min_instances
  max_instances         = var.max_instances
  container_concurrency = var.container_concurrency
  timeout_seconds       = var.timeout_seconds
  cpu_idle              = false # Static serving doesn't need CPU when idle

  allow_public_access = true

  env_vars = {
    NODE_ENV = var.node_env
  }
}
