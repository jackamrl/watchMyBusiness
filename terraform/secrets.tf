# Terraform crée les conteneurs de secrets, jamais leurs valeurs : elles
# n'apparaissent ainsi ni dans le code ni dans le state.
#   gcloud secrets versions add apify-token --data-file=-

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(["apify-token", "smtp-mot-de-passe"])
  secret_id = each.value

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }

  depends_on = [google_project_service.apis]
}
