# Backend Service - Outputs

output "backend_url" {
  description = "Backend service URL"
  value       = module.cloud_run.url
}

output "service_name" {
  description = "Cloud Run service name"
  value       = module.cloud_run.service_name
}

output "image_url" {
  description = "Deployed image URL"
  value       = var.image_url
}

output "registry_url" {
  description = "Artifact Registry repository URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${local.sanitized_name}"
}

output "storage_bucket_name" {
  description = "GCS storage bucket name"
  value       = module.storage.name
}

output "storage_bucket_url" {
  description = "GCS storage bucket URL"
  value       = module.storage.url
}

output "database_url" {
  description = "Database URL (for state retrieval)"
  value       = var.database_url
  sensitive   = true
}

output "migration_job_name" {
  description = "Migration job name"
  value       = length(google_cloud_run_v2_job.migration) > 0 ? google_cloud_run_v2_job.migration[0].name : null
}
