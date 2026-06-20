# GCS Bucket Module
# Reusable module for creating Google Cloud Storage buckets
#
# Usage:
#   module "storage" {
#     source      = "../../modules/gcs"
#     name        = "my-app-storage"
#     project_id  = "my-project"
#     region      = "us-central1"
#     cors_origins = ["https://example.com"]
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
  # Sanitize bucket name
  # Requirements: lowercase, numbers, hyphens, underscores; 3-63 chars; no consecutive dots
  bucket_name_raw = lower(replace(var.name, "/[^a-z0-9-_]/", "-"))
  bucket_name     = replace(local.bucket_name_raw, "--", "-")
}

resource "google_storage_bucket" "bucket" {
  name     = local.bucket_name
  location = var.region
  project  = var.project_id

  force_destroy               = var.force_destroy
  uniform_bucket_level_access = var.uniform_bucket_level_access
  public_access_prevention    = var.public_access_prevention

  # CORS configuration
  dynamic "cors" {
    for_each = length(var.cors_origins) > 0 ? [1] : []
    content {
      origin          = var.cors_origins
      method          = var.cors_methods
      response_header = var.cors_response_headers
      max_age_seconds = var.cors_max_age_seconds
    }
  }

  # Lifecycle rules (optional)
  dynamic "lifecycle_rule" {
    for_each = var.lifecycle_rules
    content {
      condition {
        age                   = lifecycle_rule.value.age
        created_before        = lifecycle_rule.value.created_before
        num_newer_versions    = lifecycle_rule.value.num_newer_versions
        matches_storage_class = lifecycle_rule.value.matches_storage_class
      }
      action {
        type          = lifecycle_rule.value.action_type
        storage_class = lifecycle_rule.value.storage_class
      }
    }
  }

  # Versioning (optional)
  versioning {
    enabled = var.versioning_enabled
  }

  # Labels
  labels = var.labels
}

# IAM bindings (optional)
resource "google_storage_bucket_iam_member" "members" {
  for_each = var.iam_members

  bucket = google_storage_bucket.bucket.name
  role   = each.value.role
  member = each.value.member
}
