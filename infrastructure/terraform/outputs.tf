output "service_url" { value = google_cloud_run_v2_service.app.uri }
output "runner_email" {
  description = "Add this address as a viewer in GA4, Search Console and Merchant Center."
  value       = google_service_account.runner.email
}
output "image_repository" { value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}" }
output "secrets_to_fill" { value = [for s in google_secret_manager_secret.s : s.secret_id] }
