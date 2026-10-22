resource "google_artifact_registry_repository" "depot" {
  repository_id = "watchmybusiness"
  location      = var.region
  format        = "DOCKER"

  cleanup_policies {
    id     = "garder-10-dernieres"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  depends_on = [google_project_service.apis]
}

locals {
  image = "${var.region}-docker.pkg.dev/${var.projet}/${google_artifact_registry_repository.depot.repository_id}/pipeline:${var.image_tag}"

  # Un seul conteneur, trois jobs : seule la commande change.
  jobs = {
    collecte = { args = ["collecte"], timeout = "1800s", memoire = "512Mi" }
    analyse  = { args = ["analyse"], timeout = "1800s", memoire = "1Gi" }
    rapport  = { args = ["rapport"], timeout = "900s", memoire = "512Mi" }
  }

  environnement = {
    GOOGLE_CLOUD_PROJECT = var.projet
    REGION               = var.region
    DATASET              = google_bigquery_dataset.wmb.dataset_id
    BUCKET_BRUT          = google_storage_bucket.brut.name
    MODELE_GEMINI        = var.modele_gemini
    REGION_GEMINI        = var.region_gemini
    FUSEAU               = var.fuseau
    SMTP_HOTE            = var.smtp.hote
    SMTP_PORT            = tostring(var.smtp.port)
    SMTP_UTILISATEUR     = var.smtp.utilisateur
    EMAIL_EXPEDITEUR     = var.smtp.expediteur
  }
}

resource "google_cloud_run_v2_job" "jobs" {
  for_each            = local.jobs
  name                = "wmb-${each.key}"
  location            = var.region
  deletion_protection = false

  template {
    task_count = 1

    template {
      service_account = google_service_account.pipeline.email
      timeout         = each.value.timeout
      max_retries     = 1

      containers {
        image = local.image
        args  = each.value.args

        resources {
          limits = {
            cpu    = "1"
            memory = each.value.memoire
          }
        }

        dynamic "env" {
          for_each = local.environnement
          content {
            name  = env.key
            value = env.value
          }
        }
      }
    }
  }

  depends_on = [
    google_project_iam_member.pipeline,
    google_bigquery_dataset_iam_member.pipeline,
    google_storage_bucket_iam_member.pipeline,
  ]
}
