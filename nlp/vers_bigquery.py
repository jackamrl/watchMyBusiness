"""Fichiers à charger dans BigQuery : tous les avis collectés + les analyses de notre modèle.

    python -m nlp vers-bigquery            # écrit data/bigquery/*.jsonl et *.schema.json

Puis (chargement par fichier : gratuit, contrairement à l'insertion en continu) :

    bq load --source_format=NEWLINE_DELIMITED_JSON --replace \
        PROJET:watchmybusiness.avis_historique data/bigquery/avis_historique.jsonl \
        data/bigquery/avis_historique.schema.json

Les tables `avis_historique` et `analyses_maison` sont volontairement SÉPARÉES de
`avis_bruts` / `avis_analyses` : le job d'analyse quotidien ne les lit pas, donc
aucun avis historique n'est renvoyé à une API payante.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .donnees import ecrire_jsonl, lire_jsonl

SCHEMA_AVIS = [
    {"name": "review_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "etablissement_id", "type": "STRING"},
    {"name": "source", "type": "STRING", "description": "Google ou TripAdvisor"},
    {"name": "date_avis", "type": "DATE"},
    {"name": "note", "type": "INT64"},
    {"name": "texte", "type": "STRING"},
    {"name": "langue", "type": "STRING"},
    {"name": "texte_traduit", "type": "STRING"},
    {"name": "reponse_proprietaire", "type": "STRING"},
    {"name": "notes_detaillees", "type": "STRING", "description": "JSON : Cuisine, Service…"},
    {"name": "jeu", "type": "STRING", "description": "train / val / test du modèle"},
]

SCHEMA_ANALYSES = [
    {"name": "review_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "etablissement_id", "type": "STRING"},
    {"name": "date_avis", "type": "DATE"},
    {"name": "sentiment", "type": "STRING"},
    {"name": "score", "type": "FLOAT64"},
    {"name": "humeur", "type": "STRING"},
    {"name": "confiance", "type": "FLOAT64"},
    {"name": "a_verifier", "type": "BOOL"},
    {"name": "themes", "type": "RECORD", "mode": "REPEATED", "fields": [
        {"name": "theme", "type": "STRING"}, {"name": "polarite", "type": "STRING"}]},
    {"name": "modele", "type": "STRING"},
    {"name": "analyse_le", "type": "TIMESTAMP"},
]


def construire(dossier_avis: str | Path, paquet: str | Path, sortie: str | Path) -> dict:
    from watchmybusiness.apify import normaliser
    from watchmybusiness.nlp.service import ModeleMaison

    dossier_avis, sortie = Path(dossier_avis), Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)

    # Jeu (train / val / test) de chaque avis, pour pouvoir filtrer dans BigQuery.
    jeu = {}
    for nom in ("train", "val", "test"):
        for l in lire_jsonl(dossier_avis / f"{nom}.jsonl"):
            jeu[l["review_id"]] = nom

    # 1) Tous les avis Google, y compris ceux sans texte (note seule).
    items = []
    for f in sorted(dossier_avis.glob("dataset_*.json")):
        contenu = json.loads(f.read_text(encoding="utf-8"))
        for item in contenu if isinstance(contenu, list) else []:
            items += item["reviews"] if isinstance(item.get("reviews"), list) else [item]
    avis: dict[str, dict] = {}
    texte_modele = {l["review_id"]: l for f in ("avis.jsonl", "train_lot2.jsonl")
                    for l in lire_jsonl(dossier_avis / f)}
    for l in normaliser(items, "as-du-fallafel", datetime.now(UTC)):
        brut = l["brut"]
        ligne = texte_modele.get(l["review_id"], {})
        avis[l["review_id"]] = {
            "review_id": l["review_id"], "etablissement_id": "as-du-fallafel", "source": "Google",
            "date_avis": str(l["date_avis"])[:10] if l["date_avis"] else None,
            "note": l["note"], "texte": ligne.get("texte") or l.get("texte"),
            "langue": l["langue"], "texte_traduit": ligne.get("texte_traduit"),
            "reponse_proprietaire": l["reponse_proprietaire"],
            "notes_detaillees": json.dumps(brut.get("reviewDetailedRating"), ensure_ascii=False)
            if brut.get("reviewDetailedRating") else None,
            "jeu": jeu.get(l["review_id"], "lot2" if l["review_id"] in texte_modele else None),
        }
    # 2) TripAdvisor.
    for l in lire_jsonl(dossier_avis / "tripadvisor" / "avis.jsonl"):
        avis[l["review_id"]] = {
            "review_id": l["review_id"], "etablissement_id": "as-du-fallafel",
            "source": "TripAdvisor", "date_avis": l["date_avis"], "note": l["note"],
            "texte": l["texte"], "langue": l["langue"], "texte_traduit": None,
            "reponse_proprietaire": None,
            "notes_detaillees": json.dumps(l["notes_detaillees"], ensure_ascii=False)
            if l.get("notes_detaillees") else None,
            "jeu": "train",
        }

    # 3) Analyses de notre modèle sur tous les avis qui ont un texte.
    modele = ModeleMaison(paquet)
    avec_texte = [a for a in avis.values() if a["texte"]]
    predictions = []
    for i in range(0, len(avec_texte), 64):
        predictions += modele.predire_lot([a["texte"] for a in avec_texte[i:i + 64]])
    maintenant = datetime.now(UTC).isoformat()
    analyses = [{
        "review_id": a["review_id"], "etablissement_id": a["etablissement_id"],
        "date_avis": a["date_avis"], "sentiment": p["sentiment"], "score": p["score"],
        "humeur": p["humeur"], "confiance": p["confiance"],
        "a_verifier": p["confiance"] < modele.seuil,
        "themes": [{"theme": t["theme"], "polarite": t["polarite"]} for t in p["themes"]],
        "modele": f"maison-{modele.version}", "analyse_le": maintenant,
    } for a, p in zip(avec_texte, predictions, strict=True)]

    ecrire_jsonl(sortie / "avis_historique.jsonl", avis.values())
    ecrire_jsonl(sortie / "analyses_maison.jsonl", analyses)
    (sortie / "avis_historique.schema.json").write_text(json.dumps(SCHEMA_AVIS, indent=1))
    (sortie / "analyses_maison.schema.json").write_text(json.dumps(SCHEMA_ANALYSES, indent=1))
    taille = sum(f.stat().st_size for f in sortie.glob("*.jsonl"))
    return {"avis": len(avis), "avec_texte": len(avec_texte), "analyses": len(analyses),
            "taille_mo": round(taille / 1e6, 1), "dossier": str(sortie)}


# --------------------------------------------------------------------------- #
# Chargement dans les tables DU PIPELINE (avis_bruts, avis_analyses)
# --------------------------------------------------------------------------- #


def vers_pipeline(dossier_avis: str | Path, paquet: str | Path, appliquer: bool = False) -> dict:
    """Tous les avis dans `avis_bruts`, leurs analyses dans `avis_analyses`.

    Garde-fou de coût : le job quotidien envoie à Gemini tout avis avec texte qui
    n'a pas d'analyse en version `gemini.VERSION_PROMPT`. Chaque avis chargé ici
    arrive donc AVEC son étiquette Gemini déjà produite (même version), et le job
    le saute. On n'ajoute que des lignes (MERGE sans mise à jour) : les données
    déjà présentes ne sont jamais modifiées. Sans `appliquer`, rien n'est écrit.
    """
    from watchmybusiness import apify, entrepot, gemini
    from watchmybusiness import config as configuration
    from watchmybusiness.nlp.service import ModeleMaison

    dossier_avis = Path(dossier_avis)
    maintenant = datetime.now(UTC)

    # 1) Avis bruts : Google tels que le pipeline les normalise, puis TripAdvisor.
    items = []
    for f in sorted(dossier_avis.glob("dataset_Google-Maps-Reviews-Scraper_*.json")):
        items += json.loads(f.read_text(encoding="utf-8"))
    bruts = {l["review_id"]: l for l in apify.normaliser(items, "as-du-fallafel", maintenant)}
    for f in sorted((dossier_avis / "tripadvisor").glob("dataset_*.json")):
        for it in json.loads(f.read_text(encoding="utf-8")):
            rid = f"tripadvisor-{it.get('id')}"
            texte = " ".join(filter(None, [(it.get("title") or "").strip(),
                                           (it.get("text") or "").strip()]))
            date = (it.get("publishedDate") or "")[:10]
            if rid in bruts or not date:
                continue
            bruts[rid] = {
                "review_id": rid, "etablissement_id": "as-du-fallafel", "date_avis": date,
                "publie_le": f"{date}T12:00:00+00:00",
                "note": int(it["rating"]) if it.get("rating") else None,
                "texte": texte or None, "langue": it.get("lang"), "url_avis": it.get("url"),
                "reponse_proprietaire": None, "brut": it, "collecte_le": maintenant.isoformat(),
            }

    # 2) Étiquettes Gemini déjà produites (version du pipeline) pour chaque avis avec texte.
    etiquettes = {}
    for f in ("train_gemini.jsonl", "val_gemini.jsonl", "test_gemini.jsonl",
              "train_lot2_gemini.jsonl", "tripadvisor/avis_gemini.jsonl"):
        for l in lire_jsonl(dossier_avis / f):
            if l.get("etiquette"):
                etiquettes[l["review_id"]] = l
    # Un avis avec texte mais sans étiquette (autre langue, période du test TripAdvisor)
    # partirait au job Gemini : on ne le charge pas.
    ecartes = [r for r, b in bruts.items() if b["texte"] and r not in etiquettes]
    for r in ecartes:
        del bruts[r]
    avec_texte = [b for b in bruts.values() if b["texte"]]
    sans_etiquette = [b["review_id"] for b in avec_texte if b["review_id"] not in etiquettes]

    analyses = []
    for b in avec_texte:
        l = etiquettes.get(b["review_id"])
        if not l:
            continue
        e = l["etiquette"]
        themes = [{"theme": t, "polarite": p, "extrait": ""}
                  for t, p in (e.get("themes") or {}).items()]
        analyses.append({
            "review_id": b["review_id"], "etablissement_id": "as-du-fallafel",
            "date_avis": b["date_avis"], "note": b["note"], "sentiment": e["sentiment"],
            "score": None, "themes": themes, "theme_emergent": None,
            "actionnable": any(t["polarite"] == "negatif" for t in themes), "resume": "",
            "humeur": e.get("humeur"), "confiance": None,
            "modele": l.get("etiquette_modele") or "gemini",
            "version_prompt": gemini.VERSION_PROMPT, "analyse_le": maintenant.isoformat(),
        })

    # 3) Analyses de notre modèle, sous sa propre version (comparaison dans BigQuery).
    modele = ModeleMaison(paquet)
    predictions = []
    for i in range(0, len(avec_texte), 64):
        predictions += modele.predire_lot([b["texte"] for b in avec_texte[i:i + 64]])
    for b, p in zip(avec_texte, predictions, strict=True):
        analyses.append({
            "review_id": b["review_id"], "etablissement_id": "as-du-fallafel",
            "date_avis": b["date_avis"], "note": b["note"], "sentiment": p["sentiment"],
            "score": p["score"],
            "themes": [{"theme": t["theme"], "polarite": t["polarite"], "extrait": ""}
                       for t in p["themes"]],
            "theme_emergent": None, "actionnable": p["actionnable"], "resume": "",
            "humeur": p["humeur"], "confiance": p["confiance"],
            "modele": f"maison-{modele.version}", "version_prompt": modele.version,
            "analyse_le": maintenant.isoformat(),
        })

    bilan = {"avis_bruts": len(bruts), "avec_texte": len(avec_texte),
             "analyses_gemini": sum(a["version_prompt"] == gemini.VERSION_PROMPT for a in analyses),
             "analyses_maison": sum(a["version_prompt"] == modele.version for a in analyses),
             "avec_texte_sans_etiquette": len(sans_etiquette), "ecartes": len(ecartes)}
    if not appliquer:
        return bilan
    if sans_etiquette:
        raise SystemExit(f"{len(sans_etiquette)} avis avec texte sans étiquette Gemini : ils "
                         "partiraient au job Gemini payant. Rien n'a été écrit.")
    cfg = configuration.charger()

    # Le schéma déployé peut être en retard sur Terraform (ex. pas de colonne humeur) :
    # on n'envoie que les colonnes qui existent réellement.
    def colonnes(table: str) -> set[str]:
        return {c.name for c in entrepot.client(cfg).get_table(cfg.table_id(table)).schema}

    gardees = colonnes("avis_analyses")
    bilan["colonnes_ignorees"] = sorted({k for a in analyses for k in a} - gardees)
    analyses = [{k: v for k, v in a.items() if k in gardees} for a in analyses]
    lignes_bruts = [{**b, "brut": json.loads(json.dumps(b["brut"], default=str))}
                    for b in bruts.values()]
    # Les analyses d'abord : un avis n'apparaît jamais sans son analyse.
    bilan["ecrit_avis_analyses"] = entrepot.fusionner(
        cfg, "avis_analyses", analyses, ("review_id", "version_prompt"), mettre_a_jour=False)
    bilan["ecrit_avis_bruts"] = entrepot.fusionner(
        cfg, "avis_bruts", lignes_bruts, ("review_id",), mettre_a_jour=False)
    return bilan
