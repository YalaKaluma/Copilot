# Artifact Registry Module - Variables

variable "name" {
  description = "Repository name (will be sanitized)"
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

variable "description" {
  description = "Repository description"
  type        = string
  default     = "Docker repository"
}

variable "format" {
  description = "Repository format (DOCKER, MAVEN, NPM, etc.)"
  type        = string
  default     = "DOCKER"
}

variable "cleanup_policies" {
  description = "Cleanup policies for the repository"
  type = map(object({
    action = string
    condition = optional(object({
      tag_state             = optional(string)
      tag_prefixes          = optional(list(string))
      older_than            = optional(string)
      newer_than            = optional(string)
      version_name_prefixes = optional(list(string))
    }))
    most_recent_versions = optional(object({
      keep_count = number
    }))
  }))
  default = {}
}

variable "labels" {
  description = "Labels to apply to the repository"
  type        = map(string)
  default     = {}
}

variable "iam_members" {
  description = "IAM members to grant access to the repository"
  type = map(object({
    role   = string
    member = string
  }))
  default = {}
}
