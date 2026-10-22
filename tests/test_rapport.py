import json
from datetime import date

from watchmybusiness import courriel, rapport


def test_semaine_ecoulee_va_du_lundi_au_dimanche_precedents():
    # Mercredi 21 octobre 2026 -> semaine du 12 au 18.
    assert rapport.semaine_ecoulee(date(2026, 10, 21)) == (date(2026, 10, 12), date(2026, 10, 18))
    # Lancé le lundi 19 : même semaine.
    assert rapport.semaine_ecoulee(date(2026, 10, 19)) == (date(2026, 10, 12), date(2026, 10, 18))
    # Lancé le dimanche 18 : la semaine en cours n'est pas finie -> semaine du 5 au 11.
    assert rapport.semaine_ecoulee(date(2026, 10, 18)) == (date(2026, 10, 5), date(2026, 10, 11))


def test_semaine_id_iso():
    assert rapport.semaine_id(date(2026, 10, 12)) == "2026-W42"
    assert rapport.semaine_id(date(2026, 12, 28)) == "2026-W53"


def test_tendance():
    assert rapport.tendance(60, 20) == "positive"
    assert rapport.tendance(20, 60) == "negative"
    assert rapport.tendance(40, 30) == "mitigee"


def test_classement_par_polarite_avec_parts():
    themes = [
        {"theme": "attente", "polarite": "negatif", "occurrences": 3, "libelle": "Attente"},
        {"theme": "hygiene", "polarite": "negatif", "occurrences": 1, "libelle": "Hygiène"},
        {"theme": "qualite_cuisine", "polarite": "positif", "occurrences": 9, "libelle": "Cuisine"},
    ]
    negatifs = rapport.classement(themes, "negatif")
    assert [t["theme"] for t in negatifs] == ["attente", "hygiene"]
    assert negatifs[0]["part"] == 75.0


def test_comparaison_calcule_ecarts_et_evolution_des_themes(monkeypatch):
    kpi = {
        0: {
            "nb_avis": 28,
            "note_moyenne": 3.64,
            "pct_positif": 56.2,
            "pct_negatif": 31.2,
            "pct_mixte": 12.5,
            "nb_analyses": 16,
        },
        1: {
            "nb_avis": 16,
            "note_moyenne": 4.06,
            "pct_positif": 46.2,
            "pct_negatif": 23.1,
            "pct_mixte": 23.1,
            "nb_analyses": 13,
        },
    }
    themes = {
        0: [{"theme": "service_accueil", "polarite": "negatif", "occurrences": 5}],
        1: [
            {"theme": "service_accueil", "polarite": "negatif", "occurrences": 2},
            {"theme": "prix", "polarite": "negatif", "occurrences": 4},
        ],
    }
    donnees = rapport.Donnees(None, "x", date(2026, 10, 12), date(2026, 10, 18))
    monkeypatch.setattr(donnees, "kpi", lambda decalage=0: kpi[decalage])
    monkeypatch.setattr(donnees, "themes", lambda decalage=0: themes[decalage])

    resultat = donnees.comparaison()
    assert resultat["precedente_disponible"] is True
    assert resultat["ecarts"]["nb_avis"] == 12
    assert resultat["ecarts"]["note_moyenne"] == -0.42
    evolution = {e["theme"]: (e["semaine"], e["precedente"]) for e in resultat["evolution_themes"]}
    assert evolution == {"service_accueil": (5, 2), "prix": (0, 4)}


def test_courriel_contient_kpi_synthese_et_themes():
    message = courriel.construire(
        {"nom": "L'As du Fallafel", "email_manager": "g@x.fr"},
        {
            "semaine_id": "2026-W42",
            "tendance": "positive",
            "nb_avis": 12,
            "note_moyenne": 4.1,
            "pct_positif": 66.7,
            "pct_negatif": 16.7,
            "periode_debut": "2026-10-12",
            "periode_fin": "2026-10-18",
            "synthese": "## En bref\nBonne semaine, **attente** à surveiller.\n- Un serveur",
            "top_negatifs": json.dumps([{"libelle": "Attente", "occurrences": 2}]),
        },
    )
    assert "2026-W42" in message["Subject"]
    corps_html = message.get_body(("html",)).get_content()
    assert "<b>attente</b>" in corps_html
    assert "<li>Un serveur</li>" in corps_html
    assert "Attente" in corps_html
