"""Service « web » : tableau de bord statique + API en lecture seule sur BigQuery.

Une seule application Cloud Run sert la page (même origine, donc pas de CORS)
et les routes /api/*. Le compte de service n'a que des droits de lecture.

    GET /api/etablissements
    GET /api/rapports?etablissement=&limite=        liste légère, plus récent d'abord
    GET /api/rapports/{semaine_id}?etablissement=   détail enrichi d'une semaine
    GET /api/avis?etablissement=&debut=&fin=&sentiment=
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from . import config as configuration
from . import entrepot, taxonomie
from .entrepot import serialisable

STATIQUE = Path(__file__).parent / "static"
DUREE_CACHE_S = 300
SENTIMENTS = {"POSITIF", "NEGATIF", "NEUTRE", "MIXTE"}

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


def liste_rapports(cfg, etab: str, limite: int) -> list[dict]:
    lignes = entrepot.requete(
        cfg,
        f"""
        SELECT semaine_id, periode_debut, periode_fin, nb_avis, nb_analyses,
               note_moyenne, pct_positif, pct_negatif, pct_neutre, pct_mixte, tendance
        FROM {cfg.table('rapports_hebdo')}
        WHERE etablissement_id = @etab
        ORDER BY periode_debut DESC
        LIMIT @limite
        """,
        {"etab": etab, "limite": limite},
    )
    return [serialisable(l) for l in lignes]


def detail_rapport(cfg, etab: str, semaine_id: str) -> dict | None:
    lignes = entrepot.requete(
        cfg,
        f"SELECT * FROM {cfg.table('rapports_hebdo')} "
        "WHERE etablissement_id = @etab AND semaine_id = @semaine",
        {"etab": etab, "semaine": semaine_id},
    )
    if not lignes:
        return None
    r = serialisable(lignes[0])
    debut, fin = date.fromisoformat(r["periode_debut"]), date.fromisoformat(r["periode_fin"])

    precedent = entrepot.requete(
        cfg,
        f"SELECT semaine_id, pct_positif, note_moyenne FROM {cfg.table('rapports_hebdo')} "
        "WHERE etablissement_id = @etab AND periode_debut = @debut",
        {"etab": etab, "debut": debut - timedelta(days=7)},
    )
    r["comparaison_semaine_precedente"] = (
        {
            "semaine_id": precedent[0]["semaine_id"],
            "delta_pct_positif": round(r["pct_positif"] - float(precedent[0]["pct_positif"]), 1),
        }
        if precedent
        else None
    )

    par_jour = {
        l["date_avis"].isoformat(): l["nb"]
        for l in entrepot.requete(
            cfg,
            f"SELECT date_avis, COUNT(*) AS nb FROM {cfg.table('avis_bruts')} "
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

    citations: dict[tuple[str, str], list[dict]] = {}
    for l in entrepot.requete(
        cfg,
        f"""
        SELECT t.theme, t.polarite, t.extrait
        FROM {cfg.table('avis_analyses')} a, UNNEST(a.themes) t
        WHERE a.etablissement_id = @etab AND a.version_prompt = @version
          AND a.date_avis BETWEEN @debut AND @fin AND t.extrait != ''
        QUALIFY ROW_NUMBER() OVER (PARTITION BY t.theme, t.polarite ORDER BY ABS(a.score) DESC) <= 2
        """,
        {"etab": etab, "version": r.get("version_prompt") or "v1", "debut": debut, "fin": fin},
    ):
        citations.setdefault((l["theme"], l["polarite"]), []).append({"extrait": l["extrait"]})

    for cle, polarite in (("top_negatifs", "negatif"), ("top_positifs", "positif")):
        themes = json.loads(r.get(cle) or "[]")
        for theme in themes:
            theme["libelle"] = taxonomie.libelle(theme["theme"])
            theme["exemples"] = citations.get((theme["theme"], polarite), [])
        r[cle] = themes
    return r


def liste_avis(cfg, etab: str, debut: date, fin: date, sentiment: str | None) -> list[dict]:
    filtre = "AND a.sentiment = @sentiment" if sentiment else ""
    parametres: dict[str, Any] = {"etab": etab, "debut": debut, "fin": fin}
    if sentiment:
        parametres["sentiment"] = sentiment
    lignes = entrepot.requete(
        cfg,
        f"""
        SELECT b.review_id, b.date_avis, b.note, b.texte, b.url_avis,
               a.sentiment, a.score, a.resume,
               ARRAY(SELECT t.theme FROM UNNEST(a.themes) t) AS themes
        FROM {cfg.table('avis_bruts')} b
        LEFT JOIN (
          SELECT * FROM {cfg.table('avis_analyses')}
          QUALIFY ROW_NUMBER() OVER (PARTITION BY review_id ORDER BY analyse_le DESC) = 1
        ) a USING (review_id)
        WHERE b.etablissement_id = @etab AND b.date_avis BETWEEN @debut AND @fin
          AND b.texte IS NOT NULL {filtre}
        ORDER BY b.date_avis DESC, b.publie_le DESC
        LIMIT 200
        """,
        parametres,
    )
    for ligne in lignes:
        ligne["themes"] = [taxonomie.libelle(t) for t in ligne["themes"] or []]
    return [serialisable(l) for l in lignes]


# --------------------------------------------------------------------------- #
# Application
# --------------------------------------------------------------------------- #


def creer_application():
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.staticfiles import StaticFiles

    cfg = configuration.charger()
    app = FastAPI(title="WatchMyBusiness", docs_url=None, redoc_url=None)

    @app.get("/api/etablissements")
    def route_etablissements():
        return {"etablissements": _memoriser("etab", lambda: etablissements(cfg))}

    @app.get("/api/rapports")
    def route_rapports(etablissement: str, limite: int = Query(12, ge=1, le=52)):
        return {
            "rapports": _memoriser(
                f"liste:{etablissement}:{limite}",
                lambda: liste_rapports(cfg, etablissement, limite),
            )
        }

    @app.get("/api/rapports/{semaine_id}")
    def route_rapport(semaine_id: str, etablissement: str):
        r = _memoriser(
            f"detail:{etablissement}:{semaine_id}",
            lambda: detail_rapport(cfg, etablissement, semaine_id),
        )
        if r is None:
            raise HTTPException(404, f"rapport {semaine_id} introuvable")
        return r

    @app.get("/api/avis")
    def route_avis(etablissement: str, debut: date, fin: date, sentiment: str | None = None):
        if sentiment and sentiment not in SENTIMENTS:
            raise HTTPException(400, f"sentiment inconnu : {sentiment}")
        if (fin - debut).days > 62:
            raise HTTPException(400, "période limitée à 62 jours")
        avis = _memoriser(
            f"avis:{etablissement}:{debut}:{fin}:{sentiment}",
            lambda: liste_avis(cfg, etablissement, debut, fin, sentiment),
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
