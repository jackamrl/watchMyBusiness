from datetime import UTC, datetime

from watchmybusiness import apify

MAINTENANT = datetime(2026, 10, 21, tzinfo=UTC)

ITEMS = [
    {
        "reviewId": "R1",
        "publishedAtDate": "2026-10-18T19:30:00.000Z",
        "stars": 2,
        "text": "  Une heure d'attente.  ",
        "originalLanguage": "fr",
        "reviewUrl": "https://maps/r1",
    },
    {"reviewId": "R2", "publishedAtDate": "2026-10-17T10:00:00Z", "stars": 5, "text": None},
    {"reviewId": "R1", "publishedAtDate": "2026-10-18T19:30:00Z", "stars": 3, "text": "doublon"},
    {"reviewId": "R3", "stars": 4, "text": "sans date"},
    "pas un dict",
]


def test_normaliser_dedoublonne_et_garde_les_notes_sans_texte():
    lignes = apify.normaliser(ITEMS, "as-du-fallafel", MAINTENANT)
    par_id = {l["review_id"]: l for l in lignes}
    assert set(par_id) == {"R1", "R2"}
    assert par_id["R2"]["texte"] is None
    assert par_id["R2"]["note"] == 5


def test_normaliser_conserve_le_dernier_doublon_et_nettoie_le_texte():
    r1 = {l["review_id"]: l for l in apify.normaliser(ITEMS, "x", MAINTENANT)}["R1"]
    assert r1["texte"] == "doublon"
    assert r1["date_avis"] == "2026-10-18"
    assert r1["etablissement_id"] == "x"
    assert isinstance(r1["brut"], dict)


def test_url_valide_exige_l_identifiant_de_lieu():
    assert apify.url_valide(
        "https://www.google.com/maps/place/X/@48.8,2.3,17z/data=!4m6!3m5!1s0x47e66e025d19942f:0x710304a633dfc4c2"
    )
    assert not apify.url_valide("https://www.google.com/maps/place/X/@48.857427,2.359094,17z")
    assert not apify.url_valide("https://maps.app.goo.gl/L6LjfQaNsmNRxmJc9")
