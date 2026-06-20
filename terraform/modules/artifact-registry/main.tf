# Artifact Registry Module
# Reusable module for creating Docker repositories in Artifact Registry
#
# Usage:
#   module "registry" {
#     source      = "../../modules/artifact-registry"
#     name        = "my-app-backend"
#     project_id  = "my-project"
#     region      = "us-central1"
#   }

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

locals {
  # Sanitize repository name for Artifact Registry
  # Requirements: lowercase letters, numbers, and hyphens only
  repository_id = lower(replace(var.name, "_", "-"))
}

resource "google_artifact_registry_repository" "repository" {
  location      = var.region
  project       = var.project_id
  repository_id = local.repository_id
  description   = var.description
  format        = var.format

  # Cleanup policies (optional)
  dynamic "cleanup_policies" {
    for_each = var.cleanup_policies
    content {
      id     = cleanup_policies.key
      action = cleanup_policies.value.action

      dynamic "condition" {
        for_each = cleanup_policies.value.condition != null ? [cleanup_policies.value.condition] : []
        content {
          tag_state             = condition.value.tag_state
          tag_prefixes          = condition.value.tag_prefixes
          older_than            = condition.value.older_than
          newer_than            = condition.value.newer_than
          version_name_prefixes = condition.value.version_name_prefixes
        }
      }

      dynamic "most_recent_versions" {
        for_each = cleanup_policies.value.most_recent_versions != null ? [cleanup_policies.value.most_recent_versions] : []
        content {
          keep_count = most_recent_versions.value.keep_count
        }
      }
    }
  }

  labels = var.labels
}

# IAM bindings (optional)
resource "google_artifact_registry_repository_iam_member" "members" {
  for_each = var.iam_members

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.repository.name
  role       = each.value.role
  member     = each.value.member
}
