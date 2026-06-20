# Cloud Run Module - Outputs

output "url" {
  description = "The URL of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.uri
}

output "service_name" {
  description = "The name of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.name
}

output "service_id" {
  description = "The full resource ID of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.id
}

output "location" {
  description = "The location of the Cloud Run service"
  value       = google_cloud_run_v2_service.service.location
}
