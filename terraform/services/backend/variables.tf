# Backend Service - Variables

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

variable "sandbox_image_url" {
  description = "Full Docker image URL for the sandbox executor sidecar"
  type        = string
  default     = ""
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

variable "backend_port" {
  description = "Backend service port"
  type        = number
  default     = 8080
}

variable "cpu_limit" {
  description = "CPU limit"
  type        = string
  default     = "1"
}

variable "memory_limit" {
  description = "Memory limit"
  type        = string
  default     = "2Gi"
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
  default     = 100
}

variable "timeout_seconds" {
  description = "Request timeout"
  type        = number
  default     = 300
}

# ─────────────────────────────────────────────────────────────────────────────
# Application Configuration
# ─────────────────────────────────────────────────────────────────────────────

variable "env" {
  description = "Application environment (development, staging, production)"
  type        = string
  default     = "production"
}

variable "debug" {
  description = "Debug mode"
  type        = string
  default     = "false"
}

variable "log_level" {
  description = "Log level"
  type        = string
  default     = "INFO"
}

variable "cors_origins" {
  description = "CORS allowed origins"
  type        = list(string)
  default     = ["*"]
}

# ─────────────────────────────────────────────────────────────────────────────
# Secrets (passed via TF_VAR_* environment variables)
# ─────────────────────────────────────────────────────────────────────────────

variable "database_url" {
  description = "Database connection URL"
  type        = string
  sensitive   = true
  default     = ""
}


variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Google Gemini API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "skai_api_url" {
  description = "SKAI API base URL"
  type        = string
  default     = ""
}

variable "skai_api_key" {
  description = "SKAI API key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "skai_api_origin" {
  description = "Origin header for SKAI API requests"
  type        = string
  default     = ""
}

variable "skai_api_referer" {
  description = "Referer header for SKAI API requests"
  type        = string
  default     = ""
}

variable "skai_api_user_agent" {
  description = "User-Agent header for SKAI API requests"
  type        = string
  default     = ""
}

variable "skai_token_type" {
  description = "Which Cognito token to use for SKAI API: id or access"
  type        = string
  default     = "id"
}

variable "skai_token_refresh_margin_seconds" {
  description = "Refresh SKAI token if expiring within this many seconds"
  type        = number
  default     = 300
}

variable "clerk_secret_key" {
  description = "Clerk secret key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "clerk_webhook_secret" {
  description = "Clerk webhook secret"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_service_account_json" {
  description = "Service account JSON for GCS signed URLs"
  type        = string
  sensitive   = true
  default     = ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Langfuse - LLM Observability (Optional)
# ─────────────────────────────────────────────────────────────────────────────

variable "langfuse_public_key" {
  description = "Langfuse public key (optional - enables LLM tracing)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "langfuse_secret_key" {
  description = "Langfuse secret key (optional - enables LLM tracing)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "langfuse_host" {
  description = "Langfuse host URL"
  type        = string
  default     = "https://cloud.langfuse.com"
}

variable "langfuse_tracing_environment" {
  description = "Langfuse tracing environment (e.g. production, staging) for filtering in Langfuse UI"
  type        = string
  default     = "staging"
}


# ─────────────────────────────────────────────────────────────────────────────
# SKAI Cognito Configuration
# ─────────────────────────────────────────────────────────────────────────────

variable "skai_cognito_region" {
  description = "AWS region for SKAI Cognito user pool"
  type        = string
  default     = ""
}

variable "skai_cognito_user_pool_id" {
  description = "SKAI Cognito User Pool ID"
  type        = string
  default     = ""
}

variable "skai_cognito_client_id" {
  description = "SKAI Cognito App Client ID"
  type        = string
  default     = ""
}

variable "skai_cognito_client_secret" {
  description = "SKAI Cognito App Client Secret (optional)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "extra_env_vars" {
  description = "Additional environment variables"
  type        = map(string)
  default     = {}
}
