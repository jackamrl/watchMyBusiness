from watchmybusiness import gemini, taxonomie


def test_le_schema_restreint_les_themes_a_la_taxonomie_du_metier():
    enum = gemini.schema("restaurant")["properties"]["themes"]["items"]["properties"]["theme"][
        "enum"
    ]
    assert set(enum) == set(taxonomie.themes("restaurant"))
    assert "retard_livraison" not in enum


def test_valider_filtre_les_themes_inconnus_et_les_doublons():
    sortie = gemini.valider(
        {
            "sentiment": "mixte",
            "score": 3,
            "themes": [
                {"theme": "attente", "polarite": "negatif", "extrait": "1h de queue"},
                {"theme": "attente", "polarite": "negatif", "extrait": "doublon"},
                {"theme": "parking", "polarite": "negatif", "extrait": "inventé"},
                {"theme": "qualite_cuisine", "polarite": "bizarre", "extrait": "bon"},
            ],
            "theme_emergent": "",
            "actionnable": 1,
            "resume": "Attente longue mais bon falafel.",
        },
        "restaurant",
    )
    assert sortie["sentiment"] == "MIXTE"
    assert sortie["score"] == 1.0
    assert [t["theme"] for t in sortie["themes"]] == ["attente", "qualite_cuisine"]
    assert sortie["themes"][1]["polarite"] == "neutre"
    assert sortie["theme_emergent"] is None
    assert sortie["actionnable"] is True


def test_valider_remplace_un_sentiment_inconnu_par_neutre():
    assert (
        gemini.valider({"sentiment": "JOYEUX", "themes": []}, "restaurant")["sentiment"] == "NEUTRE"
    )


class _FauxClient:
    """Imite google.genai.Client.models.generate_content."""

    def __init__(self, texte):
        self.models = self
        self.appel = None
        self._texte = texte

    def generate_content(self, model, contents, config):
        self.appel = {"model": model, "contents": contents, "config": config}
        return type("R", (), {"text": self._texte})()


def test_analyser_transmet_la_note_et_impose_le_json():
    faux = _FauxClient(
        '{"sentiment":"POSITIF","score":0.9,"themes":[],"actionnable":false,"resume":"ok"}'
    )
    sortie = gemini.analyser(faux, "gemini-x", "restaurant", "L'As du Fallafel", "Top !", 5)
    assert sortie["sentiment"] == "POSITIF"
    assert "5/5" in faux.appel["contents"]
    assert faux.appel["config"].response_mime_type == "application/json"
    assert faux.appel["config"].temperature == 0
