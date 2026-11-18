"""Comparaison de tous les modèles sur le MÊME jeu de test (idéalement annoté à la main).

    Bayes naïf (plancher) · modèle(s) maison · Gemini (prédictions pré-calculées)

Mesures : F1 macro sentiment, F1 macro humeur, F1 thèmes (paires thème/polarité),
exactitude du sentiment, temps de prédiction par avis.
"""

from __future__ import annotations

import time
from pathlib import Path

from watchmybusiness.nlp import etiquettes

from . import metriques
from .bayes import BayesAvis
from .donnees import lire_jsonl


def scores(vrais: list[dict], predits: list[dict]) -> dict[str, float]:
    res: dict[str, float] = {}
    paires = [(v, p) for v, p in zip(vrais, predits, strict=True) if v.get("sentiment")]
    if paires:
        res["f1_sentiment"] = metriques.f1_macro([v["sentiment"] for v, _ in paires],
                                                 [p.get("sentiment") for _, p in paires],
                                                 etiquettes.SENTIMENTS)
        res["exactitude_sentiment"] = metriques.exactitude(
            [v["sentiment"] for v, _ in paires], [p.get("sentiment") for _, p in paires])
    paires = [(v, p) for v, p in zip(vrais, predits, strict=True) if v.get("humeur")]
    if paires:
        res["f1_humeur"] = metriques.f1_macro([v["humeur"] for v, _ in paires],
                                              [p.get("humeur") for _, p in paires],
                                              etiquettes.HUMEURS)
    paires = [(v, p) for v, p in zip(vrais, predits, strict=True) if v.get("themes") is not None]
    if paires:
        res["f1_themes"] = metriques.f1_ensembles(
            [set(v["themes"].items()) for v, _ in paires],
            [set((p.get("themes") or {}).items()) for _, p in paires])
    return res


def _maison(dossier: str, textes: list[str]) -> tuple[list[dict], float]:
    from watchmybusiness.nlp.service import ModeleMaison

    modele = ModeleMaison(dossier)
    debut = time.perf_counter()
    sorties = []
    for i in range(0, len(textes), 64):
        sorties += modele.predire_lot(textes[i:i + 64])
    duree = time.perf_counter() - debut
    return ([{"sentiment": s["sentiment"], "humeur": s["humeur"],
              "themes": {t["theme"]: t["polarite"] for t in s["themes"]}} for s in sorties],
            duree)


def calibrer_themes(paquet: str | Path, val: str | Path | list, min_exemples: int = 5) -> dict:
    """Seuil de détection par thème, choisi sur la VALIDATION (jamais sur le test) :
    celui qui maximise le F1 (thème, polarité) de ce thème. Écrit
    `seuils_themes.json` dans le paquet ; un thème trop rare en validation garde
    l'argmax."""
    import json

    from watchmybusiness.nlp.service import ModeleMaison, polarite_theme

    fichiers = val if isinstance(val, list) else [val]
    lignes = [l for f in fichiers for l in lire_jsonl(f)
              if l.get("etiquette") and l["etiquette"].get("themes") is not None]
    modele = ModeleMaison(paquet)
    probas = modele.probas_themes([l["texte"] for l in lignes])
    seuils, rapport = {}, {}
    for j, theme in enumerate(modele.themes):
        vrais = [l["etiquette"]["themes"].get(theme) for l in lignes]
        if theme not in modele.themes_appris or sum(v is not None for v in vrais) < min_exemples:
            continue

        def f1(seuil, j=j, vrais=vrais):
            preds = [polarite_theme(p[j], seuil) for p in probas]
            preds = [None if x == "absent" else x for x in preds]
            juste = sum(1 for v, p in zip(vrais, preds, strict=True) if v and p == v)
            nb_p, nb_v = sum(p is not None for p in preds), sum(v is not None for v in vrais)
            return 2 * juste / (nb_p + nb_v) if nb_p + nb_v else 0.0

        base = f1(None)
        meilleur = max((round(0.5 + 0.01 * k, 2) for k in range(50)), key=f1)
        if f1(meilleur) > base:
            seuils[theme] = meilleur
        rapport[theme] = {"argmax": round(base, 3), "seuil": seuils.get(theme),
                          "f1_val": round(max(base, f1(meilleur)), 3)}
    Path(paquet, "seuils_themes.json").write_text(json.dumps(seuils, indent=1))
    return rapport


def comparer(test: str | Path, maisons: list[str], bayes: str | None = None,
             gemini: str | None = None, sortie: str | Path | None = None) -> str:
    lignes = [l for l in lire_jsonl(test) if l.get("etiquette")]
    if not lignes:
        raise SystemExit(f"Aucun avis étiqueté dans {test}.")
    vrais = [l["etiquette"] for l in lignes]
    textes = [l["texte"] for l in lignes]
    tableau: list[tuple[str, dict, float | None]] = []

    if bayes:
        modele = BayesAvis.charger(bayes)
        debut = time.perf_counter()
        pred = modele.predire(textes)
        tableau.append(("Bayes naïf", scores(vrais, pred), time.perf_counter() - debut))
    for dossier in maisons:
        pred, duree = _maison(dossier, textes)
        tableau.append((f"Maison {Path(dossier).parent.name}/{Path(dossier).name}",
                        scores(vrais, pred), duree))
    if gemini:
        par_id = {l["review_id"]: l.get("etiquette") or {} for l in lire_jsonl(gemini)}
        manquants = sum(1 for l in lignes if l["review_id"] not in par_id)
        pred = [par_id.get(l["review_id"], {}) for l in lignes]
        nom = "Gemini" + (f" ({manquants} manquants)" if manquants else "")
        tableau.append((nom, scores(vrais, pred), None))

    colonnes = ["f1_sentiment", "exactitude_sentiment", "f1_humeur", "f1_themes"]
    md = [f"Jeu de test : {test} — {len(lignes)} avis "
          f"(source des étiquettes : {lignes[0].get('source_etiquette')})", "",
          "| Modèle | F1 sentiment | Exactitude sentiment | F1 humeur | F1 thèmes | ms / avis |",
          "|---|---|---|---|---|---|"]
    for nom, s, duree in tableau:
        cellules = [f"{s[c]:.3f}" if c in s else "—" for c in colonnes]
        ms = f"{1000 * duree / len(lignes):.1f}" if duree is not None else "API"
        md.append(f"| {nom} | " + " | ".join(cellules) + f" | {ms} |")
    texte = "\n".join(md)
    if sortie:
        Path(sortie).write_text(texte + "\n", encoding="utf-8")
    return texte
