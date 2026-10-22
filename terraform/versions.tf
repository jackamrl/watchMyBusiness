terraform {
  required_version = ">= 1.6"

  # Bucket créé par deployer.ps1 : terraform init -backend-config="bucket=<projet>-tfstate"
  backend "gcs" {
    prefix = "watchmybusiness"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
  }
}

provider "google" {
  project = var.projet
  region  = var.region

  # L'API Budgets facture le quota au projet appelant, pas au compte de facturation.
  user_project_override = true
  billing_project       = var.projet
}
