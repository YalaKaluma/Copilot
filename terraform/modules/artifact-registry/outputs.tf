# Artifact Registry Module - Outputs

output "name" {
  description = "The repository name"
  value       = google_artifact_registry_repository.repository.name
}

output "id" {
  description = "The repository ID"
  value       = google_artifact_registry_repository.repository.id
}

output "repository_url" {
  description = "The repository URL for Docker images"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repository.name}"
}

output "image_prefix" {
  description = "The prefix for Docker images (use: image_prefix/image-name:tag)"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repository.name}"
}
