"""Données du tableau de bord en mode démo, produites par NOTRE modèle, sans BigQuery.

    python -m nlp tableau-demo --paquet modeles/fallafel/nlp-S-duo \
        --avis "data/l'asdefalafel/avis.jsonl" "data/l'asdefalafel/tripadvisor/avis.jsonl"

Chaque avis est classé par le modèle maison (sentiment, humeur, thèmes, confiance),
puis les rapports hebdomadaires sont calculés comme dans `rapport.py` (mêmes
indicateurs, même règle de tendance, même classement des thèmes). La synthèse est
un texte factuel construit à partir des indicateurs : aucun modèle externe.

Le fichier produit est lu par `web.py` quand SOURCE_DONNEES=local.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from watchmybusiness import taxonomie
from watchmybusiness.nlp import etiquettes

from .donnees import lire_jsonl

SEUIL_TENDANCE = 15.0  # identique à rapport.SEUIL_TENDANCE
NB_THEMES = 5  # identique à rapport.NB_THEMES


def tendance(pct_positif: float, pct_negatif: float) -> str:
    ecart = pct_positif - pct_negatif
    if ecart > SEUIL_TENDANCE:
        return "positive"
    if ecart < -SEUIL_TENDANCE:
        return "negative"
    return "mitigee"


def classement(compte: Counter, polarite: str) -> list[dict]:
    retenus = [(t, n) for (t, p), n in compte.items() if p == polarite]
    total = sum(n for _, n in retenus) or 1
    return [{"theme": t, "polarite": polarite, "occurrences": n,
             "part": round(100 * n / total, 1)}
            for t, n in sorted(retenus, key=lambda x: -x[1])[:NB_THEMES]]


def _extrait(texte: str, longueur: int = 160) -> str:
    texte = " ".join(texte.split())
    return texte if len(texte) <= longueur else texte[:longueur].rsplit(" ", 1)[0] + "…"


def _nb(n: int, mot: str) -> str:
    return f"{n} {mot}{'s' if n > 1 else ''}"


def _fr(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _synthese(r: dict, precedent: dict | None) -> str:
    lignes = ["## En bref"]
    evolution = ""
    if precedent:
        delta = round(r["pct_positif"] - precedent["pct_positif"], 1)
        signe = "+" if delta >= 0 else ""
        evolution = f" ({signe}{_fr(delta)} pts par rapport à la semaine précédente)"
    note = _fr(r["note_moyenne"] or 0)
    lignes.append(f"- **{r['nb_avis']} avis** reçus, note moyenne **{note} / 5**.")
    lignes.append(f"- **{_fr(r['pct_positif'])} %** d'avis positifs et "
                  f"**{_fr(r['pct_negatif'])} %** de négatifs{evolution}.")
    for cle, titre, mot in (("top_negatifs", "Ce qui a posé problème", "avis négatif"),
                            ("top_positifs", "Ce qui a bien fonctionné", "avis positif")):
        if r[cle]:
            lignes.append(f"## {titre}")
            lignes += [f"- **{taxonomie.libelle(t['theme'])}** : {_nb(t['occurrences'], mot)}"
                       for t in r[cle][:3]]
    if r["nb_a_verifier"]:
        lignes.append("## À vérifier")
        lignes.append(f"- {r['nb_a_verifier']} avis sur lesquels le modèle hésite : "
                      "à relire avant d'agir.")
    return "\n".join(lignes)


def construire(paquet: str | Path, fichiers_avis: list[str | Path], sortie: str | Path,
               etablissement_id: str = "as-du-fallafel", nom: str = "L'As du Fallafel",
               nb_semaines: int = 26) -> dict:
    from watchmybusiness.nlp.service import ModeleMaison

    avis = {}
    for f in fichiers_avis:
        for l in lire_jsonl(f):
            if l.get("texte") and l.get("date_avis"):
                avis[l["review_id"]] = l
    avis = sorted(avis.values(), key=lambda l: l["date_avis"])
    modele = ModeleMaison(paquet)
    predictions = []
    for i in range(0, len(avis), 64):
        predictions += modele.predire_lot([a["texte"] for a in avis[i:i + 64]])

    lignes_avis = []
    for a, p in zip(avis, predictions, strict=True):
        source = "TripAdvisor" if a["review_id"].startswith("tripadvisor-") else "Google"
        lignes_avis.append({
            "review_id": a["review_id"], "date_avis": a["date_avis"][:10],
            "note": a.get("note"), "texte": a["texte"], "langue": a.get("langue"),
            "source": source, "url_avis": None,
            "sentiment": p["sentiment"], "score": p["score"], "humeur": p["humeur"],
            "confiance": p["confiance"], "a_verifier": p["confiance"] < modele.seuil,
            "themes": [{"theme": t["theme"], "libelle": taxonomie.libelle(t["theme"]),
                        "polarite": t["polarite"]} for t in p["themes"]],
            "actionnable": p["actionnable"],
        })

    # Semaines ISO (lundi → dimanche), les plus récentes.
    par_semaine: dict[date, list[dict]] = defaultdict(list)
    for l in lignes_avis:
        d = date.fromisoformat(l["date_avis"])
        par_semaine[d - timedelta(days=d.weekday())].append(l)
    lundis = sorted(par_semaine)[-nb_semaines:]

    rapports = []
    precedent = None
    for lundi in lundis:
        semaine = par_semaine[lundi]
        n = len(semaine)
        sent = Counter(l["sentiment"] for l in semaine)
        pct = {s: round(100 * sent[s] / n, 1) for s in etiquettes.SENTIMENTS}
        notes = [l["note"] for l in semaine if l["note"]]
        themes = Counter((t["theme"], t["polarite"]) for l in semaine for t in l["themes"])
        exemples: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for l in sorted(semaine, key=lambda l: -l["confiance"]):
            for t in l["themes"]:
                cle = (t["theme"], t["polarite"])
                if len(exemples[cle]) < 2:
                    exemples[cle].append({"extrait": _extrait(l["texte"])})
        iso = lundi.isocalendar()
        r = {
            "etablissement_id": etablissement_id,
            "semaine_id": f"{iso[0]}-W{iso[1]:02d}",
            "periode_debut": lundi.isoformat(),
            "periode_fin": (lundi + timedelta(days=6)).isoformat(),
            "nb_avis": n, "nb_analyses": n,
            "note_moyenne": round(sum(notes) / len(notes), 2) if notes else None,
            **{f"nb_{s.lower()}": sent[s] for s in etiquettes.SENTIMENTS},
            **{f"pct_{s.lower()}": pct[s] for s in etiquettes.SENTIMENTS},
            "nb_actionnables": sum(l["actionnable"] for l in semaine),
            "nb_a_verifier": sum(l["a_verifier"] for l in semaine),
            "tendance": tendance(pct["POSITIF"], pct["NEGATIF"]),
            "top_negatifs": classement(themes, "negatif"),
            "top_positifs": classement(themes, "positif"),
            "humeurs": [{"humeur": h, "nb": c}
                        for h, c in Counter(l["humeur"] for l in semaine).most_common()],
            "themes_matrice": [
                {"theme": t, "libelle": taxonomie.libelle(t),
                 **{p: themes[(t, p)] for p in ("positif", "negatif", "neutre")}}
                for t in etiquettes.themes() if any(themes[(t, p)] for p in
                                                    ("positif", "negatif", "neutre"))],
            "modele": f"NLP maison {modele.version}",
        }
        for cle, polarite in (("top_negatifs", "negatif"), ("top_positifs", "positif")):
            for t in r[cle]:
                t["libelle"] = taxonomie.libelle(t["theme"])
                t["exemples"] = exemples[(t["theme"], polarite)]
        r["synthese"] = _synthese(r, precedent)
        precedent = r
        rapports.append(r)

    jeu = {"etablissements": [{"etablissement_id": etablissement_id, "nom": nom,
                               "metier": "restaurant"}],
           "modele": {"version": modele.version, "seuil_confiance": modele.seuil},
           "rapports": rapports,
           "avis": [l for l in lignes_avis if date.fromisoformat(l["date_avis"]) >= lundis[0]]}
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    Path(sortie).write_text(json.dumps(jeu, ensure_ascii=False), encoding="utf-8")
    return {"avis_classes": len(lignes_avis), "semaines": len(rapports),
            "avis_dans_le_tableau": len(jeu["avis"]), "sortie": str(sortie)}
