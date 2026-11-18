"""Étiquetage par Gemini (API publique, clé dans GEMINI_API_KEY, pas de Vertex AI).

Deux usages, une seule commande :
  * produire les étiquettes « argent » du jeu d'entraînement (sentiment, humeur, thèmes) ;
  * produire les prédictions de Gemini sur le jeu de test, pour la comparaison.

Reprise automatique : les avis déjà présents dans le fichier de sortie sont sautés,
on peut donc interrompre et relancer sans repayer.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from watchmybusiness import gemini
from watchmybusiness.nlp import etiquettes

from .donnees import lire_jsonl

journal = logging.getLogger(__name__)


def etiqueter(entree: str | Path, sortie: str | Path, modele: str = "gemini-3.5-flash",
              nom: str = "l'établissement", parallelisme: int = 8,
              limite: int | None = None, essais: int = 4) -> dict[str, int]:
    cle = os.environ.get("GEMINI_API_KEY")
    if not cle:
        raise SystemExit("GEMINI_API_KEY absent : créez une clé sur aistudio.google.com.")
    client = gemini.client("", "", cle_api=cle)

    deja = set()
    if Path(sortie).exists():
        deja = {l["review_id"] for l in lire_jsonl(sortie)}
    a_faire = [l for l in lire_jsonl(entree) if l.get("texte") and l["review_id"] not in deja]
    if limite:
        a_faire = a_faire[:limite]
    journal.info("%d avis à étiqueter (%d déjà faits)", len(a_faire), len(deja))

    verrou = threading.Lock()
    compte = {"ok": 0, "echec": 0}
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    f = open(sortie, "a", encoding="utf-8")  # noqa: SIM115 — fermé dans le finally

    def traiter(ligne: dict) -> None:
        metier = ligne.get("metier") or "restaurant"
        for essai in range(essais):
            try:
                analyse = gemini.analyser(client, modele, metier, nom, ligne["texte"],
                                          ligne.get("note"), avec_humeur=True)
                break
            except Exception as erreur:  # quota 429, 5xx, JSON invalide
                code = getattr(erreur, "code", None)
                if isinstance(code, int) and 400 <= code < 500 and code != 429:
                    raise
                if essai == essais - 1:
                    journal.error("avis %s abandonné : %s", ligne["review_id"], erreur)
                    with verrou:
                        compte["echec"] += 1
                    return
                time.sleep(2 ** (essai + 1))
        resultat = dict(ligne, etiquette=etiquettes.depuis_analyse(analyse),
                        source_etiquette="gemini", etiquette_modele=modele)
        with verrou:
            f.write(json.dumps(resultat, ensure_ascii=False) + "\n")
            f.flush()
            compte["ok"] += 1
            if compte["ok"] % 100 == 0:
                journal.info("%d / %d", compte["ok"], len(a_faire))

    try:
        with ThreadPoolExecutor(max_workers=parallelisme) as pool:
            list(pool.map(traiter, a_faire))
    finally:
        f.close()
    return compte
