# Cloud Run Module
# Reusable module for deploying containerized services to Cloud Run
#
# Usage:
#   module "backend" {
#     source    = "../../modules/cloud-run"
#     name      = "my-backend"
#     image_url = "us-docker.pkg.dev/my-project/my-repo/my-image:abc123"
#     ...
#   }

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0"
    }
  }
}

locals {
  # Sanitize service name for Cloud Run
  # Requirements: lowercase, digits, hyphens only; must begin with letter; cannot end with hyphen; < 50 chars
  name_raw = lower(replace(var.name, "_", "-"))

  # Replace invalid characters with hyphens
  name_with_hyphens = join("", [
    for seq in regexall("[a-z0-9-]+|[^a-z0-9-]+", local.name_raw) :
    length(regexall("[^a-z0-9-]", seq)) > 0 ? "-" : seq
  ])

  # Trim leading/trailing hyphens
  name_trimmed = trim(local.name_with_hyphens, "-")

  # Ensure it starts with a letter
  first_char         = length(local.name_trimmed) > 0 ? substr(local.name_trimmed, 0, 1) : ""
  starts_with_letter = can(regex("^[a-z]", local.first_char))
  name_prefixed      = local.starts_with_letter ? local.name_trimmed : "svc-${local.name_trimmed}"

  # Truncate to 50 characters and remove trailing hyphens
  name_truncated = trimsuffix(substr(local.name_prefixed, 0, min(50, length(local.name_prefixed))), "-")

  # Final service name with fallback
  service_name = length(local.name_truncated) > 0 ? local.name_truncated : "svc-${substr(var.name, 0, 8)}"
}

# Cloud Run service
resource "google_cloud_run_v2_service" "service" {
  name     = local.service_name
  location = var.region
  project  = var.project_id
  deletion_protection = false

  template {
    service_account = var.service_account_email

    dynamic "volumes" {
      for_each = var.volumes
      content {
        name = volumes.value.name

        dynamic "empty_dir" {
          for_each = volumes.value.empty_dir != null ? [volumes.value.empty_dir] : []
          content {
            medium     = try(empty_dir.value.medium, null)
            size_limit = try(empty_dir.value.size_limit, null)
          }
        }
      }
    }

    # GPU configuration via node selector (requires provider >= 6.0)
    dynamic "node_selector" {
      for_each = var.gpu_type != null ? [1] : []
      content {
        accelerator = var.gpu_type
      }
    }

    containers {
      name  = "app"
      image = var.image_url

      ports {
        container_port = var.port
      }

      # Environment variables
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Secret environment variables (from Secret Manager)
      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret_name
              version = env.value.version
            }
          }
        }
      }

      resources {
        limits = merge(
          {
            cpu    = var.cpu_limit
            memory = var.memory_limit
          },
          # GPU configuration via resource limits
          var.gpu_type != null ? { "nvidia.com/gpu" = tostring(var.gpu_count) } : {}
        )
        cpu_idle          = var.cpu_idle
        startup_cpu_boost = var.startup_cpu_boost
      }

      dynamic "volume_mounts" {
        for_each = var.volume_mounts
        content {
          name       = volume_mounts.value.name
          mount_path = volume_mounts.value.mount_path
        }
      }

      # Startup probe (optional)
      dynamic "startup_probe" {
        for_each = var.startup_probe != null ? [var.startup_probe] : []
        content {
          http_get {
            path = startup_probe.value.path
            port = var.port
          }
          initial_delay_seconds = startup_probe.value.initial_delay_seconds
          timeout_seconds       = startup_probe.value.timeout_seconds
          period_seconds        = startup_probe.value.period_seconds
          failure_threshold     = startup_probe.value.failure_threshold
        }
      }

      # Liveness probe (optional)
      dynamic "liveness_probe" {
        for_each = var.liveness_probe != null ? [var.liveness_probe] : []
        content {
          http_get {
            path = liveness_probe.value.path
            port = var.port
          }
          initial_delay_seconds = liveness_probe.value.initial_delay_seconds
          timeout_seconds       = liveness_probe.value.timeout_seconds
          period_seconds        = liveness_probe.value.period_seconds
          failure_threshold     = liveness_probe.value.failure_threshold
        }
      }
    }

    dynamic "containers" {
      for_each = var.additional_containers
      content {
        name  = containers.value.name
        image = containers.value.image
        command = try(containers.value.command, null)
        args    = try(containers.value.args, null)
        depends_on = try(containers.value.depends_on, [])

        dynamic "env" {
          for_each = try(containers.value.env_vars, {})
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = try(containers.value.secret_env_vars, {})
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value.secret_name
                version = env.value.version
              }
            }
          }
        }

        resources {
          limits = {
            cpu    = containers.value.cpu_limit
            memory = containers.value.memory_limit
          }
          cpu_idle          = containers.value.cpu_idle
          startup_cpu_boost = containers.value.startup_cpu_boost
        }

        dynamic "volume_mounts" {
          for_each = try(containers.value.volume_mounts, [])
          content {
            name       = volume_mounts.value.name
            mount_path = volume_mounts.value.mount_path
          }
        }
      }
    }

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Disable GPU zonal redundancy (no quota for redundant GPUs)
    gpu_zonal_redundancy_disabled = var.gpu_type != null ? true : null

    max_instance_request_concurrency = var.container_concurrency
    timeout                          = "${var.timeout_seconds}s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    ignore_changes = [
      client,
      client_version,
    ]
  }
}

# Public access (optional)
resource "google_cloud_run_service_iam_binding" "public" {
  count = var.allow_public_access ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_service.service.location
  service  = google_cloud_run_v2_service.service.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}
