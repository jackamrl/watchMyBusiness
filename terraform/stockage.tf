# Zone de dépôt brute : réponses Apify telles quelles, avant toute transformation.
# Source de vérité rejouable ; BigQuery en est la vue structurée.

resource "google_storage_bucket" "brut" {
  name                        = "${var.projet}-avis-brut"
  location                    = var.region
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  # Filet contre une suppression ou un écrasement accidentel.
  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "ARCHIVE"
    }
  }

  depends_on = [google_project_service.apis]
}

# Le pipeline peut créer et lire, jamais modifier ni supprimer : le dépôt est
# immuable de son point de vue (objectCreator n'autorise pas l'écrasement).
resource "google_storage_bucket_iam_member" "pipeline" {
  for_each = toset(["roles/storage.objectCreator", "roles/storage.objectViewer"])
  bucket   = google_storage_bucket.brut.name
  role     = each.value
  member   = google_service_account.pipeline.member
}
