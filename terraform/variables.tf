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

variable "image" {
  description = "Full container image URI (e.g. us.gcr.io/project/repo/service:tag)"
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
