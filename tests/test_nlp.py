"""Tests du NLP maison : tokenizer, métriques, Bayes naïf, découpage, modèle,
entraînement de bout en bout (minuscule, sur CPU) et branchement dans le job d'analyse."""

import json
from datetime import date
from types import SimpleNamespace

import pytest
from nlp import bayes, donnees, metriques

from watchmybusiness import gemini
from watchmybusiness.nlp import etiquettes
from watchmybusiness.nlp.tokenizer import BOS, UNK, TokenizerBPE, normaliser

CORPUS = [
    "Le falafel est délicieux et pas cher.",
    "Une heure d'attente, le service était lent !",
    "Personnel souriant, falafel délicieux, je reviendrai.",
    "Trop cher pour ce que c'est, et la salle était sale.",
    "L'attente est longue mais le falafel vaut le coup.",
] * 4


# --------------------------------------------------------------------------- #
# Tokenizer BPE
# --------------------------------------------------------------------------- #
def test_bpe_decode_exactement_ce_qu_il_encode():
    tok = TokenizerBPE.entrainer(CORPUS, taille_vocab=120)
    for texte in CORPUS[:5]:
        assert tok.decoder(tok.encoder(texte)) == normaliser(texte)


def test_bpe_fusionne_les_mots_frequents_et_compresse():
    tok = TokenizerBPE.entrainer(CORPUS, taille_vocab=150)
    assert " falafel" in tok.vocab
    texte = CORPUS[0]
    assert len(tok.encoder(texte)) < len(texte) / 2


def test_bpe_caractere_inconnu_et_speciaux():
    tok = TokenizerBPE.entrainer(CORPUS, taille_vocab=80)
    ids = tok.encoder("€", bos=True)
    assert ids[0] == BOS and UNK in ids


def test_bpe_sauver_charger(tmp_path):
    tok = TokenizerBPE.entrainer(CORPUS, taille_vocab=120)
    tok.sauver(tmp_path / "t.json")
    recharge = TokenizerBPE.charger(tmp_path / "t.json")
    assert recharge.encoder(CORPUS[1]) == tok.encoder(CORPUS[1])


# --------------------------------------------------------------------------- #
# Étiquettes et métriques
# --------------------------------------------------------------------------- #
def test_etoiles_comme_etiquette_faible():
    assert etiquettes.depuis_etoiles(1) == "NEGATIF"
    assert etiquettes.depuis_etoiles(5) == "POSITIF"
    assert etiquettes.depuis_etoiles(3) is None


def test_encoder_une_etiquette_partielle():
    e = etiquettes.encoder({"sentiment": "MIXTE", "themes": {"attente": "negatif"}})
    assert e["sentiment"] == etiquettes.SENTIMENTS.index("MIXTE")
    assert e["humeur"] == etiquettes.IGNORER
    i = etiquettes.themes().index("attente")
    assert e["themes"][i] == etiquettes.POLARITES.index("negatif")
    assert e["themes"][0 if i else 1] == etiquettes.POLARITES.index("absent")


def test_kappa_de_cohen():
    assert metriques.kappa_cohen(list("oonn"), list("oonn")) == 1.0
    assert metriques.kappa_cohen(list("oonn"), list("onnn")) == pytest.approx(0.5)


def test_f1_macro_et_ensembles():
    vrais = ["POSITIF", "POSITIF", "NEGATIF", "NEGATIF"]
    assert metriques.f1_macro(vrais, vrais, etiquettes.SENTIMENTS) == 1.0
    assert metriques.f1_macro(vrais, ["POSITIF"] * 4, etiquettes.SENTIMENTS) == pytest.approx(
        (2 / 3 + 0) / 2)
    assert metriques.f1_ensembles([{("attente", "negatif")}], [{("attente", "negatif"),
                                                                ("prix", "positif")}]) \
        == pytest.approx(2 / 3)


def test_bayes_naif_apprend_un_cas_separable():
    textes = ["délicieux génial super"] * 5 + ["horrible sale lent"] * 5
    labels = ["POSITIF"] * 5 + ["NEGATIF"] * 5
    modele = bayes.BayesNaif().entrainer(textes, labels)
    assert modele.predire(["vraiment génial", "très sale"]) == ["POSITIF", "NEGATIF"]


