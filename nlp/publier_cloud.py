"""Publie les résultats NLP maison déjà en BigQuery pour le tableau de bord cloud.

Les tables `avis_historique` et `analyses_maison` sont déjà remplies. Ce module :

1. Ajoute `humeur` / `confiance` dans `avis_analyses` (après Terraform) depuis
   `analyses_maison`, pour que le job web et les vues lisent un seul endroit.
2. Calcule les rapports hebdomadaires à partir des analyses maison (sans Gemini)
   et les MERGE dans `rapports_hebdo`.

    python -m nlp publier-cloud
    python -m nlp publier-cloud --semaines 52 --dry-run
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from watchmybusiness import config as configuration
from watchmybusiness import entrepot, taxonomie
from watchmybusiness.nlp import etiquettes

from .tableau_demo import _extrait, _synthese, classement, tendance

journal = logging.getLogger(__name__)

VERSION_DEFAUT = "fallafel-v3+fallafel-v4"
MODELE_DEFAUT = "maison-fallafel-v3+fallafel-v4"
SEUIL_DEFAUT = 0.92


def synchroniser_analyses(cfg, version: str = VERSION_DEFAUT) -> int:
    """Copie humeur et confiance de analyses_maison → avis_analyses."""
    from google.cloud import bigquery

    sql = f"""
    MERGE {cfg.table('avis_analyses')} T
    USING (
      SELECT review_id, humeur, confiance
      FROM {cfg.table('analyses_maison')}
      WHERE modele LIKE 'maison-%'
    ) S
    ON T.review_id = S.review_id AND T.version_prompt = @version
    WHEN MATCHED THEN UPDATE SET
      humeur = S.humeur,
      confiance = S.confiance
    """
    job = entrepot.client(cfg).query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("version", "STRING", version)]
        ),
    )
    job.result()
    return job.num_dml_affected_rows or 0


def _charger_avis(cfg, version: str) -> list[dict]:
    """Avis avec texte + analyse maison (tables dédiées, déjà peuplées)."""
    return entrepot.requete(
        cfg,
        f"""
        SELECT
          h.review_id, h.etablissement_id, h.date_avis, h.note, h.texte,
          a.sentiment, a.score, a.humeur, a.confiance, a.a_verifier, a.themes, a.modele
        FROM {cfg.table('avis_historique')} h
        JOIN {cfg.table('analyses_maison')} a USING (review_id)
        WHERE h.texte IS NOT NULL AND a.modele LIKE 'maison-%'
        ORDER BY h.date_avis
        """,
    )


def _rapports_depuis_avis(
    avis: list[dict],
    etablissement_id: str,
    version: str,
    modele: str,
    nb_semaines: int,
    seuil: float,
) -> list[dict]:
    par_semaine: dict[date, list[dict]] = defaultdict(list)
    for a in avis:
        if a.get("etablissement_id") and a["etablissement_id"] != etablissement_id:
            continue
        d = a["date_avis"] if isinstance(a["date_avis"], date) else date.fromisoformat(str(a["date_avis"]))
        lignes = []
        themes = []
        for t in a.get("themes") or []:
            theme = t["theme"] if isinstance(t, dict) else t
            polarite = t.get("polarite") if isinstance(t, dict) else None
            if polarite and polarite != "absent":
                themes.append({"theme": theme, "polarite": polarite})
        confiance = float(a["confiance"]) if a.get("confiance") is not None else 1.0
        par_semaine[d - timedelta(days=d.weekday())].append({
            "date_avis": d.isoformat(),
            "note": a.get("note"),
            "texte": a.get("texte") or "",
            "sentiment": a["sentiment"],
            "confiance": confiance,
            "a_verifier": bool(a.get("a_verifier")) if a.get("a_verifier") is not None
            else confiance < seuil,
            "humeur": a.get("humeur"),
            "themes": themes,
            "actionnable": any(t["polarite"] == "negatif" for t in themes),
        })

    lundis = sorted(par_semaine)[-nb_semaines:]
    rapports = []
    precedent = None
    for lundi in lundis:
        semaine = par_semaine[lundi]
        n = len(semaine)
        sent = Counter(l["sentiment"] for l in semaine)
        pct = {s: round(100 * sent[s] / n, 1) for s in etiquettes.SENTIMENTS}
        notes = [l["note"] for l in semaine if l["note"] is not None]
        themes = Counter((t["theme"], t["polarite"]) for l in semaine for t in l["themes"])
        exemples: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for l in sorted(semaine, key=lambda x: -x["confiance"]):
            for t in l["themes"]:
                cle = (t["theme"], t["polarite"])
                if len(exemples[cle]) < 2 and l["texte"]:
                    exemples[cle].append({"extrait": _extrait(l["texte"])})
        iso = lundi.isocalendar()
        scores = [l["confiance"] for l in semaine]
        r = {
            "etablissement_id": etablissement_id,
            "semaine_id": f"{iso[0]}-W{iso[1]:02d}",
            "periode_debut": lundi.isoformat(),
            "periode_fin": (lundi + timedelta(days=6)).isoformat(),
            "nb_avis": n,
            "nb_analyses": n,
            "note_moyenne": round(sum(notes) / len(notes), 2) if notes else None,
            **{f"nb_{s.lower()}": sent[s] for s in etiquettes.SENTIMENTS},
            **{f"pct_{s.lower()}": pct[s] for s in etiquettes.SENTIMENTS},
            "score_moyen": round(sum(scores) / len(scores), 3) if scores else None,
            "nb_actionnables": sum(l["actionnable"] for l in semaine),
            "nb_a_verifier": sum(l["a_verifier"] for l in semaine),
            "tendance": tendance(pct["POSITIF"], pct["NEGATIF"]),
            "top_negatifs": classement(themes, "negatif"),
            "top_positifs": classement(themes, "positif"),
            "humeurs": [{"humeur": h, "nb": c}
                        for h, c in Counter(l["humeur"] for l in semaine if l["humeur"]).most_common()],
            "modele": modele,
            "version_prompt": version,
        }
        for cle, polarite in (("top_negatifs", "negatif"), ("top_positifs", "positif")):
            for t in r[cle]:
                t["libelle"] = taxonomie.libelle(t["theme"])
                t["exemples"] = exemples.get((t["theme"], polarite), [])
        r["synthese"] = _synthese(r, precedent)
        precedent = r
        rapports.append(r)
    return rapports


def publier_rapports(
    cfg,
    version: str = VERSION_DEFAUT,
    modele: str = MODELE_DEFAUT,
    etablissement_id: str = "as-du-fallafel",
    nb_semaines: int = 52,
    seuil: float = SEUIL_DEFAUT,
    dry_run: bool = False,
) -> dict:
    avis = _charger_avis(cfg, version)
    rapports = _rapports_depuis_avis(avis, etablissement_id, version, modele, nb_semaines, seuil)
    if dry_run:
        return {"avis": len(avis), "rapports": len(rapports),
                "semaines": [r["semaine_id"] for r in rapports[-5:]]}
    return {"avis": len(avis), **_ecrire_rapports(cfg, rapports)}


def _charger_avis_gemini(cfg) -> list[dict]:
    return entrepot.requete(
        cfg,
        f"""
        SELECT
          b.review_id, b.etablissement_id, b.date_avis, b.note, b.texte,
          a.sentiment, a.score, a.humeur, a.confiance, a.themes, a.modele
        FROM {cfg.table('avis_bruts')} b
        JOIN {cfg.table('avis_analyses')} a
          ON a.review_id = b.review_id AND a.version_prompt = 'v1'
        WHERE b.texte IS NOT NULL
        ORDER BY b.date_avis
        """,
    )


def _ecrire_rapports(cfg, rapports: list[dict]) -> dict:
    lignes = []
    for r in rapports:
        lignes.append({
            "etablissement_id": r["etablissement_id"],
            "semaine_id": r["semaine_id"],
            "periode_debut": r["periode_debut"],
            "periode_fin": r["periode_fin"],
            "nb_avis": r["nb_avis"],
            "nb_analyses": r["nb_analyses"],
            "note_moyenne": r["note_moyenne"],
            "nb_positif": r["nb_positif"],
            "nb_negatif": r["nb_negatif"],
            "nb_neutre": r["nb_neutre"],
            "nb_mixte": r["nb_mixte"],
            "pct_positif": r["pct_positif"],
            "pct_negatif": r["pct_negatif"],
            "pct_neutre": r["pct_neutre"],
            "pct_mixte": r["pct_mixte"],
            "score_moyen": r["score_moyen"],
            "nb_actionnables": r["nb_actionnables"],
            "tendance": r["tendance"],
            "top_negatifs": json.dumps(
                [{k: t[k] for k in ("theme", "polarite", "occurrences", "part") if k in t}
                 for t in r["top_negatifs"]], ensure_ascii=False),
            "top_positifs": json.dumps(
                [{k: t[k] for k in ("theme", "polarite", "occurrences", "part") if k in t}
                 for t in r["top_positifs"]], ensure_ascii=False),
            "synthese": r["synthese"],
            "modele": r["modele"],
            "version_prompt": r["version_prompt"],
            "genere_le": datetime.now(timezone.utc).isoformat(),
            "statut_email": "non_envoye",
        })
    ecrits = entrepot.fusionner(
        cfg, "rapports_hebdo", lignes, ("etablissement_id", "semaine_id", "version_prompt")
    )
    return {"rapports": len(rapports), "ecrits": ecrits,
            "semaines": [r["semaine_id"] for r in rapports[-5:]]}


def executer(
    semaines: int = 52,
    version: str = VERSION_DEFAUT,
    dry_run: bool = False,
    sans_sync: bool = False,
    aussi_gemini: bool = True,
) -> dict:
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "watch-my-business-512316")
    cfg = configuration.charger()
    bilan: dict = {"version": version, "dry_run": dry_run}
    if not sans_sync and not dry_run:
        try:
            bilan["sync_avis_analyses"] = synchroniser_analyses(cfg, version)
        except Exception as erreur:
            journal.warning("sync humeur/confiance impossible (schéma pas encore à jour ?) : %s", erreur)
            bilan["sync_erreur"] = str(erreur)
    avis = _charger_avis(cfg, version)
    rapports = _rapports_depuis_avis(
        avis, "as-du-fallafel", version, MODELE_DEFAUT, semaines, SEUIL_DEFAUT
    )
    if dry_run:
        bilan.update({"avis": len(avis), "rapports": len(rapports),
                      "semaines": [r["semaine_id"] for r in rapports[-5:]]})
    else:
        bilan.update({"avis": len(avis), **_ecrire_rapports(cfg, rapports)})
    if aussi_gemini:
        try:
            if dry_run:
                avis_g = _charger_avis_gemini(cfg)
                for a in avis_g:
                    if a.get("confiance") is None:
                        a["confiance"] = abs(float(a["score"])) if a.get("score") is not None else 0.8
                r_g = _rapports_depuis_avis(
                    avis_g, "as-du-fallafel", "v1", "gemini-3.5-flash", semaines, SEUIL_DEFAUT
                )
                bilan["gemini"] = {"avis": len(avis_g), "rapports": len(r_g),
                                   "semaines": [r["semaine_id"] for r in r_g[-5:]]}
            else:
                avis_g = _charger_avis_gemini(cfg)
                for a in avis_g:
                    if a.get("confiance") is None:
                        a["confiance"] = abs(float(a["score"])) if a.get("score") is not None else 0.8
                    a["a_verifier"] = False
                r_g = _rapports_depuis_avis(
                    avis_g, "as-du-fallafel", "v1", "gemini-3.5-flash", semaines, SEUIL_DEFAUT
                )
                bilan["gemini"] = _ecrire_rapports(cfg, r_g)
                bilan["gemini"]["avis"] = len(avis_g)
        except Exception as erreur:
            journal.warning("rapports Gemini non publiés : %s", erreur)
            bilan["gemini_erreur"] = str(erreur)
    return bilan
