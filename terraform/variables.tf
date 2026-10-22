variable "projet" {
  type        = string
  description = "Identifiant du projet GCP."
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "compte_facturation" {
  type        = string
  description = "ID du compte de facturation (pour l'alerte budgétaire)."
}

variable "budget_mensuel" {
  type        = number
  default     = 5
  description = "Montant de l'alerte budgétaire, dans la devise du compte de facturation."
}

variable "email_alertes" {
  type        = string
  description = "Destinataire des alertes (échec de job, budget)."
}

variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Tag de l'image du pipeline dans Artifact Registry."
}

variable "modele_gemini" {
  type    = string
  default = "gemini-3.5-flash"
}

variable "region_gemini" {
  type        = string
  default     = "europe-west3"
  description = <<-EOT
    Région Vertex AI des appels Gemini. Tous les modèles ne sont pas servis
    partout : gemini-3.5-flash l'est à Francfort, pas à Bruxelles. Une région
    UE (plutôt que « global ») garde le traitement des avis dans l'Union.
    Vérification : gcp\.venv\Scripts\python gcp\sonder_modeles.py
  EOT
}

variable "planification_collecte" {
  type    = string
  default = "0 6 * * *"
}

variable "planification_rapport" {
  type    = string
  default = "0 8 * * 1"
}

variable "fuseau" {
  type    = string
  default = "Europe/Paris"
}

variable "smtp" {
  type = object({
    hote        = string
    port        = number
    utilisateur = string
    expediteur  = string
  })
  default = {
    hote        = ""
    port        = 587
    utilisateur = ""
    expediteur  = ""
  }
  description = "Envoi du rapport par e-mail. Vide = pas d'e-mail (Looker Studio seul)."
}

variable "etablissements" {
  type = list(object({
    etablissement_id = string
    nom              = string
    url_maps         = string
    metier           = string
    email_manager    = string
    max_avis         = number
    langue           = string
    actif            = bool
  }))
  description = "Établissements suivis. Ajouter un lieu = ajouter une entrée ici."

  validation {
    condition     = alltrue([for e in var.etablissements : contains(["restaurant", "mobilier"], e.metier)])
    error_message = "metier doit valoir restaurant ou mobilier."
  }

  validation {
    condition     = alltrue([for e in var.etablissements : can(regex("!1s0x[0-9a-f]+:0x[0-9a-f]+", e.url_maps))])
    error_message = "url_maps doit contenir l'identifiant de lieu (!1s0x…:0x…). Suivez la redirection du lien maps.app.goo.gl."
  }
}