# --------------------------------------------------------------------------- #
# Données
# --------------------------------------------------------------------------- #
def _avis(n_etabs=4, par_etab=10):
    lignes = []
    for e in range(n_etabs):
        for k in range(par_etab):
            positif = k % 2 == 0
            lignes.append({
                "review_id": f"r{e}-{k}", "etablissement_id": f"resto-{e}",
                "metier": "restaurant", "note": 5 if positif else 1,
                "texte": CORPUS[0] if positif else CORPUS[3],
                "etiquette": {"sentiment": "POSITIF" if positif else "NEGATIF",
                              "humeur": "joie" if positif else "colere",
                              "themes": {"qualite_cuisine": "positif"} if positif
                              else {"prix": "negatif", "hygiene": "negatif"}},
            })
    return lignes


def test_decouper_par_restaurant_sans_fuite(tmp_path):
    donnees.ecrire_jsonl(tmp_path / "avis.jsonl", _avis(n_etabs=6))
    tailles = donnees.decouper(tmp_path / "avis.jsonl", tmp_path)
    assert sum(tailles.values()) == 60
    etabs = {nom: {l["etablissement_id"] for l in donnees.lire_jsonl(tmp_path / f"{nom}.jsonl")}
             for nom in ("train", "val", "test")}
    assert etabs["test"] and etabs["val"] and etabs["train"]
    assert not (etabs["test"] & etabs["train"]) and not (etabs["val"] & etabs["train"])


def test_annotation_kappa_et_import(tmp_path):
    donnees.ecrire_jsonl(tmp_path / "test.jsonl", _avis(n_etabs=1, par_etab=4))
    a, b = donnees.exporter_annotation(tmp_path / "test.jsonl", tmp_path, n=4)
    for chemin, sentiment in ((a, "POSITIF"), (b, "POSITIF")):
        lignes = chemin.read_text(encoding="utf-8-sig").splitlines()
        chemin.write_text("\n".join([lignes[0]] + [
            l.replace(";;", f";{sentiment};joie;", 1) for l in lignes[1:]]), encoding="utf-8-sig")
    k = donnees.kappa(a, b, tmp_path / "desaccords.csv")
    assert k["sentiment"] == 1.0
    assert donnees.importer_annotation(a, tmp_path / "test.jsonl", tmp_path / "or.jsonl") == 4


def test_gemini_peut_etiqueter_l_humeur():
    assert "humeur" in gemini.schema("restaurant", avec_humeur=True)["required"]
    assert "humeur" not in gemini.schema("restaurant")["properties"]
    assert "frustration" in gemini.consigne("restaurant", "X", avec_humeur=True)
    sortie = gemini.valider({"sentiment": "NEGATIF", "humeur": "colere"}, "restaurant")
    assert sortie["humeur"] == "colere"


# --------------------------------------------------------------------------- #
# Modèle et entraînement (PyTorch)
# --------------------------------------------------------------------------- #
torch = pytest.importorskip("torch")


def test_modele_formes_et_remplissage_sans_effet():
    from watchmybusiness.nlp.modele import ConfigModele, ModeleAvis

    m = ModeleAvis(ConfigModele.depuis_taille("XS", 100, contexte=16)).eval()
    ids = torch.randint(5, 100, (1, 6))
    masque = torch.ones(1, 6, dtype=torch.bool)
    s = m.classer(ids, masque)
    assert s["sentiment"].shape == (1, 4)
    assert s["themes"].shape == (1, 8, 4)
    assert m.langue(ids).shape == (1, 6, 100)
    # Ajouter du remplissage ne doit rien changer à la prédiction.
    ids_pad = torch.cat([ids, torch.zeros(1, 4, dtype=torch.long)], dim=1)
    masque_pad = torch.cat([masque, torch.zeros(1, 4, dtype=torch.bool)], dim=1)
    s_pad = m.classer(ids_pad, masque_pad)
    assert torch.allclose(s["sentiment"], s_pad["sentiment"], atol=1e-5)


