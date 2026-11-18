"""Job « analyse » : avis_bruts non encore analysés → `avis_analyses`.

Deux moteurs, choisis par MOTEUR_ANALYSE :
  * gemini : un appel Gemini par avis (historique) ;
  * maison : le NLP fait main classe les avis ; ceux sur lesquels il hésite
             (confiance < seuil calibré) passent en relais à Gemini.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from . import entrepot, gemini, secrets
from .config import Config

journal = logging.getLogger(__name__)

TAILLE_LOT = 500
PARALLELISME = 8
ESSAIS = 4


def a_analyser(config: Config, limite: int = TAILLE_LOT, version: str | None = None) -> list[dict]:
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
        {"version": version or gemini.VERSION_PROMPT, "limite": limite},
    )


class ErreurDefinitive(RuntimeError):
    """Modèle introuvable, droits manquants… : réessayer ne changera rien."""


def _reessayable(erreur: Exception) -> bool:
    code = getattr(erreur, "code", None)
    return not (isinstance(code, int) and 400 <= code < 500 and code != 429)


def _analyser_un(
    client_genai, config: Config, avis: dict, avec_humeur: bool = False
) -> dict | None:
    for essai in range(ESSAIS):
        try:
            sortie = gemini.analyser(
                client_genai,
                config.modele_gemini,
                avis["metier"],
                avis["nom"],
                avis["texte"],
                avis["note"],
                avec_humeur=avec_humeur,
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


def client_gemini(config: Config):
    """API Gemini par clé si SECRET_GEMINI est défini (sans Vertex), sinon Vertex AI."""
    cle = secrets.lire(config, config.secret_gemini) if config.secret_gemini else None
    return gemini.client(config.projet, config.region_gemini, cle_api=cle)


def executer(config: Config) -> int:
    if config.moteur_analyse == "maison":
        return executer_maison(config)
    avis = a_analyser(config)
    if not avis:
        journal.info("Aucun nouvel avis à analyser.")
        return 0

    client_genai = client_gemini(config)

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


def executer_maison(config: Config) -> int:
    from .nlp.service import ModeleMaison

    if not config.modele_maison:
        raise SystemExit("MOTEUR_ANALYSE=maison mais MODELE_MAISON est vide.")
    # Poids introuvables ou illisibles : arrêt immédiat, avant le premier avis.
    modele = ModeleMaison.depuis_uri(config.modele_maison)
    if modele.version != config.version_modele:
        raise SystemExit(
            f"Paquet modèle en version {modele.version}, VERSION_MODELE={config.version_modele}."
        )
    avis = a_analyser(config, version=modele.version)
    if not avis:
        journal.info("Aucun nouvel avis à analyser.")
        return 0

    debut = time.monotonic()
    sorties: list[dict] = []
    for i in range(0, len(avis), 64):
        sorties += modele.predire_lot([a["texte"] for a in avis[i : i + 64]])
    journal.info(
        "%d avis classés par le modèle maison %s en %.1f s",
        len(avis), modele.version, time.monotonic() - debut,
    )

    maintenant = datetime.now(UTC).isoformat()
    lignes = [
        {
            "review_id": a["review_id"],
            "etablissement_id": a["etablissement_id"],
            "date_avis": a["date_avis"].isoformat(),
            "note": a["note"],
            **sortie,
            "modele": f"maison-{modele.version}",
            "version_prompt": modele.version,
            "analyse_le": maintenant,
        }
        for a, sortie in zip(avis, sorties, strict=True)
    ]

    incertains = [i for i, s in enumerate(sorties) if s["confiance"] < modele.seuil]
    journal.info(
        "%d avis sous le seuil de confiance %.2f%s",
        len(incertains), modele.seuil, " → relais Gemini" if config.relais_gemini else "",
    )
    if config.relais_gemini and incertains:
        client_genai = client_gemini(config)

        def relayer(i: int) -> None:
            try:
                resultat = _analyser_un(client_genai, config, avis[i], avec_humeur=True)
            except ErreurDefinitive as erreur:
                journal.error("relais Gemini impossible : %s", erreur)
                return
            if resultat:  # sinon : on garde le résultat maison, marqué par sa confiance
                lignes[i] = {**resultat, "version_prompt": modele.version, "confiance": None}

        with ThreadPoolExecutor(max_workers=PARALLELISME) as pool:
            list(pool.map(relayer, incertains))

    entrepot.fusionner(config, "avis_analyses", lignes, ("review_id", "version_prompt"))
    return 0
