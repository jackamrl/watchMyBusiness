"""Job « analyse » : avis_bruts non encore analysés → Gemini → `avis_analyses`."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from . import entrepot, gemini
from .config import Config

journal = logging.getLogger(__name__)

TAILLE_LOT = 500
PARALLELISME = 8
ESSAIS = 4


def a_analyser(config: Config, limite: int = TAILLE_LOT) -> list[dict]:
    return entrepot.requete(
        config,
        f"""
        SELECT b.review_id, b.etablissement_id, b.date_avis, b.note, b.texte,
               e.nom, e.metier
        FROM {config.table('avis_bruts')} b
        JOIN {config.table('etablissements')} e USING (etablissement_id)
        LEFT JOIN {config.table('avis_analyses')} a
          ON a.review_id = b.review_id AND a.version_prompt = @version
        WHERE a.review_id IS NULL AND b.texte IS NOT NULL
        ORDER BY b.date_avis DESC
        LIMIT @limite
        """,
        {"version": gemini.VERSION_PROMPT, "limite": limite},
    )


class ErreurDefinitive(RuntimeError):
    """Modèle introuvable, droits manquants… : réessayer ne changera rien."""


def _reessayable(erreur: Exception) -> bool:
    code = getattr(erreur, "code", None)
    return not (isinstance(code, int) and 400 <= code < 500 and code != 429)


def _analyser_un(client_genai, config: Config, avis: dict) -> dict | None:
    for essai in range(ESSAIS):
        try:
            sortie = gemini.analyser(
                client_genai,
                config.modele_gemini,
                avis["metier"],
                avis["nom"],
                avis["texte"],
                avis["note"],
            )
            break
        except Exception as erreur:  # quota 429, 5xx, JSON invalide
            if not _reessayable(erreur):
                raise ErreurDefinitive(f"{config.modele_gemini} : {erreur}") from erreur
            if essai == ESSAIS - 1:
                journal.error("avis %s abandonné : %s", avis["review_id"], erreur)
                return None
            time.sleep(2 ** (essai + 1))
    return {
        "review_id": avis["review_id"],
        "etablissement_id": avis["etablissement_id"],
        "date_avis": avis["date_avis"].isoformat(),
        "note": avis["note"],
        **sortie,
        "modele": config.modele_gemini,
        "version_prompt": gemini.VERSION_PROMPT,
        "analyse_le": datetime.now(UTC).isoformat(),
    }


def executer(config: Config) -> int:
    avis = a_analyser(config)
    if not avis:
        journal.info("Aucun nouvel avis à analyser.")
        return 0

    client_genai = gemini.client(config.projet, config.region_gemini)

    # Un premier avis seul : une erreur de configuration (modèle, région, droits)
    # arrête le job immédiatement au lieu d'échouer N fois en parallèle.
    try:
        premier = _analyser_un(client_genai, config, avis[0])
    except ErreurDefinitive as erreur:
        raise SystemExit(f"Analyse impossible — {erreur}") from None

    with ThreadPoolExecutor(max_workers=PARALLELISME) as pool:
        suite = list(pool.map(lambda a: _analyser_un(client_genai, config, a), avis[1:]))
    resultats = [premier, *suite]

    lignes = [r for r in resultats if r]
    entrepot.fusionner(config, "avis_analyses", lignes, ("review_id", "version_prompt"))
    echecs = len(avis) - len(lignes)
    journal.info("%d avis analysés par %s, %d échecs", len(lignes), config.modele_gemini, echecs)
    if echecs and echecs > len(avis) // 10:
        raise SystemExit(f"{echecs}/{len(avis)} analyses en échec")
    return 0
