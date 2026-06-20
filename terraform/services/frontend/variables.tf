# Frontend Service - Variables

# ─────────────────────────────────────────────────────────────────────────────
# Required Variables
# ─────────────────────────────────────────────────────────────────────────────

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod, or branch name)"
  type        = string
}

variable "image_url" {
  description = "Full Docker image URL (built by GitHub Actions)"
  type        = string
}

# ─────────────────────────────────────────────────────────────────────────────
# Optional Configuration
# ─────────────────────────────────────────────────────────────────────────────

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "app"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-southeast1"
}

# ─────────────────────────────────────────────────────────────────────────────
# Cloud Run Configuration
# ─────────────────────────────────────────────────────────────────────────────

variable "cpu_limit" {
  description = "CPU limit"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit"
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum instances"
  type        = number
  default     = 10
}

variable "container_concurrency" {
  description = "Max concurrent requests per instance"
  type        = number
  default     = 1000 # Higher for static serving
}

variable "timeout_seconds" {
  description = "Request timeout"
  type        = number
  default     = 60
}

# ─────────────────────────────────────────────────────────────────────────────
# Application Configuration
# ─────────────────────────────────────────────────────────────────────────────

variable "node_env" {
  description = "Node environment"
  type        = string
  default     = "production"
}
