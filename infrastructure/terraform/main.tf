locals {
  labels  = { system = "lunanele-google-bi", environment = var.environment, managed_by = "terraform" }
  raw     = "${var.dataset_prefix}_raw"
  mart    = "${var.dataset_prefix}_mart"
  bq_dir  = "${path.module}/../bigquery"
  service = "lunanele-google-bi-${var.environment}"

  # table -> partition column
  tables = {
    ga4_daily_metrics        = "event_date"
    search_console_daily     = "query_date"
    merchant_center_products = "snapshot_date"
    business_profile_daily   = "metric_date"
    sync_runs                = null # partitioned by DATE(started_at)
  }
  # views in dependency order are handled with depends_on below
  views = ["v_holdings_executive_rollup", "v_top_search_queries", "v_data_freshness"]

  secrets = ["GBP_OAUTH_CLIENT_ID", "GBP_OAUTH_CLIENT_SECRET", "GBP_OAUTH_REFRESH_TOKEN", "LUNACORE_API_KEY"]
}

# ---------- APIs ----------
resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com", "cloudbuild.googleapis.com", "artifactregistry.googleapis.com",
    "bigquery.googleapis.com", "secretmanager.googleapis.com", "cloudscheduler.googleapis.com",
    "analyticsdata.googleapis.com", "searchconsole.googleapis.com", "merchantapi.googleapis.com",
    "businessprofileperformance.googleapis.com", "billingbudgets.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}

# ---------- Identity ----------
resource "google_service_account" "runner" {
  account_id   = "lunanele-bi-runner"
  display_name = "Lunanele BI Ingestor (${var.environment})"
}

resource "google_project_iam_member" "runner_jobs" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = google_service_account.runner.member
}

# ---------- BigQuery ----------
resource "google_bigquery_dataset" "raw" {
  dataset_id                      = local.raw
  location                        = var.bq_location
  description                     = "Raw Google data per entity. No personal information."
  labels                          = local.labels
  default_partition_expiration_ms = var.retention_days == null ? null : var.retention_days * 86400000
  delete_contents_on_destroy      = false
  depends_on                      = [google_project_service.apis]
}

resource "google_bigquery_dataset" "mart" {
  dataset_id  = local.mart
  location    = var.bq_location
  description = "Views for Looker Studio."
  labels      = local.labels
  depends_on  = [google_project_service.apis]
}

# Least privilege: the runner edits data only in these two datasets.
resource "google_bigquery_dataset_iam_member" "runner_edit" {
  for_each   = { raw = google_bigquery_dataset.raw.dataset_id, mart = google_bigquery_dataset.mart.dataset_id }
  dataset_id = each.value
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.runner.member
}

resource "google_bigquery_dataset_iam_member" "admins" {
  for_each   = toset(var.admins)
  dataset_id = google_bigquery_dataset.raw.dataset_id
  role       = "roles/bigquery.dataOwner"
  member     = each.value
}

resource "google_bigquery_table" "raw" {
  for_each            = local.tables
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = each.key
  schema              = file("${local.bq_dir}/schemas/${each.key}.json")
  labels              = local.labels
  deletion_protection = true

  time_partitioning {
    type          = "DAY"
    field         = each.value == null ? "started_at" : each.value
    expiration_ms = var.retention_days == null ? null : var.retention_days * 86400000
  }
  clustering = each.value == null ? null : ["entity_slug"]
}

resource "google_bigquery_table" "views" {
  for_each            = toset(local.views)
  dataset_id          = google_bigquery_dataset.mart.dataset_id
  table_id            = each.value
  deletion_protection = false
  labels              = local.labels
  view {
    query          = replace(file("${local.bq_dir}/views/${each.value}.sql"), "lunanele_bi_", "${var.dataset_prefix}_")
    use_legacy_sql = false
  }
  depends_on = [google_bigquery_table.raw]
}

resource "google_bigquery_table" "acquisition_view" {
  dataset_id          = google_bigquery_dataset.mart.dataset_id
  table_id            = "v_customer_acquisition_daily"
  deletion_protection = false
  labels              = local.labels
  view {
    query          = replace(file("${local.bq_dir}/views/v_customer_acquisition_daily.sql"), "lunanele_bi_", "${var.dataset_prefix}_")
    use_legacy_sql = false
  }
  depends_on = [google_bigquery_table.views]
}

# ---------- Secrets (values are added outside Terraform, never in code) ----------
resource "google_secret_manager_secret" "s" {
  for_each  = toset(local.secrets)
  secret_id = "lunanele-bi-${lower(replace(each.value, "_", "-"))}"
  labels    = local.labels
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "runner_read" {
  for_each  = google_secret_manager_secret.s
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.runner.member
}

# ---------- Cloud Run ----------
resource "google_cloud_run_v2_service" "app" {
  name                = local.service
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.environment == "live"
  labels              = local.labels

  template {
    service_account = google_service_account.runner.email
    timeout         = "900s"
    scaling {
      min_instance_count = 0 # scale to zero: stays in the free tier
      max_instance_count = 1
    }
    containers {
      image = var.image
      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "BQ_DATASET_PREFIX"
        value = var.dataset_prefix
      }
      dynamic "env" {
        for_each = var.env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        # Only secrets that already have a value: Cloud Run refuses to start on an empty secret.
        for_each = { for k, v in google_secret_manager_secret.s : k => v if contains(var.secrets_in_use, k) }
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
  depends_on = [google_secret_manager_secret_iam_member.runner_read, google_bigquery_dataset_iam_member.runner_edit]
}
# Private service: only the scheduler's identity may call it.
resource "google_cloud_run_v2_service_iam_member" "scheduler_invoke" {
  name     = google_cloud_run_v2_service.app.name
  location = var.region
  role     = "roles/run.invoker"
  member   = google_service_account.runner.member
}

# ---------- Schedule (1 of 3 free jobs) ----------
resource "google_cloud_scheduler_job" "daily" {
  name             = "${local.service}-daily"
  region           = var.region
  schedule         = var.schedule
  time_zone        = "Africa/Johannesburg"
  attempt_deadline = "900s"
  paused           = var.environment != "live"
  retry_config {
    retry_count          = 2
    min_backoff_duration = "300s"
  }
  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.app.uri}/run-sync"
    oidc_token {
      service_account_email = google_service_account.runner.email
      audience              = google_cloud_run_v2_service.app.uri
    }
  }
}

# ---------- Free-tier guardrails ----------
resource "google_artifact_registry_repository" "images" {
  repository_id          = "lunanele-bi"
  location               = var.region
  format                 = "DOCKER"
  labels                 = local.labels
  cleanup_policy_dry_run = false
  cleanup_policies {
    id     = "keep-latest-2"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }
  cleanup_policies {
    id     = "delete-older"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "604800s"
    }
  }
  depends_on = [google_project_service.apis]
}

data "google_project" "this" {}

resource "google_billing_budget" "guard" {
  count           = var.billing_account_id == "" ? 0 : 1
  billing_account = var.billing_account_id
  display_name    = "Lunanele free-tier guard (${var.environment})"
  budget_filter {
    projects = ["projects/${data.google_project.this.number}"]
  }
  amount {
    specified_amount {
      units = tostring(var.budget_amount)
    }
  }
  threshold_rules { threshold_percent = 0.01 }
  threshold_rules { threshold_percent = 1.0 }
}
