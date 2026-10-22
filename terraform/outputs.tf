output "image" {
  value = local.image
}

output "dataset" {
  value = "${var.projet}.${google_bigquery_dataset.wmb.dataset_id}"
}

output "depot_brut" {
  value = "gs://${google_storage_bucket.brut.name}"
}

output "jobs" {
  value = { for cle, job in google_cloud_run_v2_job.jobs : cle => job.name }
}

output "tableau_de_bord" {
  value = google_cloud_run_v2_service.web.uri
}

output "workflow" {
  value = google_workflows_workflow.quotidien.name
}

output "looker_studio" {
  value = "https://lookerstudio.google.com/datasources/create?connectorId=2 — projet ${var.projet}, dataset watchmybusiness, vues v_kpi_semaine / v_themes / v_avis"
}
