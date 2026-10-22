"""Client Apify minimal (bibliothèque standard) et normalisation des avis."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

API = "https://api.apify.com/v2"
ACTEUR = "compass~google-maps-reviews-scraper"

_CLES_TEXTE = ("text", "reviewText", "textTranslated")
_CLES_DATE = ("publishedAtDate", "publishedAt", "reviewDate")


class ErreurApify(RuntimeError):
    pass


def _appel(url: str, jeton: str, methode: str = "GET", corps: dict | None = None) -> Any:
    donnees = json.dumps(corps).encode("utf-8") if corps is not None else None
    requete = urllib.request.Request(
        url,
        data=donnees,
        method=methode,
        headers={
            "Authorization": f"Bearer {jeton}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=60) as reponse:
            brut = reponse.read().decode("utf-8")
    except urllib.error.HTTPError as erreur:
        detail = erreur.read().decode("utf-8", errors="replace")[:300]
        raise ErreurApify(f"HTTP {erreur.code} sur {url} : {detail}") from erreur
    return json.loads(brut) if brut else {}


def collecter(
    jeton: str, url_lieu: str, max_avis: int, langue: str = "fr", delai_max_s: int = 900
) -> tuple[str, list[dict]]:
    """Lance l'acteur, attend la fin du run, renvoie (run_id, items du dataset)."""
    lancement = _appel(
        f"{API}/acts/{ACTEUR}/runs",
        jeton,
        "POST",
        {
            "startUrls": [{"url": url_lieu}],
            "maxReviews": max_avis,
            "reviewsSort": "newest",
            "language": langue,
            "personalData": False,
        },
    )["data"]
    run_id = lancement["id"]
    fin = time.monotonic() + delai_max_s
    statut = lancement["status"]
    while statut in {"READY", "RUNNING"}:
        if time.monotonic() > fin:
            raise ErreurApify(f"run {run_id} toujours en cours après {delai_max_s} s")
        time.sleep(5)
        statut = _appel(f"{API}/actor-runs/{run_id}", jeton)["data"]["status"]
    if statut != "SUCCEEDED":
        raise ErreurApify(f"run {run_id} terminé en {statut}")
    items = _appel(f"{API}/actor-runs/{run_id}/dataset/items?clean=true&format=json", jeton)
    if not items:
        raise ErreurApify(
            f"run {run_id} sans avis : URL de lieu non reconnue ? "
            f"Journal : {API}/actor-runs/{run_id}/log"
        )
    return run_id, items


def _date(valeur: Any) -> datetime | None:
    if not valeur:
        return None
    chaine = str(valeur).strip()
    try:
        return datetime.fromisoformat(chaine.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        correspondance = re.match(r"\d{4}-\d{2}-\d{2}", chaine)
        if correspondance:
            return datetime.fromisoformat(correspondance.group(0)).replace(tzinfo=UTC)
    return None


def _premier(item: dict, cles: Iterable[str]) -> Any:
    for cle in cles:
        valeur = item.get(cle)
        if valeur not in (None, ""):
            return valeur
    return None


def identifiant(item: dict) -> str:
    brut = item.get("reviewId") or item.get("reviewUrl")
    if not brut:
        brut = json.dumps(
            [item.get("reviewerId"), item.get("publishedAtDate"), item.get("text")],
            default=str,
        )
    return str(brut) if item.get("reviewId") else hashlib.sha1(brut.encode()).hexdigest()


def normaliser(items: Iterable[dict], etablissement_id: str, collecte_le: datetime) -> list[dict]:
    """Une ligne `avis_bruts` par avis daté. Les avis sans texte sont gardés :
    la note seule compte dans les KPI, seule l'analyse Gemini les ignore."""
    lignes: dict[str, dict] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        publie = _date(_premier(item, _CLES_DATE))
        if publie is None:
            continue
        texte = _premier(item, _CLES_TEXTE)
        review_id = identifiant(item)
        lignes[review_id] = {
            "review_id": review_id,
            "etablissement_id": etablissement_id,
            "date_avis": publie.date().isoformat(),
            "publie_le": publie.isoformat(),
            "note": int(item["stars"]) if item.get("stars") is not None else None,
            "texte": str(texte).strip() if texte else None,
            "langue": item.get("originalLanguage") or item.get("language"),
            "url_avis": item.get("reviewUrl"),
            "reponse_proprietaire": item.get("responseFromOwnerText"),
            "brut": json.loads(json.dumps(item, default=str)),
            "collecte_le": collecte_le.isoformat(),
        }
    return list(lignes.values())


def url_valide(url: str) -> bool:
    """L'acteur exige l'identifiant de lieu (`!1s0x…:0x…`) dans l'URL."""
    return bool(re.search(r"!1s0x[0-9a-f]+:0x[0-9a-f]+", urllib.parse.unquote(url)))
