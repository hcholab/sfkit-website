variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "service_region" {
  description = "GCP region for Cloud Run service"
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "sfkit-website"
}

variable "frontend_service_name" {
  description = "Cloud Run service name for the frontend"
  type        = string
  default     = "sfkit-react"
}

variable "artifact_repository" {
  description = "Artifact Registry repository ID"
  type        = string
  default     = "us.gcr.io"
}

variable "image" {
  description = "Full container image URI"
  type        = string
}

variable "database_name" {
  description = "Firestore database name"
  type        = string
  default     = "sfkit"
}

variable "database_region" {
  description = "Firestore database region"
  type        = string
  default     = "us-central1"
}

variable "results_bucket" {
  description = "GCS bucket name for study results"
  type        = string
}

variable "storage_region" {
  description = "GCS bucket region"
  type        = string
  default     = "us-central1"
}

variable "cors_origins" {
  description = "Comma-separated allowed CORS origins"
  type        = string
  default     = ""
}

variable "flask_debug" {
  description = "Flask debug mode (1 / 0)"
  type        = number
  default     = 0
}

variable "oidc_audience" {
  description = "OIDC audience (for example, Google or Azure B2C client ID)."
  type        = string
}

variable "oidc_jwks_url" {
  description = "OIDC JWKS URL"
  type        = string
  default     = ""
}

variable "sfkit_proxy_args" {
  description = "Arguments to pass to the sfkit proxy"
  type        = string
  default     = "-v"
}

variable "sfkit_cli_image" {
  description = "Full sfkit CLI Docker image URI"
  type        = string
  default     = "ghcr.io/hcholab/sfkit"
}

variable "turn_port" {
  description = "TURN server port"
  type        = number
  default     = 15830
}

variable "vpc_flow_logs_interval" {
  description = "VPC flow logs interval"
  type        = string
  default     = "INTERVAL_15_MIN"
}

variable "vpc_flow_logs_sampling" {
  description = "VPC flow logs sampling"
  type        = number
  default     = 1.0
}
