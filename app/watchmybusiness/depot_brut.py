"""Zone de dépôt brute (Cloud Storage) : la réponse Apify telle quelle, immuable.

Écrite AVANT toute transformation : si la normalisation ou le MERGE échoue,
ou s'avère boguée plus tard, la donnée source reste intacte et rejouable sans
repayer Apify. BigQuery n'est qu'une vue structurée de ce dépôt.

    gs://<bucket>/<etablissement_id>/<AAAA-MM-JJ>/run-<run_id>.json
"""

from __future__ import annotations

import json
from datetime import datetime

from .config import Config


def chemin(etablissement_id: str, collecte_le: datetime, run_id: str) -> str:
    return f"{etablissement_id}/{collecte_le:%Y-%m-%d}/run-{run_id}.json"


def _bucket(config: Config):
    from google.cloud import storage

    if not config.bucket_brut:
        raise RuntimeError("BUCKET_BRUT absent de l'environnement.")
    return storage.Client(project=config.projet).bucket(config.bucket_brut)


def deposer(
    config: Config, etablissement_id: str, collecte_le: datetime, run_id: str, items: list
) -> str:
    """Écrit l'export brut ; refuse d'écraser un fichier existant."""
    nom = chemin(etablissement_id, collecte_le, run_id)
    blob = _bucket(config).blob(nom)
    blob.metadata = {
        "etablissement_id": etablissement_id,
        "apify_run_id": run_id,
        "nb_items": str(len(items)),
        "collecte_le": collecte_le.isoformat(),
    }
    blob.upload_from_string(
        json.dumps(items, ensure_ascii=False),
        content_type="application/json",
        if_generation_match=0,
    )
    return f"gs://{config.bucket_brut}/{nom}"


def lister(config: Config, prefixe: str) -> list[str]:
    return sorted(
        blob.name
        for blob in _bucket(config).list_blobs(prefix=prefixe)
        if blob.name.endswith(".json")
    )


def lire(config: Config, nom: str) -> tuple[list, dict]:
    blob = _bucket(config).blob(nom)
    contenu = blob.download_as_text(encoding="utf-8")
    blob.reload()
    return json.loads(contenu), dict(blob.metadata or {})
