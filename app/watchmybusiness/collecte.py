"""Job « collecte » : Apify → Cloud Storage (brut) → BigQuery `avis_bruts`.

L'ordre est imposé : dépôt brut d'abord, transformation ensuite. Un échec
après le dépôt se répare avec `rejouer`, sans nouvelle collecte.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from . import apify, depot_brut, entrepot, secrets
from .config import Config

journal = logging.getLogger(__name__)


def charger(
    config: Config, items: list, etablissement_id: str, collecte_le: datetime
) -> tuple[int, int]:
    """Normalise puis MERGE dans avis_bruts. Renvoie (avis lus, lignes modifiées)."""
    lignes = apify.normaliser(items, etablissement_id, collecte_le)
    return len(lignes), entrepot.fusionner(config, "avis_bruts", lignes, ("review_id",))


def executer(config: Config) -> int:
    etablissements = entrepot.requete(
        config,
        f"SELECT etablissement_id, nom, url_maps, max_avis, langue "
        f"FROM {config.table('etablissements')} WHERE actif",
    )
    if not etablissements:
        journal.warning("Aucun établissement actif.")
        return 0

    jeton = secrets.lire(config, config.secret_apify)
    echecs = 0
    for etab in etablissements:
        nom = etab["nom"]
        if not apify.url_valide(etab["url_maps"]):
            journal.error("%s : URL Maps sans identifiant de lieu (!1s0x…:0x…)", nom)
            echecs += 1
            continue
        try:
            run_id, items = apify.collecter(
                jeton, etab["url_maps"], etab["max_avis"] or 50, etab["langue"] or "fr"
            )
        except apify.ErreurApify as erreur:
            journal.error("%s : %s", nom, erreur)
            echecs += 1
            continue

        collecte_le = datetime.now(UTC)
        uri = depot_brut.deposer(config, etab["etablissement_id"], collecte_le, run_id, items)
        journal.info("%s : %d items bruts déposés dans %s", nom, len(items), uri)

        lus, modifiees = charger(config, items, etab["etablissement_id"], collecte_le)
        journal.info(
            "%s : %d avis normalisés, %d lignes insérées ou mises à jour", nom, lus, modifiees
        )

    if echecs:
        raise SystemExit(f"{echecs} établissement(s) en échec")
    return 0


def rejouer(config: Config, prefixe: str) -> int:
    """Recharge BigQuery depuis le dépôt brut, sans appeler Apify.

    `prefixe` : « as-du-fallafel/2026-10-22/ », « as-du-fallafel/ » ou « » (tout).
    Idempotent grâce au MERGE : rejouer deux fois ne crée aucun doublon.
    """
    fichiers = depot_brut.lister(config, prefixe)
    if not fichiers:
        raise SystemExit(f"Aucun dépôt brut sous gs://{config.bucket_brut}/{prefixe}")

    for nom in fichiers:
        items, meta = depot_brut.lire(config, nom)
        etablissement_id = meta.get("etablissement_id") or nom.split("/", 1)[0]
        collecte_le = (
            datetime.fromisoformat(meta["collecte_le"])
            if meta.get("collecte_le")
            else datetime.now(UTC)
        )
        lus, modifiees = charger(config, items, etablissement_id, collecte_le)
        journal.info("rejeu %s : %d avis, %d lignes modifiées", nom, lus, modifiees)
    return 0