def test_entrainement_complet_minuscule(tmp_path):
    from nlp import entrainement

    from watchmybusiness.nlp.service import ModeleMaison

    lignes = _avis(n_etabs=4, par_etab=10)
    donnees.ecrire_jsonl(tmp_path / "train.jsonl", lignes)
    donnees.ecrire_jsonl(tmp_path / "val.jsonl", lignes[:10])
    (tmp_path / "corpus.txt").write_text("\n".join(CORPUS * 5), encoding="utf-8")
    entrainement.appareil = lambda: "cpu"

    entrainement.entrainer_tokenizer(tmp_path / "corpus.txt", tmp_path / "tok.json", taille=150)
    r = entrainement.pretrain(tmp_path / "corpus.txt", tmp_path / "tok.json",
                              tmp_path / "pre.pt", taille="XS", contexte=32, pas=30, lot=8,
                              eval_tous=15)
    assert len(r["historique"]) == 2
    entrainement.finetune(tmp_path / "train.jsonl", tmp_path / "val.jsonl", tmp_path / "tok.json",
                          tmp_path / "paquet", init=tmp_path / "pre.pt", epoques=8, lot=8,
                          lr=3e-3, version="nlp-test")

    modele = ModeleMaison(tmp_path / "paquet")
    assert modele.version == "nlp-test"
    assert modele.tetes == {"sentiment", "humeur", "themes"}
    p = modele.predire(CORPUS[3])
    assert set(p) >= {"sentiment", "score", "confiance", "humeur", "themes", "actionnable"}
    assert p["sentiment"] in etiquettes.SENTIMENTS and 0 <= p["confiance"] <= 1
    # Le cas d'entraînement, trivialement séparable, doit être appris.
    assert modele.predire(CORPUS[0])["sentiment"] == "POSITIF"
    assert p["sentiment"] == "NEGATIF"

    # Paquet combiné : un spécialiste des thèmes s'ajoute sans changer le reste.
    from nlp.__main__ import combiner

    combiner(tmp_path / "paquet", tmp_path / "paquet", tmp_path / "combine")
    duo = ModeleMaison(tmp_path / "combine")
    assert duo.modele_themes is not None and duo.version == "nlp-test+nlp-test"
    assert duo.predire(CORPUS[3])["sentiment"] == p["sentiment"]


def test_job_analyse_maison_relaie_les_avis_incertains(monkeypatch):
    from watchmybusiness import analyse, config

    cfg = config.Config(projet="p", region="r", dataset="d", bucket_brut="b",
                        modele_gemini="gemini-x", region_gemini="g", secret_apify="",
                        secret_smtp="", smtp_hote="", smtp_port=587, smtp_utilisateur="",
                        email_expediteur="", fuseau="Europe/Paris", moteur_analyse="maison",
                        modele_maison="/tmp/paquet", version_modele="nlp-v1",
                        relais_gemini=True)
    avis = [{"review_id": f"r{i}", "etablissement_id": "e", "date_avis": date(2026, 11, 2),
             "note": 4, "texte": f"avis {i}", "nom": "X", "metier": "restaurant"}
            for i in range(3)]
    faux_modele = SimpleNamespace(
        version="nlp-v1", seuil=0.7,
        predire_lot=lambda textes: [
            {"sentiment": "POSITIF", "score": 0.9, "confiance": c, "humeur": "joie",
             "themes": [], "theme_emergent": None, "actionnable": False, "resume": ""}
            for c in (0.95, 0.4, 0.8)][: len(textes)])
    from watchmybusiness.nlp import service

    monkeypatch.setattr(service.ModeleMaison, "depuis_uri", classmethod(lambda cls, u: faux_modele))
    versions = []
    monkeypatch.setattr(analyse, "a_analyser",
                        lambda c, limite=500, version=None: versions.append(version) or avis)
    monkeypatch.setattr(analyse, "client_gemini", lambda c: object())
    monkeypatch.setattr(analyse, "_analyser_un", lambda cl, c, a, avec_humeur=False: {
        "review_id": a["review_id"], "sentiment": "MIXTE", "humeur": "deception",
        "modele": "gemini-x", "version_prompt": "v1"})
    ecrit = {}
    monkeypatch.setattr(analyse.entrepot, "fusionner",
                        lambda c, table, lignes, cles: ecrit.update(table=table, lignes=lignes))

    assert analyse.executer(cfg) == 0
    assert versions == ["nlp-v1"]
    lignes = {l["review_id"]: l for l in ecrit["lignes"]}
    assert lignes["r0"]["modele"] == "maison-nlp-v1" and lignes["r0"]["confiance"] == 0.95
    assert lignes["r1"]["modele"] == "gemini-x"  # sous le seuil → relais Gemini
    assert lignes["r1"]["version_prompt"] == "nlp-v1" and lignes["r1"]["confiance"] is None
    assert json.dumps(ecrit["lignes"], default=str)


