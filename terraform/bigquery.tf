resource "google_bigquery_dataset" "wmb" {
  dataset_id  = "watchmybusiness"
  location    = var.region
  description = "WatchMyBusiness : avis bruts, analyses Gemini, rapports hebdomadaires."

  depends_on = [google_project_service.apis]
}

resource "google_bigquery_table" "etablissements" {
  dataset_id          = google_bigquery_dataset.wmb.dataset_id
  table_id            = "etablissements"
  deletion_protection = false

  schema = jsonencode([
    { name = "etablissement_id", type = "STRING", mode = "REQUIRED" },
    { name = "nom", type = "STRING", mode = "REQUIRED" },
    { name = "url_maps", type = "STRING", mode = "REQUIRED" },
    { name = "metier", type = "STRING", mode = "REQUIRED" },
    { name = "email_manager", type = "STRING" },
    { name = "max_avis", type = "INT64" },
    { name = "langue", type = "STRING" },
    { name = "actif", type = "BOOL", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "avis_bruts" {
  dataset_id          = google_bigquery_dataset.wmb.dataset_id
  table_id            = "avis_bruts"
  deletion_protection = true
  description         = "Avis Google Maps tels que collectés par Apify. Clé : review_id."

  time_partitioning {
    type  = "DAY"
    field = "date_avis"
  }
  clustering = ["etablissement_id"]

  schema = jsonencode([
    { name = "review_id", type = "STRING", mode = "REQUIRED" },
    { name = "etablissement_id", type = "STRING", mode = "REQUIRED" },
    { name = "date_avis", type = "DATE", mode = "REQUIRED" },
    { name = "publie_le", type = "TIMESTAMP" },
    { name = "note", type = "INT64" },
    { name = "texte", type = "STRING" },
    { name = "langue", type = "STRING" },
    { name = "url_avis", type = "STRING" },
    { name = "reponse_proprietaire", type = "STRING" },
    { name = "brut", type = "JSON", description = "Item Apify complet, pour retraitement." },
    { name = "collecte_le", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "avis_analyses" {
  dataset_id          = google_bigquery_dataset.wmb.dataset_id
  table_id            = "avis_analyses"
  deletion_protection = true
  description         = "Sortie structurée Gemini. Clé : (review_id, version_prompt)."

  time_partitioning {
    type  = "DAY"
    field = "date_avis"
  }
  clustering = ["etablissement_id", "version_prompt"]

  schema = jsonencode([
    { name = "review_id", type = "STRING", mode = "REQUIRED" },
    { name = "etablissement_id", type = "STRING", mode = "REQUIRED" },
    { name = "date_avis", type = "DATE", mode = "REQUIRED" },
    { name = "note", type = "INT64" },
    { name = "sentiment", type = "STRING", mode = "REQUIRED" },
    { name = "score", type = "FLOAT64" },
    {
      name = "themes", type = "RECORD", mode = "REPEATED",
      fields = [
        { name = "theme", type = "STRING" },
        { name = "polarite", type = "STRING" },
        { name = "extrait", type = "STRING" },
      ]
    },
    { name = "theme_emergent", type = "STRING" },
    { name = "actionnable", type = "BOOL" },
    { name = "resume", type = "STRING" },
    { name = "modele", type = "STRING", mode = "REQUIRED" },
    { name = "version_prompt", type = "STRING", mode = "REQUIRED" },
    { name = "analyse_le", type = "TIMESTAMP", mode = "REQUIRED" },
  ])
}

resource "google_bigquery_table" "rapports_hebdo" {
  dataset_id          = google_bigquery_dataset.wmb.dataset_id
  table_id            = "rapports_hebdo"
  deletion_protection = true

  time_partitioning {
    type  = "MONTH"
    field = "periode_debut"
  }
  clustering = ["etablissement_id"]

  schema = jsonencode([
    { name = "etablissement_id", type = "STRING", mode = "REQUIRED" },
    { name = "semaine_id", type = "STRING", mode = "REQUIRED" },
    { name = "periode_debut", type = "DATE", mode = "REQUIRED" },
    { name = "periode_fin", type = "DATE", mode = "REQUIRED" },
    { name = "nb_avis", type = "INT64" },
    { name = "nb_analyses", type = "INT64" },
    { name = "note_moyenne", type = "FLOAT64" },
    { name = "nb_positif", type = "INT64" },
    { name = "nb_negatif", type = "INT64" },
    { name = "nb_neutre", type = "INT64" },
    { name = "nb_mixte", type = "INT64" },
    { name = "pct_positif", type = "FLOAT64" },
    { name = "pct_negatif", type = "FLOAT64" },
    { name = "pct_neutre", type = "FLOAT64" },
    { name = "pct_mixte", type = "FLOAT64" },
    { name = "score_moyen", type = "FLOAT64" },
    { name = "nb_actionnables", type = "INT64" },
    { name = "tendance", type = "STRING" },
    { name = "top_negatifs", type = "STRING", description = "JSON : thèmes négatifs classés" },
    { name = "top_positifs", type = "STRING", description = "JSON : thèmes positifs classés" },
    { name = "synthese", type = "STRING", description = "Markdown rédigé par l'agent Gemini" },
    { name = "modele", type = "STRING" },
    { name = "version_prompt", type = "STRING" },
    { name = "genere_le", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "statut_email", type = "STRING" },
  ])
}

# --------------------------------------------------------------------------- #
# Vues pour Looker Studio (une seule analyse par avis : la plus récente)
# --------------------------------------------------------------------------- #

locals {
  ds = "${var.projet}.${google_bigquery_dataset.wmb.dataset_id}"
}

resource "google_bigquery_table" "v_avis" {
  dataset_id          = google_bigquery_dataset.wmb.dataset_id
  table_id            = "v_avis"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        e.nom AS etablissement, e.metier, b.etablissement_id, b.review_id,
        b.date_avis, DATE_TRUNC(b.date_avis, ISOWEEK) AS semaine,
        b.note, b.texte, b.langue, b.url_avis,
        a.sentiment, a.score, a.resume, a.actionnable, a.theme_emergent,
        a.modele, a.version_prompt,
        ARRAY_LENGTH(a.themes) AS nb_themes
      FROM `${local.ds}.avis_bruts` b
      JOIN `${local.ds}.etablissements` e USING (etablissement_id)
      LEFT JOIN (
        SELECT * FROM `${local.ds}.avis_analyses`
        QUALIFY ROW_NUMBER() OVER (PARTITION BY review_id ORDER BY analyse_le DESC) = 1
      ) a USING (review_id)
    SQL
  }

  depends_on = [
    google_bigquery_table.avis_bruts,
    google_bigquery_table.avis_analyses,
    google_bigquery_table.etablissements,
  ]
}

resource "google_bigquery_table" "v_themes" {
  dataset_id          = google_bigquery_dataset.wmb.dataset_id
  table_id            = "v_themes"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        e.nom AS etablissement, a.etablissement_id, a.review_id, a.date_avis,
        DATE_TRUNC(a.date_avis, ISOWEEK) AS semaine,
        a.sentiment, t.theme, t.polarite, t.extrait
      FROM (
        SELECT * FROM `${local.ds}.avis_analyses`
        QUALIFY ROW_NUMBER() OVER (PARTITION BY review_id ORDER BY analyse_le DESC) = 1
      ) a
      JOIN `${local.ds}.etablissements` e USING (etablissement_id),
      UNNEST(a.themes) t
    SQL
  }

  depends_on = [google_bigquery_table.avis_analyses, google_bigquery_table.etablissements]
}

resource "google_bigquery_table" "v_kpi_semaine" {
  dataset_id          = google_bigquery_dataset.wmb.dataset_id
  table_id            = "v_kpi_semaine"
  deletion_protection = false

  view {
    use_legacy_sql = false
    query          = <<-SQL
      SELECT
        etablissement, etablissement_id, semaine,
        COUNT(*) AS nb_avis,
        ROUND(AVG(note), 2) AS note_moyenne,
        COUNTIF(sentiment IS NOT NULL) AS nb_analyses,
        ROUND(100 * SAFE_DIVIDE(COUNTIF(sentiment = 'POSITIF'), COUNTIF(sentiment IS NOT NULL)), 1) AS pct_positif,
        ROUND(100 * SAFE_DIVIDE(COUNTIF(sentiment = 'NEGATIF'), COUNTIF(sentiment IS NOT NULL)), 1) AS pct_negatif,
        ROUND(100 * SAFE_DIVIDE(COUNTIF(sentiment = 'MIXTE'), COUNTIF(sentiment IS NOT NULL)), 1) AS pct_mixte,
        ROUND(100 * SAFE_DIVIDE(COUNTIF(sentiment = 'NEUTRE'), COUNTIF(sentiment IS NOT NULL)), 1) AS pct_neutre,
        ROUND(AVG(score), 3) AS score_moyen,
        COUNTIF(actionnable) AS nb_actionnables
      FROM `${local.ds}.v_avis`
      GROUP BY 1, 2, 3
    SQL
  }

  depends_on = [google_bigquery_table.v_avis]
}

# --------------------------------------------------------------------------- #
# Référentiel des établissements, piloté par var.etablissements
# --------------------------------------------------------------------------- #

locals {
  lignes_etablissements = join(",\n", [
    for e in var.etablissements : format(
      "STRUCT(%q AS etablissement_id, %q AS nom, %q AS url_maps, %q AS metier, %q AS email_manager, %d AS max_avis, %q AS langue, %t AS actif)",
      e.etablissement_id, e.nom, e.url_maps, e.metier, e.email_manager, e.max_avis, e.langue, e.actif
    )
  ])
  sql_etablissements = <<-SQL
    MERGE `${local.ds}.etablissements` c
    USING (SELECT * FROM UNNEST([${local.lignes_etablissements}])) s
    ON c.etablissement_id = s.etablissement_id
    WHEN MATCHED THEN UPDATE SET
      nom = s.nom, url_maps = s.url_maps, metier = s.metier,
      email_manager = s.email_manager, max_avis = s.max_avis,
      langue = s.langue, actif = s.actif
    WHEN NOT MATCHED THEN INSERT ROW
    WHEN NOT MATCHED BY SOURCE THEN UPDATE SET actif = FALSE
  SQL
}

# Un job BigQuery est immuable : l'empreinte du SQL dans l'identifiant force un
# nouveau MERGE à chaque modification de var.etablissements, et seulement alors.
resource "google_bigquery_job" "etablissements" {
  job_id   = "etablissements_${substr(sha256(local.sql_etablissements), 0, 16)}"
  location = var.region

  query {
    query              = local.sql_etablissements
    use_legacy_sql     = false
    create_disposition = ""
    write_disposition  = ""
  }

  depends_on = [google_bigquery_table.etablissements]
}
