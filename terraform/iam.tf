# Un compte d'exécution pour les jobs, un compte d'orchestration pour les
# déclencheurs. Le second peut lancer les jobs mais ne lit aucune donnée.

resource "google_service_account" "pipeline" {
  account_id   = "wmb-pipeline"
  display_name = "WatchMyBusiness — exécution des jobs"
  depends_on   = [google_project_service.apis]
}

resource "google_service_account" "orchestrateur" {
  account_id   = "wmb-orchestrateur"
  display_name = "WatchMyBusiness — Scheduler et Workflows"
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "pipeline" {
  for_each = toset([
    "roles/bigquery.jobUser",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
  ])
  project = var.projet
  role    = each.value
  member  = google_service_account.pipeline.member
}

resource "google_bigquery_dataset_iam_member" "pipeline" {
  dataset_id = google_bigquery_dataset.wmb.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = google_service_account.pipeline.member
}

resource "google_secret_manager_secret_iam_member" "pipeline" {
  for_each  = google_secret_manager_secret.secrets
  secret_id = each.value.id
  role      = "roles/secretmanager.secretAccessor"
  member    = google_service_account.pipeline.member
}

resource "google_project_iam_member" "orchestrateur" {
  for_each = toset([
    "roles/run.viewer",
    "roles/workflows.invoker",
    "roles/logging.logWriter",
  ])
  project = var.projet
  role    = each.value
  member  = google_service_account.orchestrateur.member
}

resource "google_cloud_run_v2_job_iam_member" "orchestrateur" {
  for_each = google_cloud_run_v2_job.jobs
  name     = each.value.name
  location = var.region
  role     = "roles/run.invoker"
  member   = google_service_account.orchestrateur.member
}
