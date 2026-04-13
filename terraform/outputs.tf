output "frontend_service_account" {
  description = "Service account email for the frontend Cloud Run service"
  value       = google_service_account.frontend.email
}
