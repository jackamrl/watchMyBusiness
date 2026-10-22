from datetime import UTC, datetime

import pytest

from watchmybusiness import collecte, depot_brut
from watchmybusiness.config import Config

CONFIG = Config(
    projet="p",
    region="europe-west1",
    dataset="wmb",
    bucket_brut="p-avis-brut",
    modele_gemini="m",
    region_gemini="europe-west3",
    secret_apify="apify-token",
    secret_smtp="s",
    smtp_hote="",
    smtp_port=587,
    smtp_utilisateur="",
    email_expediteur="",
    fuseau="Europe/Paris",
)

ETAB = {
    "etablissement_id": "as-du-fallafel",
    "nom": "L'As du Fallafel",
    "url_maps": "https://www.google.com/maps/place/X/data=!4m6!3m5!1s0x47e66e025d19942f:0x710304a633dfc4c2",
    "max_avis": 10,
    "langue": "fr",
}
ITEMS = [{"reviewId": "R1", "publishedAtDate": "2026-10-20T10:00:00Z", "stars": 5, "text": "Top"}]


@pytest.fixture
def journal_appels(monkeypatch):
    appels = []
    monkeypatch.setattr(collecte.entrepot, "requete", lambda *a, **k: [ETAB])
    monkeypatch.setattr(collecte.secrets, "lire", lambda *a, **k: "jeton")
    monkeypatch.setattr(collecte.apify, "collecter", lambda *a, **k: ("RUN42", ITEMS))
    monkeypatch.setattr(
        collecte.depot_brut,
        "deposer",
        lambda cfg, etab, quand, run, items: appels.append(("depot", run, len(items))) or "gs://x",
    )
    monkeypatch.setattr(
        collecte.entrepot,
        "fusionner",
        lambda cfg, table, lignes, cles: appels.append(("merge", table, len(lignes)))
        or len(lignes),
    )
    return appels


def test_le_brut_est_depose_avant_le_merge(journal_appels):
    collecte.executer(CONFIG)
    assert journal_appels == [("depot", "RUN42", 1), ("merge", "avis_bruts", 1)]


def test_un_echec_bigquery_laisse_le_depot_brut_intact(journal_appels, monkeypatch):
    def merge_en_panne(*a, **k):
        raise RuntimeError("quota BigQuery")

    monkeypatch.setattr(collecte.entrepot, "fusionner", merge_en_panne)
    with pytest.raises(RuntimeError):
        collecte.executer(CONFIG)
    assert journal_appels == [("depot", "RUN42", 1)]


def test_rejouer_recharge_depuis_le_depot_sans_apify(monkeypatch):
    monkeypatch.setattr(
        collecte.depot_brut, "lister", lambda cfg, p: ["as-du-fallafel/2026-10-22/run-RUN42.json"]
    )
    monkeypatch.setattr(
        collecte.depot_brut,
        "lire",
        lambda cfg, nom: (
            ITEMS,
            {"etablissement_id": "as-du-fallafel", "collecte_le": "2026-10-22T04:00:00+00:00"},
        ),
    )
    monkeypatch.setattr(collecte.apify, "collecter", lambda *a, **k: pytest.fail("Apify appelé"))
    charges = []
    monkeypatch.setattr(
        collecte.entrepot,
        "fusionner",
        lambda cfg, table, lignes, cles: charges.extend(lignes) or len(lignes),
    )

    collecte.rejouer(CONFIG, "as-du-fallafel/")
    assert [l["review_id"] for l in charges] == ["R1"]
    assert charges[0]["collecte_le"] == "2026-10-22T04:00:00+00:00"


def test_chemin_du_depot_brut():
    quand = datetime(2026, 10, 22, 4, 0, tzinfo=UTC)
    assert (
        depot_brut.chemin("as-du-fallafel", quand, "RUN42")
        == "as-du-fallafel/2026-10-22/run-RUN42.json"
    )
