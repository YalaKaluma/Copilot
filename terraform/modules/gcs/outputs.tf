# GCS Bucket Module - Outputs

output "name" {
  description = "The name of the bucket"
  value       = google_storage_bucket.bucket.name
}

output "url" {
  description = "The GCS URL of the bucket"
  value       = "gs://${google_storage_bucket.bucket.name}"
}

output "self_link" {
  description = "The self link of the bucket"
  value       = google_storage_bucket.bucket.self_link
}
