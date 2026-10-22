# Tableau de bord public : même image que les jobs, commande « web ».
# Le compte de service ne peut que lire le dataset : une faille dans l'API ne
# permettrait ni d'écrire dans BigQuery, ni d'appeler Gemini, ni de lire les secrets.

resource "google_service_account" "web" {
  account_id   = "wmb-web"
  display_name = "WatchMyBusiness — tableau de bord (lecture seule)"
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "web" {
  for_each = toset([
    "roles/bigquery.jobUser",
    "roles/logging.logWriter",
  ])
  project = var.projet
  role    = each.value
  member  = google_service_account.web.member
}

resource "google_bigquery_dataset_iam_member" "web" {
  dataset_id = google_bigquery_dataset.wmb.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = google_service_account.web.member
}

resource "google_cloud_run_v2_service" "web" {
  name                = "wmb-web"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = false

  template {
    service_account                  = google_service_account.web.email
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0
      max_instance_count = 2
    }

    containers {
      image = local.image
      args  = ["web"]

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = true
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.projet
      }
      env {
        name  = "REGION"
        value = var.region
      }
      env {
        name  = "DATASET"
        value = google_bigquery_dataset.wmb.dataset_id
      }

      startup_probe {
        http_get {
          path = "/api/sante"
        }
      }
    }
  }

  depends_on = [
    google_project_iam_member.web,
    google_bigquery_dataset_iam_member.web,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  name     = google_cloud_run_v2_service.web.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}
