# GCS Bucket Module - Variables

variable "name" {
  description = "Bucket name (will be sanitized)"
  type        = string
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "force_destroy" {
  description = "Allow bucket to be destroyed even if not empty"
  type        = bool
  default     = false
}

variable "uniform_bucket_level_access" {
  description = "Enable uniform bucket-level access"
  type        = bool
  default     = true
}

variable "public_access_prevention" {
  description = "Public access prevention setting (enforced, inherited)"
  type        = string
  default     = "enforced"
}

# CORS Configuration
variable "cors_origins" {
  description = "CORS allowed origins"
  type        = list(string)
  default     = []
}

variable "cors_methods" {
  description = "CORS allowed methods"
  type        = list(string)
  default     = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
}

variable "cors_response_headers" {
  description = "CORS response headers"
  type        = list(string)
  default     = ["*"]
}

variable "cors_max_age_seconds" {
  description = "CORS max age in seconds"
  type        = number
  default     = 3600
}

# Lifecycle Rules
variable "lifecycle_rules" {
  description = "Lifecycle rules for the bucket"
  type = list(object({
    age                   = optional(number)
    created_before        = optional(string)
    num_newer_versions    = optional(number)
    matches_storage_class = optional(list(string))
    action_type           = string
    storage_class         = optional(string)
  }))
  default = []
}

# Versioning
variable "versioning_enabled" {
  description = "Enable object versioning"
  type        = bool
  default     = false
}

# Labels
variable "labels" {
  description = "Labels to apply to the bucket"
  type        = map(string)
  default     = {}
}

# IAM
variable "iam_members" {
  description = "IAM members to grant access to the bucket"
  type = map(object({
    role   = string
    member = string
  }))
  default = {}
}
