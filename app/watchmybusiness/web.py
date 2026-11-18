"""Service « web » : tableau de bord statique + API en lecture seule sur BigQuery.

Une seule application Cloud Run sert la page (même origine, donc pas de CORS)
et les routes /api/*. Le compte de service n'a que des droits de lecture.

    GET /api/etablissements
    GET /api/rapports?etablissement=&limite=        liste légère, plus récent d'abord
    GET /api/rapports/{semaine_id}?etablissement=   détail enrichi d'une semaine
    GET /api/avis?etablissement=&debut=&fin=&sentiment=&a_verifier=

SOURCE_DONNEES=local : les mêmes routes lisent un fichier JSON produit par
`python -m nlp tableau-demo` (avis classés par le modèle maison), sans BigQuery.
Utile pour une démonstration hors ligne et sans aucun coût.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from . import config as configuration
from . import entrepot, taxonomie
from .entrepot import serialisable

STATIQUE = Path(__file__).parent / "static"
DUREE_CACHE_S = 300
SENTIMENTS = {"POSITIF", "NEGATIF", "NEUTRE", "MIXTE"}
SEUIL = float(os.environ.get("SEUIL_CONFIANCE", "0.92"))  # sous ce seuil : « à vérifier »
# Version d'analyses à privilégier dans le tableau de bord (ex. fallafel-v3+fallafel-v4).
VERSION_MAISON = os.environ.get("VERSION_MODELE", "fallafel-v3+fallafel-v4").strip()
VERSION_GEMINI = "v1"


def version_pour(moteur: str | None) -> str:
    """maison → NLP fait main ; gemini → analyses Gemini (version_prompt=v1)."""
    if (moteur or "maison").lower() == "gemini":
        return VERSION_GEMINI
    return VERSION_MAISON or VERSION_GEMINI

_cache: dict[str, tuple[float, Any]] = {}
_verrou = threading.Lock()


def _memoriser(cle: str, calculer: Callable[[], Any]) -> Any:
    """BigQuery facture 10 Mo minimum par requête : un cache court évite de
    repayer chaque rechargement de page. Les données changent une fois par jour."""
    maintenant = time.monotonic()
    with _verrou:
        trouve = _cache.get(cle)
        if trouve and maintenant - trouve[0] < DUREE_CACHE_S:
            return trouve[1]
    valeur = calculer()
    with _verrou:
        _cache[cle] = (maintenant, valeur)
    return valeur


# --------------------------------------------------------------------------- #
# Requêtes
# --------------------------------------------------------------------------- #


def etablissements(cfg) -> list[dict]:
    return entrepot.requete(
        cfg,
        f"SELECT etablissement_id, nom, metier FROM {cfg.table('etablissements')} "
        "WHERE actif ORDER BY nom",
    )


def liste_rapports(cfg, etab: str, limite: int, moteur: str | None = None) -> list[dict]:
    version = version_pour(moteur)
    parametres: dict[str, Any] = {"etab": etab, "limite": limite, "version": version}
    lignes = entrepot.requete(
        cfg,
        f"""
        SELECT semaine_id, periode_debut, periode_fin, nb_avis, nb_analyses,
               note_moyenne, pct_positif, pct_negatif, pct_neutre, pct_mixte, tendance,
               modele, version_prompt
        FROM {cfg.table('rapports_hebdo')}
        WHERE etablissement_id = @etab AND version_prompt = @version
          AND IFNULL(nb_avis, 0) > 0
        ORDER BY periode_debut DESC
        LIMIT @limite
        """,
        parametres,
    )
    return [serialisable(l) for l in lignes]


def detail_rapport(cfg, etab: str, semaine_id: str, moteur: str | None = None) -> dict | None:
    version = version_pour(moteur)
    lignes = entrepot.requete(
        cfg,
        f"SELECT * FROM {cfg.table('rapports_hebdo')} "
        "WHERE etablissement_id = @etab AND semaine_id = @semaine "
        "AND version_prompt = @version",
        {"etab": etab, "semaine": semaine_id, "version": version},
    )
    if not lignes:
        return None
    r = serialisable(lignes[0])
    debut, fin = date.fromisoformat(r["periode_debut"]), date.fromisoformat(r["periode_fin"])

    precedent = entrepot.requete(
        cfg,
        f"SELECT semaine_id, pct_positif, note_moyenne FROM {cfg.table('rapports_hebdo')} "
        "WHERE etablissement_id = @etab AND periode_debut = @debut AND version_prompt = @version",
        {"etab": etab, "debut": debut - timedelta(days=7), "version": version},
    )
    r["comparaison_semaine_precedente"] = (
        {
            "semaine_id": precedent[0]["semaine_id"],
            "delta_pct_positif": round(r["pct_positif"] - float(precedent[0]["pct_positif"]), 1),
        }
        if precedent
        else None
    )

    est_maison = version != VERSION_GEMINI
    table_volume = cfg.table("avis_historique") if est_maison else cfg.table("avis_bruts")
    par_jour = {
        (l["date_avis"].isoformat() if hasattr(l["date_avis"], "isoformat") else str(l["date_avis"])): l["nb"]
        for l in entrepot.requete(
            cfg,
            f"SELECT date_avis, COUNT(*) AS nb FROM {table_volume} "
            "WHERE etablissement_id = @etab AND date_avis BETWEEN @debut AND @fin GROUP BY 1",
            {"etab": etab, "debut": debut, "fin": fin},
        )
    }
    r["volume_par_jour"] = [
        {
            "date": (debut + timedelta(days=i)).isoformat(),
            "nb_avis": par_jour.get((debut + timedelta(days=i)).isoformat(), 0),
        }
        for i in range((fin - debut).days + 1)
    ]

    version = r.get("version_prompt") or version
    p = {"etab": etab, "version": version, "debut": debut, "fin": fin}
    est_maison = version != VERSION_GEMINI
    table_a = cfg.table("analyses_maison") if est_maison else cfg.table("avis_analyses")
    table_h = cfg.table("avis_historique") if est_maison else cfg.table("avis_bruts")
    filtre = "a.etablissement_id = @etab AND a.date_avis BETWEEN @debut AND @fin"
    if not est_maison:
        filtre += " AND a.version_prompt = @version"

    citations: dict[tuple[str, str], list[dict]] = {}
    for l in entrepot.requete(
        cfg,
        f"""
        SELECT t.theme, t.polarite, LEFT(h.texte, 160) AS extrait, a.score
        FROM {table_a} a
        JOIN {table_h} h USING (review_id)
        , UNNEST(a.themes) t
        WHERE {filtre} AND h.texte IS NOT NULL AND t.polarite != 'absent'
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY t.theme, t.polarite ORDER BY ABS(IFNULL(a.score, 0)) DESC
        ) <= 2
        """,
        p,
    ):
        citations.setdefault((l["theme"], l["polarite"]), []).append({"extrait": l["extrait"]})

    r["humeurs"] = entrepot.requete(
        cfg, f"SELECT humeur, COUNT(*) AS nb FROM {table_a} a "
             f"WHERE {filtre} AND humeur IS NOT NULL GROUP BY 1 ORDER BY nb DESC", p)
    matrice: dict[str, dict] = {}
    for l in entrepot.requete(
        cfg, f"SELECT t.theme, t.polarite, COUNT(*) AS nb FROM {table_a} a, "
             f"UNNEST(a.themes) t WHERE {filtre} AND t.polarite != 'absent' GROUP BY 1, 2", p):
        ligne = matrice.setdefault(l["theme"], {"theme": l["theme"], "positif": 0, "negatif": 0,
                                                "neutre": 0,
                                                "libelle": taxonomie.libelle(l["theme"])})
        ligne[l["polarite"]] = l["nb"]
    r["themes_matrice"] = list(matrice.values())
    r["nb_a_verifier"] = entrepot.requete(
        cfg, f"SELECT COUNTIF(IFNULL(confiance, 1) < @seuil) AS nb FROM {table_a} a "
             f"WHERE {filtre}", {**p, "seuil": SEUIL})[0]["nb"]

    for cle, polarite in (("top_negatifs", "negatif"), ("top_positifs", "positif")):
        themes = json.loads(r.get(cle) or "[]")
        for theme in themes:
            theme["libelle"] = taxonomie.libelle(theme["theme"])
            theme["exemples"] = citations.get((theme["theme"], polarite), [])
        r[cle] = themes
    return r


def liste_avis(cfg, etab: str, debut: date, fin: date, sentiment: str | None,
               moteur: str | None = None) -> list[dict]:
    filtre = "AND a.sentiment = @sentiment" if sentiment else ""
    parametres: dict[str, Any] = {"etab": etab, "debut": debut, "fin": fin}
    if sentiment:
        parametres["sentiment"] = sentiment
    version = version_pour(moteur)
    if version != VERSION_GEMINI:
        lignes = entrepot.requete(
            cfg,
            f"""
            SELECT h.review_id, h.date_avis, h.note, h.texte,
                   CAST(NULL AS STRING) AS url_avis,
                   a.sentiment, a.score, CAST(NULL AS STRING) AS resume,
                   a.humeur, a.confiance,
                   ARRAY(SELECT AS STRUCT t.theme, t.polarite FROM UNNEST(a.themes) t) AS themes
            FROM {cfg.table('avis_historique')} h
            JOIN {cfg.table('analyses_maison')} a USING (review_id)
            WHERE h.etablissement_id = @etab AND h.date_avis BETWEEN @debut AND @fin
              AND h.texte IS NOT NULL {filtre}
            ORDER BY h.date_avis DESC
            LIMIT 200
            """,
            parametres,
        )
    else:
        parametres["version"] = version
        lignes = entrepot.requete(
            cfg,
            f"""
            SELECT b.review_id, b.date_avis, b.note, b.texte, b.url_avis,
                   a.sentiment, a.score, a.resume, a.humeur, a.confiance,
                   ARRAY(SELECT AS STRUCT t.theme, t.polarite FROM UNNEST(a.themes) t) AS themes
            FROM {cfg.table('avis_bruts')} b
            JOIN {cfg.table('avis_analyses')} a
              ON a.review_id = b.review_id AND a.version_prompt = @version
            WHERE b.etablissement_id = @etab AND b.date_avis BETWEEN @debut AND @fin
              AND b.texte IS NOT NULL {filtre}
            ORDER BY b.date_avis DESC, b.publie_le DESC
            LIMIT 200
            """,
            parametres,
        )
    for ligne in lignes:
        ligne["themes"] = [{"theme": t["theme"], "libelle": taxonomie.libelle(t["theme"]),
                            "polarite": t["polarite"]} for t in ligne["themes"] or []]
        ligne["a_verifier"] = ligne.get("confiance") is not None and ligne["confiance"] < SEUIL
    return [serialisable(l) for l in lignes]


class SourceLocale:
    """Mêmes réponses que BigQuery, lues dans le JSON de `python -m nlp tableau-demo`."""

    def __init__(self, chemin: str | Path):
        self.donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))

    def etablissements(self) -> list[dict]:
        return self.donnees["etablissements"]

    def liste_rapports(self, etab: str, limite: int) -> list[dict]:
        rapports = [r for r in self.donnees["rapports"] if r["etablissement_id"] == etab]
        return sorted(rapports, key=lambda r: r["periode_debut"], reverse=True)[:limite]

    def detail_rapport(self, etab: str, semaine_id: str) -> dict | None:
        rapports = sorted((r for r in self.donnees["rapports"] if r["etablissement_id"] == etab),
                          key=lambda r: r["periode_debut"])
        for i, r in enumerate(rapports):
            if r["semaine_id"] != semaine_id:
                continue
            r = dict(r)
            precedent = rapports[i - 1] if i else None
            r["comparaison_semaine_precedente"] = (
                {"semaine_id": precedent["semaine_id"],
                 "delta_pct_positif": round(r["pct_positif"] - precedent["pct_positif"], 1)}
                if precedent else None)
            debut = date.fromisoformat(r["periode_debut"])
            fin = date.fromisoformat(r["periode_fin"])
            par_jour: dict[str, int] = {}
            for a in self.donnees["avis"]:
                if r["periode_debut"] <= a["date_avis"] <= r["periode_fin"]:
                    par_jour[a["date_avis"]] = par_jour.get(a["date_avis"], 0) + 1
            r["volume_par_jour"] = [
                {"date": (debut + timedelta(days=k)).isoformat(),
                 "nb_avis": par_jour.get((debut + timedelta(days=k)).isoformat(), 0)}
                for k in range((fin - debut).days + 1)]
            return r
        return None

    def liste_avis(self, etab: str, debut: date, fin: date, sentiment: str | None,
                   a_verifier: bool = False) -> list[dict]:
        avis = [a for a in self.donnees["avis"]
                if debut.isoformat() <= a["date_avis"] <= fin.isoformat()
                and (not sentiment or a["sentiment"] == sentiment)
                and (not a_verifier or a["a_verifier"])]
        return sorted(avis, key=lambda a: a["date_avis"], reverse=True)[:200]


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #


def creer_application():
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.staticfiles import StaticFiles

    app = FastAPI(title="WatchMyBusiness", docs_url=None, redoc_url=None)
    if os.environ.get("SOURCE_DONNEES") == "local":
        locale = SourceLocale(os.environ.get("DONNEES_LOCALES", "data/demo/tableau.json"))
        source = SimpleNamespace(
            etablissements=locale.etablissements, liste_rapports=locale.liste_rapports,
            detail_rapport=locale.detail_rapport, liste_avis=locale.liste_avis)
    else:
        cfg = configuration.charger()
        source = SimpleNamespace(
            etablissements=lambda: etablissements(cfg),
            liste_rapports=lambda e, n, m=None: liste_rapports(cfg, e, n, m),
            detail_rapport=lambda e, s, m=None: detail_rapport(cfg, e, s, m),
            liste_avis=lambda e, d, f, s, v=False, m=None: [
                a for a in liste_avis(cfg, e, d, f, s, m) if not v or a["a_verifier"]])

    @app.get("/api/etablissements")
    def route_etablissements():
        return {"etablissements": _memoriser("etab", source.etablissements)}

    @app.get("/api/rapports")
    def route_rapports(etablissement: str, limite: int = Query(12, ge=1, le=52),
                       moteur: str = Query("maison")):
        return {
            "rapports": _memoriser(
                f"liste:{etablissement}:{limite}:{moteur}",
                lambda: source.liste_rapports(etablissement, limite, moteur),
            )
        }

    @app.get("/api/rapports/{semaine_id}")
    def route_rapport(semaine_id: str, etablissement: str, moteur: str = Query("maison")):
        r = _memoriser(
            f"detail:{etablissement}:{semaine_id}:{moteur}",
            lambda: source.detail_rapport(etablissement, semaine_id, moteur),
        )
        if r is None:
            raise HTTPException(404, f"rapport {semaine_id} introuvable")
        return r

    @app.get("/api/avis")
    def route_avis(etablissement: str, debut: date, fin: date, sentiment: str | None = None,
                   a_verifier: bool = False, moteur: str = Query("maison")):
        if sentiment and sentiment not in SENTIMENTS:
            raise HTTPException(400, f"sentiment inconnu : {sentiment}")
        if (fin - debut).days > 62:
            raise HTTPException(400, "période limitée à 62 jours")
        avis = _memoriser(
            f"avis:{etablissement}:{debut}:{fin}:{sentiment}:{a_verifier}:{moteur}",
            lambda: source.liste_avis(etablissement, debut, fin, sentiment, a_verifier, moteur),
        )
        return {"nb": len(avis), "avis": avis}

    @app.get("/api/sante")
    def route_sante():
        return {"statut": "ok"}

    app.mount("/", StaticFiles(directory=STATIQUE, html=True), name="statique")
    return app


def servir() -> int:
    import uvicorn

    uvicorn.run(
        creer_application(),
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        log_level="warning",
    )
    return 0
