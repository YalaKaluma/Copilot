# Frontend Service - Outputs

output "frontend_url" {
  description = "Frontend service URL"
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
