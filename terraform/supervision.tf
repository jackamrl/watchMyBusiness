resource "google_monitoring_notification_channel" "email" {
  display_name = "WatchMyBusiness — alertes"
  type         = "email"
  labels = {
    email_address = var.email_alertes
  }
  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "job_en_echec" {
  display_name = "WatchMyBusiness — job en échec"
  combiner     = "OR"

  conditions {
    display_name = "Exécution Cloud Run Job en échec"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_job\" AND metric.type = \"run.googleapis.com/job/completed_execution_count\" AND metric.labels.result = \"failed\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }

  documentation {
    content   = "Un job WatchMyBusiness a échoué. Journaux : Cloud Run > Jobs > wmb-* > Exécutions. Cause fréquente : collecte Apify à 0 avis (URL de lieu) ou quota Gemini."
    mime_type = "text/markdown"
  }

  notification_channels = [google_monitoring_notification_channel.email.id]
}

resource "google_billing_budget" "budget" {
  billing_account = var.compte_facturation
  display_name    = "WatchMyBusiness"

  budget_filter {
    projects = ["projects/${data.google_project.courant.number}"]
  }

  amount {
    specified_amount {
      units = tostring(var.budget_mensuel)
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  threshold_rules {
    threshold_percent = 1.0
  }

  all_updates_rule {
    monitoring_notification_channels = [google_monitoring_notification_channel.email.id]
    disable_default_iam_recipients   = false
  }

  depends_on = [google_project_service.apis]
}

data "google_project" "courant" {
  project_id = var.projet
}