def test_detection_du_francais_et_import_csv(tmp_path):
    assert donnees.est_francais("La chambre était très propre et le personnel est adorable")
    assert not donnees.est_francais("The room was very clean and the staff is great")
    assert donnees.langue("The room was very clean and the staff is great") == "en"
    assert donnees.langue("ok") is None
    (tmp_path / "avis.csv").write_text(
        "review,rating\n"
        '"La chambre était très propre et le personnel est adorable, nous reviendrons",5\n'
        '"The room was very clean and the staff was great, we will come back",5\n',
        encoding="utf-8")
    compte = donnees.construire_corpus(tmp_path / "c.txt", [], [],
                                       csvs=[f"{tmp_path / 'avis.csv'}:review"],
                                       francais_seulement=True)
    assert compte == {"avis.csv": 1}
    with pytest.raises(SystemExit):
        list(donnees.textes_csv(tmp_path / "avis.csv", "texte", False))


def test_les_emotions_publiques_correspondent_a_nos_humeurs():
    assert set(donnees.EMOTIONS_VERS_HUMEURS.values()) <= set(etiquettes.HUMEURS)
    assert set(donnees.SENTIMENTS_CLAPAI.values()) <= set(etiquettes.SENTIMENTS)


def test_finetune_lit_plusieurs_fichiers(tmp_path):
    from nlp import entrainement

    donnees.ecrire_jsonl(tmp_path / "a.jsonl", [{"review_id": "1"}])
    donnees.ecrire_jsonl(tmp_path / "b.jsonl", [{"review_id": "2"}, {"review_id": "3"}])
    assert len(entrainement._lire([tmp_path / "a.jsonl", tmp_path / "b.jsonl"])) == 3
    assert len(entrainement._lire(tmp_path / "a.jsonl")) == 1


def test_import_apify_et_decoupage_par_date(tmp_path):
    items = [{"reviewId": f"R{i}", "publishedAtDate": f"2026-0{1 + i % 9}-1{i % 10}T10:00:00Z",
              "stars": 1 + i % 5, "text": f"Avis numéro {i}, le falafel est bon",
              "originalLanguage": "fr"} for i in range(20)]
    items.append({"reviewId": "SANS", "publishedAtDate": "2026-01-01", "stars": 5, "text": None})
    (tmp_path / "run.json").write_text(json.dumps(items), encoding="utf-8")
    compte = donnees.importer_apify([tmp_path / "run.json"], "as-du-fallafel",
                                    tmp_path / "avis.jsonl")
    assert compte["gardes"] == 20 and compte["sans_texte"] == 1
    tailles = donnees.decouper_par_date(tmp_path / "avis.jsonl", tmp_path)
    assert tailles == {"train": 16, "val": 2, "test": 2}
    dates = {n: [l["date_avis"] for l in donnees.lire_jsonl(tmp_path / f"{n}.jsonl")]
             for n in ("train", "test")}
    assert max(dates["train"]) <= min(dates["test"])


def test_une_tete_jamais_entrainee_n_est_pas_affichee(tmp_path):
    from nlp import entrainement

    from watchmybusiness.nlp.modele import ConfigModele, ModeleAvis
    from watchmybusiness.nlp.service import ModeleMaison

    ign = etiquettes.IGNORER
    ex = [{"ids": [1], "sentiment": 0, "humeur": ign, "themes": [ign] * 8}]
    assert entrainement.tetes_entrainees(ex, {}) == ["sentiment"]
    assert entrainement.tetes_entrainees(ex, {"tetes_entrainees": ["humeur"]}) == [
        "humeur", "sentiment"]

    tok = TokenizerBPE.entrainer(CORPUS, taille_vocab=120)
    tok.sauver(tmp_path / "tokenizer.json")
    ModeleAvis(ConfigModele.depuis_taille("XS", len(tok), contexte=32)).sauver(
        tmp_path / "modele.pt", {"version": "v", "tetes_entrainees": ["sentiment"]})
    p = ModeleMaison(tmp_path).predire(CORPUS[0])
    assert p["themes"] == [] and p["humeur"] is None and p["actionnable"] is False


