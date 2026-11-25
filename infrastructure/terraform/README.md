# Terraform — Lunanele Google BI

Everything the pipeline needs in Google Cloud, as reviewed, version-controlled code:
APIs, the `lunanele-bi-runner` service account (least privilege), BigQuery datasets/tables/views
(with optional POPIA retention), Secret Manager secrets, the private Cloud Run service,
the daily Scheduler job (paused outside `live`), image cleanup, and the budget alert.

## First run (per environment)
```bash
gcloud auth application-default login
PROJECT=lunanele-bi-live
gcloud storage buckets create gs://$PROJECT-tfstate --location=africa-south1 --uniform-bucket-level-access
gcloud storage buckets update gs://$PROJECT-tfstate --versioning

# one image to start with
gcloud artifacts repositories create lunanele-bi --repository-format=docker --location=africa-south1 || true
gcloud builds submit ../.. --tag africa-south1-docker.pkg.dev/$PROJECT/lunanele-bi/app:latest

cp live.tfvars.example live.tfvars   # fill in IDs (no secrets in this file)
terraform init -backend-config="bucket=$PROJECT-tfstate"
terraform plan -var-file=live.tfvars
terraform apply -var-file=live.tfvars
```
If the Artifact Registry repo was created by hand above, import it first:
`terraform import -var-file=live.tfvars google_artifact_registry_repository.images projects/$PROJECT/locations/africa-south1/repositories/lunanele-bi`.

Then add secret values (never in code):
```bash
printf '%s' "<token>" | gcloud secrets versions add lunanele-bi-gbp-oauth-refresh-token --data-file=-
```

## Existing setup from bootstrap_gcp.sh
Import what already exists instead of recreating it, e.g.
`terraform import google_bigquery_dataset.raw projects/$PROJECT/datasets/lunanele_bi_raw`.
Raw tables have `deletion_protection = true`; data is never dropped by Terraform.

## Test vs live
Use a separate project and state bucket for `test`. Its scheduler is created paused; trigger runs by hand.
