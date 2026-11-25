variable "project_id" {
  description = "GCP project (use separate projects for test and live)."
  type        = string
}

variable "environment" {
  description = "test or live. Used in names and labels."
  type        = string
  validation {
    condition     = contains(["test", "live"], var.environment)
    error_message = "environment must be test or live."
  }
}

variable "region" {
  description = "Region for Cloud Run, Scheduler and Artifact Registry."
  type        = string
  default     = "africa-south1"
}

variable "bq_location" {
  description = "BigQuery dataset location."
  type        = string
  default     = "africa-south1"
}

variable "dataset_prefix" {
  type    = string
  default = "lunanele_bi"
}

variable "image" {
  description = "Container image for the Cloud Run service (built by CI or `gcloud builds submit`)."
  type        = string
}

variable "retention_days" {
  description = "POPIA retention: partitions older than this are deleted automatically. null = keep forever."
  type        = number
  default     = null
}

variable "billing_account_id" {
  description = "Billing account for the free-tier budget alert. Leave empty to skip."
  type        = string
  default     = ""
}

variable "budget_amount" {
  description = "Alert as soon as spend reaches this amount (in the billing account's currency)."
  type        = number
  default     = 1
}

variable "schedule" {
  description = "Cron for the daily sync, Africa/Johannesburg time."
  type        = string
  default     = "10 6 * * *"
}

variable "env" {
  description = "Plain (non-secret) environment variables for the service: GA4_*_PROPERTY_ID, GBP_*_LOCATION_ID, MERCHANT_CENTER_*_ID, LUNACORE_WEBHOOK_URL."
  type        = map(string)
  default     = {}
}

variable "admins" {
  description = "Extra people who may administer the BI data, e.g. [\"user:someone@lunaneleholdings.com\"]."
  type        = list(string)
  default     = []
}

variable "secrets_in_use" {
  description = "Secrets to inject into the service. Add a name here only after its secret has a value (e.g. [\"GBP_OAUTH_REFRESH_TOKEN\", ...])."
  type        = list(string)
  default     = []
}