def test_import_google_maps_scraper_avec_notes_detaillees(tmp_path):
    fiche = [{"title": "L'As du Fallafel", "reviews": [
        {"reviewId": "A", "publishedAtDate": "2026-11-01T10:00:00Z", "stars": 2,
         "text": "Un peu déçu...<br>Plus de merguez", "originalLanguage": "fr",
         "reviewDetailedRating": {"Cuisine": 2, "Service": 3, "Ambiance": 5},
         "reviewContext": {"Type de commande": "Repas sur place"}},
        {"reviewId": "B", "publishedAtDate": "2026-11-02T10:00:00Z", "stars": 5, "text": ""},
    ]}]
    (tmp_path / "fiche.json").write_text(json.dumps(fiche), encoding="utf-8")
    compte = donnees.importer_apify([tmp_path / "fiche.json"], "as-du-fallafel",
                                    tmp_path / "avis.jsonl")
    assert compte["gardes"] == 1 and compte["avec_notes_detaillees"] == 1
    ligne = donnees.lire_jsonl(tmp_path / "avis.jsonl")[0]
    assert ligne["texte"] == "Un peu déçu... Plus de merguez"
    assert etiquettes.themes_depuis_notes(ligne["notes_detaillees"]) == {
        "qualite_cuisine": "negatif", "service_accueil": "neutre", "cadre_ambiance": "positif"}


def test_les_langues_hors_modele_passent_par_la_traduction(tmp_path):
    items = [
        {"reviewId": "ES", "publishedAtDate": "2026-11-01", "stars": 5, "originalLanguage": "es",
         "text": "Increibles emparedados!", "textTranslated": "Des sandwichs exceptionnels !"},
        {"reviewId": "EN", "publishedAtDate": "2026-11-01", "stars": 5, "originalLanguage": "en",
         "text": "Amazing falafel", "textTranslated": "Falafel incroyable"},
    ]
    (tmp_path / "run.json").write_text(json.dumps(items), encoding="utf-8")
    compte = donnees.importer_apify([tmp_path / "run.json"], "x", tmp_path / "avis.jsonl")
    par_id = {l["review_id"]: l for l in donnees.lire_jsonl(tmp_path / "avis.jsonl")}
    assert compte["traduits"] == 1
    assert par_id["ES"]["texte"] == "Des sandwichs exceptionnels !"
    assert par_id["EN"]["texte"] == "Amazing falafel"
    assert par_id["EN"]["texte_traduit"] == "Falafel incroyable"


def test_seuls_les_themes_appris_sont_retenus():
    from nlp import entrainement

    ign = etiquettes.IGNORER
    themes = [ign] * 8
    themes[etiquettes.themes().index("service_accueil")] = 1
    ex = [{"ids": [1], "sentiment": 0, "humeur": ign, "themes": themes}]
    assert entrainement.themes_entraines(ex, {}, "restaurant") == ["service_accueil"]
    assert entrainement.themes_entraines(ex, {"themes_entraines": ["prix"]}, "restaurant") == [
        "service_accueil", "prix"]


def test_poids_themes_favorise_les_themes_presents():
    from nlp.entrainement import IGN, poids_themes

    lignes = [[0, 0]] * 9 + [[1, IGN]]
    w = poids_themes(lignes, nb_themes=2)
    assert w[0, 1] > w[0, 0]  # « positif » rare pèse plus que « absent »
    assert w[0, 2] == 0  # polarité jamais vue : poids nul
    assert w[1, 0] > 0 and w[1, 1] == 0


def test_polarite_theme_avec_et_sans_seuil():
    from watchmybusiness.nlp.service import polarite_theme

    probas = [0.6, 0.1, 0.25, 0.05]
    assert polarite_theme(probas) == "absent"
    assert polarite_theme(probas, seuil=0.7) == "negatif"
    assert polarite_theme(probas, seuil=0.5) == "absent"
