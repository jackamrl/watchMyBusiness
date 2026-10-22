# Quotidien : collecte puis analyse, enchaînées par Workflows (l'analyse ne
# démarre que si la collecte a réussi). Hebdomadaire : rapport.

resource "google_workflows_workflow" "quotidien" {
  name            = "wmb-quotidien"
  region          = var.region
  service_account = google_service_account.orchestrateur.id
  description     = "Collecte Apify puis analyse Gemini."

  source_contents = <<-YAML
    main:
      steps:
        - collecte:
            call: googleapis.run.v2.projects.locations.jobs.run
            args:
              name: ${google_cloud_run_v2_job.jobs["collecte"].id}
            result: execution_collecte
        - analyse:
            call: googleapis.run.v2.projects.locations.jobs.run
            args:
              name: ${google_cloud_run_v2_job.jobs["analyse"].id}
            result: execution_analyse
        - fin:
            return:
              collecte: $${execution_collecte.name}
              analyse: $${execution_analyse.name}
  YAML

  depends_on = [google_project_service.apis]
}

resource "google_cloud_scheduler_job" "quotidien" {
  name             = "wmb-quotidien"
  region           = var.region
  schedule         = var.planification_collecte
  time_zone        = var.fuseau
  attempt_deadline = "180s"

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/${google_workflows_workflow.quotidien.id}/executions"
    body        = base64encode("{}")

    oauth_token {
      service_account_email = google_service_account.orchestrateur.email
    }
  }
}

resource "google_cloud_scheduler_job" "rapport" {
  name             = "wmb-rapport-hebdo"
  region           = var.region
  schedule         = var.planification_rapport
  time_zone        = var.fuseau
  attempt_deadline = "180s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/${google_cloud_run_v2_job.jobs["rapport"].id}:run"

    oauth_token {
      service_account_email = google_service_account.orchestrateur.email
    }
  }
}
