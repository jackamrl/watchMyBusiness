from datetime import date

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from watchmybusiness import web  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "projet-test")
    web._cache.clear()
    return TestClient(web.creer_application())


def test_page_servie(client):
    reponse = client.get("/")
    assert reponse.status_code == 200
    assert "WatchMyBusiness" in reponse.text


def test_sentiment_inconnu_refuse(client):
    reponse = client.get(
        "/api/avis",
        params={
            "etablissement": "x",
            "debut": "2026-10-12",
            "fin": "2026-10-18",
            "sentiment": "POSITIVE",
        },
    )
    assert reponse.status_code == 400


def test_periode_trop_longue_refusee(client):
    reponse = client.get(
        "/api/avis", params={"etablissement": "x", "debut": "2026-01-01", "fin": "2026-10-18"}
    )
    assert reponse.status_code == 400


def test_avis_mis_en_cache(client, monkeypatch):
    appels = []

    def faux(cfg, etab, debut, fin, sentiment):
        appels.append((etab, debut, fin, sentiment))
        return [{"review_id": "r1"}]

    monkeypatch.setattr(web, "liste_avis", faux)
    params = {"etablissement": "x", "debut": "2026-10-12", "fin": "2026-10-18"}
    assert client.get("/api/avis", params=params).json() == {"nb": 1, "avis": [{"review_id": "r1"}]}
    client.get("/api/avis", params=params)
    assert appels == [("x", date(2026, 10, 12), date(2026, 10, 18), None)]


def test_rapport_absent_404(client, monkeypatch):
    monkeypatch.setattr(web, "detail_rapport", lambda cfg, etab, semaine: None)
    assert client.get("/api/rapports/2026-W01", params={"etablissement": "x"}).status_code == 404
