"""Lecture Secret Manager à l'exécution (pas de montage) : un secret facultatif
absent ne doit pas empêcher le job de démarrer."""

from __future__ import annotations

from .config import Config


def lire(config: Config, nom: str, obligatoire: bool = True) -> str | None:
    from google.api_core import exceptions
    from google.cloud import secretmanager

    chemin = f"projects/{config.projet}/secrets/{nom}/versions/latest"
    try:
        reponse = secretmanager.SecretManagerServiceClient().access_secret_version(name=chemin)
    except (exceptions.NotFound, exceptions.FailedPrecondition):
        if obligatoire:
            raise RuntimeError(
                f"Secret « {nom} » sans version. Ajoutez-la : "
                f"gcloud secrets versions add {nom} --data-file=-"
            ) from None
        return None
    return reponse.payload.data.decode("utf-8").strip()
