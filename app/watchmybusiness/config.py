"""Configuration lue dans l'environnement (variables posées par Terraform)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    projet: str
    region: str
    dataset: str
    bucket_brut: str
    modele_gemini: str
    region_gemini: str
    secret_apify: str
    secret_smtp: str
    smtp_hote: str
    smtp_port: int
    smtp_utilisateur: str
    email_expediteur: str
    fuseau: str

    def table(self, nom: str) -> str:
        return f"`{self.projet}.{self.dataset}.{nom}`"

    def table_id(self, nom: str) -> str:
        return f"{self.projet}.{self.dataset}.{nom}"


def charger() -> Config:
    projet = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
    if not projet:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT absent de l'environnement.")
    return Config(
        projet=projet,
        region=os.environ.get("REGION", "europe-west1"),
        dataset=os.environ.get("DATASET", "watchmybusiness"),
        bucket_brut=os.environ.get("BUCKET_BRUT", f"{projet}-avis-brut"),
        modele_gemini=os.environ.get("MODELE_GEMINI", "gemini-3.5-flash"),
        region_gemini=os.environ.get("REGION_GEMINI", "europe-west3"),
        secret_apify=os.environ.get("SECRET_APIFY", "apify-token"),
        secret_smtp=os.environ.get("SECRET_SMTP", "smtp-mot-de-passe"),
        smtp_hote=os.environ.get("SMTP_HOTE", ""),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_utilisateur=os.environ.get("SMTP_UTILISATEUR", ""),
        email_expediteur=os.environ.get("EMAIL_EXPEDITEUR", ""),
        fuseau=os.environ.get("FUSEAU", "Europe/Paris"),
    )
