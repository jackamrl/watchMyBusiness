"""Préparation des données : export BigQuery, découpage par restaurant, corpus de
pré-entraînement, annotation humaine du jeu de test (CSV) et kappa de Cohen.

Format commun (JSON Lines, une ligne par avis) :
    {"review_id", "etablissement_id", "metier", "texte", "note", "langue",
     "reponse_proprietaire", "date_avis",
     "etiquette": {"sentiment", "humeur", "themes": {theme: polarite}} | null,
     "source_etiquette": "gemini" | "humain" | null}
"""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import logging
import random
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from pathlib import Path

from watchmybusiness import taxonomie
from watchmybusiness.nlp import etiquettes

from . import metriques

journal = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# JSON Lines
# --------------------------------------------------------------------------- #
def lire_jsonl(chemin: str | Path) -> list[dict]:
    with open(chemin, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def ecrire_jsonl(chemin: str | Path, lignes: Iterable[dict]) -> int:
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(chemin, "w", encoding="utf-8") as f:
        for ligne in lignes:
            f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n


# --------------------------------------------------------------------------- #
# Export depuis BigQuery (avis bruts + dernière analyse Gemini comme étiquette)
# --------------------------------------------------------------------------- #
def exporter_bigquery(projet: str, dataset: str, sortie: str | Path) -> int:
    from google.cloud import bigquery

    sql = f"""
    WITH derniere AS (
      SELECT * EXCEPT(rang) FROM (
        SELECT a.*, ROW_NUMBER() OVER (PARTITION BY review_id ORDER BY analyse_le DESC) rang
        FROM `{projet}.{dataset}.avis_analyses` a
        WHERE NOT STARTS_WITH(modele, 'maison')
      ) WHERE rang = 1
    )
    SELECT b.review_id, b.etablissement_id, e.metier, b.texte, b.note, b.langue,
           b.reponse_proprietaire, CAST(b.date_avis AS STRING) AS date_avis,
           d.sentiment, d.themes, d.modele
    FROM `{projet}.{dataset}.avis_bruts` b
    JOIN `{projet}.{dataset}.etablissements` e USING (etablissement_id)
    LEFT JOIN derniere d USING (review_id)
    WHERE b.texte IS NOT NULL
    """
    lignes = []
    for r in bigquery.Client(project=projet).query(sql).result():
        r = dict(r)
        etiquette = None
        if r.get("sentiment"):
            etiquette = etiquettes.depuis_analyse(
                {"sentiment": r["sentiment"], "themes": r.get("themes") or []})
        lignes.append({
            "review_id": r["review_id"], "etablissement_id": r["etablissement_id"],
            "metier": r["metier"], "texte": r["texte"], "note": r["note"],
            "langue": r["langue"], "reponse_proprietaire": r["reponse_proprietaire"],
            "date_avis": r["date_avis"], "etiquette": etiquette,
            "source_etiquette": "gemini" if etiquette else None,
        })
    return ecrire_jsonl(sortie, lignes)


# --------------------------------------------------------------------------- #
# Découpage train / val / test PAR RESTAURANT
# --------------------------------------------------------------------------- #
def _hash(texte: str) -> int:
    return int(hashlib.sha1(texte.encode()).hexdigest(), 16)


def decouper_par_date(entree: str | Path, dossier: str | Path,
                      part: float = 0.1) -> dict[str, int]:
    """Un seul établissement (L'As du Fallafel) : découpage DANS LE TEMPS. Les avis
    les plus récents forment le test, les suivants la validation, les plus anciens
    l'entraînement. C'est l'usage réel : prédire les avis à venir."""
    lignes = sorted(lire_jsonl(entree), key=lambda l: l.get("date_avis") or "")
    n = max(1, int(len(lignes) * part))
    jeux = {"train": lignes[:-2 * n], "val": lignes[-2 * n:-n], "test": lignes[-n:]}
    for nom, jeu in jeux.items():
        if jeu:
            journal.info("%s : %d avis, du %s au %s", nom, len(jeu),
                         jeu[0].get("date_avis"), jeu[-1].get("date_avis"))
    return {nom: ecrire_jsonl(Path(dossier) / f"{nom}.jsonl", jeu) for nom, jeu in jeux.items()}


def decouper(entree: str | Path, dossier: str | Path, test: list[str] | None = None,
             val: list[str] | None = None, part: float = 0.1) -> dict[str, int]:
    """Les restaurants du test (et de la validation) ne sont JAMAIS vus à
    l'entraînement : on mesure la capacité à généraliser à un nouvel établissement.

    Sans liste explicite, environ `part` des avis vont au test et autant à la
    validation, en prenant des restaurants entiers (choix déterministe)."""
    lignes = lire_jsonl(entree)
    par_etab = defaultdict(list)
    for l in lignes:
        par_etab[l["etablissement_id"]].append(l)
    etabs = sorted(par_etab, key=_hash)

    if len(etabs) < 3:
        journal.warning(
            "Seulement %d établissement(s) : découpage par avis (ESSAI UNIQUEMENT, "
            "le test n'est pas indépendant des restaurants d'entraînement).", len(etabs))
        random.Random(0).shuffle(lignes)
        n = max(1, int(len(lignes) * part))
        jeux = {"test": lignes[:n], "val": lignes[n:2 * n], "train": lignes[2 * n:]}
    else:
        total = len(lignes)
        test = test or []
        val = val or []
        restants = [e for e in etabs if e not in test and e not in val]
        for cible, liste in (("test", test), ("val", val)):
            if liste:
                continue
            while restants and (not liste or
                                sum(len(par_etab[e]) for e in liste) < part * total):
                liste.append(restants.pop(0))
            journal.info("%s : %d établissement(s)", cible, len(liste))
        jeux = {
            "test": [l for e in test for l in par_etab[e]],
            "val": [l for e in val for l in par_etab[e]],
            "train": [l for e in restants for l in par_etab[e]],
        }
    dossier = Path(dossier)
    return {nom: ecrire_jsonl(dossier / f"{nom}.jsonl", jeu) for nom, jeu in jeux.items()}


# --------------------------------------------------------------------------- #
# Corpus de pré-entraînement (texte brut, un document par ligne)
# --------------------------------------------------------------------------- #
def _allocine(max_docs: int) -> Iterator[str]:
    from datasets import load_dataset  # pip install datasets

    for i, ex in enumerate(load_dataset("tblard/allocine", split="train", streaming=True)):
        if i >= max_docs:
            break
        yield ex["review"]


def _wikipedia(max_mo: int) -> Iterator[str]:
    from datasets import load_dataset  # pip install datasets

    budget = max_mo * 1_000_000
    flux = load_dataset("wikimedia/wikipedia", "20231101.fr", split="train", streaming=True)
    for ex in flux:
        for paragraphe in ex["text"].split("\n"):
            if len(paragraphe) > 200:
                budget -= len(paragraphe.encode())
                yield paragraphe
        if budget <= 0:
            break


def importer_allocine(dossier: str | Path, max_train: int | None = None) -> dict[str, int]:
    """Critiques de films Allociné (positif / négatif), déjà découpées par leurs auteurs :
    jeu d'essai étiqueté gratuit pour valider la chaîne complète, et données de
    transfert pour le sentiment. Pas d'humeur ni de thèmes."""
    from datasets import load_dataset  # pip install datasets

    tailles = {}
    for split, nom in (("train", "train"), ("validation", "val"), ("test", "test")):
        def lignes(split=split, nom=nom):
            for i, ex in enumerate(load_dataset("tblard/allocine", split=split, streaming=True)):
                if nom == "train" and max_train and i >= max_train:
                    break
                yield {"review_id": f"allocine-{nom}-{i}", "etablissement_id": "allocine",
                       "metier": "restaurant", "texte": ex["review"], "note": None,
                       "etiquette": {"sentiment": "POSITIF" if ex["label"] == 1 else "NEGATIF",
                                     "humeur": None, "themes": None},
                       "source_etiquette": "humain"}
        tailles[nom] = ecrire_jsonl(Path(dossier) / f"{nom}.jsonl", lignes())
    return tailles


# Émotions de JusteLeo/French-emotion → humeurs du modèle. peur, surprise et dégoût
# n'ont pas d'équivalent dans nos humeurs : ces exemples sont ignorés.
EMOTIONS_VERS_HUMEURS = {"joie": "joie", "colere": "colere", "neutre": "neutre",
                         "tristesse": "deception"}
SENTIMENTS_CLAPAI = {"positive": "POSITIF", "negative": "NEGATIF", "neutral": "NEUTRE"}


def importer_french_emotion(dossier: str | Path) -> dict[str, int]:
    """Phrases françaises synthétiques étiquetées par émotion (licence MIT) : amorce de
    la tête « humeur ». Seule l'humeur est renseignée."""
    from datasets import load_dataset

    tailles = {}
    for split, nom in (("train", "train"), ("validation", "val"), ("test", "test")):
        lignes = (
            {"review_id": f"emotion-{nom}-{i}", "etablissement_id": "french-emotion",
             "metier": "restaurant", "texte": ex["text"], "note": None,
             "etiquette": {"sentiment": None, "themes": None,
                           "humeur": EMOTIONS_VERS_HUMEURS[ex["label"]]},
             "source_etiquette": "jeu-public"}
            for i, ex in enumerate(load_dataset("JusteLeo/French-emotion", split=split))
            if ex["label"] in EMOTIONS_VERS_HUMEURS
        )
        tailles[nom] = ecrire_jsonl(Path(dossier) / f"{nom}.jsonl", lignes)
    return tailles


def importer_clapai(dossier: str | Path) -> dict[str, int]:
    """Partie française de clapAI/MultiLingualSentiment (positif / neutre / négatif).
    La source Allociné est écartée : déjà importée séparément, et la garder risquerait
    de mettre des critiques du test Allociné dans l'entraînement."""
    from datasets import load_dataset

    tailles = {}
    for split, nom in (("train", "train"), ("validation", "val"), ("test", "test")):
        domaines = Counter()

        def lignes(split=split, nom=nom, domaines=domaines):
            flux = load_dataset("clapAI/MultiLingualSentiment", split=split, streaming=True)
            for i, ex in enumerate(flux):
                if ex["language"] != "fr" or "allocine" in (ex["source"] or "").lower():
                    continue
                if ex["label"] not in SENTIMENTS_CLAPAI:
                    continue
                domaines[(ex["domain"] or "").strip()] += 1
                yield {"review_id": f"clapai-{nom}-{i}",
                       "etablissement_id": f"clapai-{(ex['domain'] or '').strip()}",
                       "metier": "restaurant", "texte": ex["text"], "note": None,
                       "etiquette": {"sentiment": SENTIMENTS_CLAPAI[ex["label"]],
                                     "humeur": None, "themes": None},
                       "source_etiquette": "jeu-public", "source": ex["source"]}

        tailles[nom] = ecrire_jsonl(Path(dossier) / f"{nom}.jsonl", lignes())
        journal.info("clapAI %s par domaine : %s", nom, dict(domaines))
    return tailles


_MOTS_FR = {"le", "la", "les", "et", "est", "très", "nous", "pas", "une", "des", "du",
            "avec", "pour", "mais", "était", "chambre", "personnel", "bien", "on", "il"}
_MOTS_EN = {"the", "and", "was", "very", "we", "not", "with", "for", "but", "room",
            "staff", "is", "of", "to", "it", "they", "hotel", "great", "good"}


def langue(texte: str) -> str | None:
    """Détection de langue minimale par mots-outils : "fr", "en" ou None (incertain)."""
    mots = [m.lower().strip(".,!?;:()\"'") for m in texte.split()]
    fr = sum(m in _MOTS_FR for m in mots)
    en = sum(m in _MOTS_EN for m in mots)
    if fr >= 3 and fr > 2 * en:
        return "fr"
    if en >= 3 and en > 2 * fr:
        return "en"
    return None


def est_francais(texte: str) -> bool:
    return langue(texte) == "fr"


def textes_csv(chemin: str | Path, colonne: str, francais_seulement: bool) -> Iterator[str]:
    """Textes d'une colonne d'un CSV (par ex. un jeu Kaggle téléchargé à la main)."""
    csv.field_size_limit(10_000_000)
    with open(chemin, encoding="utf-8", errors="replace", newline="") as f:
        lecteur = csv.DictReader(f)
        if colonne not in (lecteur.fieldnames or []):
            raise SystemExit(f"Colonne « {colonne} » absente de {chemin} : {lecteur.fieldnames}")
        for ligne in lecteur:
            texte = ligne.get(colonne) or ""
            if not francais_seulement or est_francais(texte):
                yield texte


def echantillon(entree: str | Path, sortie: str | Path, n: int,
                etoiles: bool = False, graine: int = 0) -> int:
    """n avis tirés au hasard (réservoir, une passe). Avec `etoiles`, le sentiment
    vient de la note (1-2 → NEGATIF, 4-5 → POSITIF) et les 3 étoiles sont exclues :
    sert de jeu de test « faible » quand il n'y a pas d'annotation humaine."""
    rng = random.Random(graine)
    reservoir: list[dict] = []
    vus = 0
    with open(entree, encoding="utf-8") as f:
        for texte in f:
            ligne = json.loads(texte)
            if etoiles:
                s = etiquettes.depuis_etoiles(ligne.get("note"))
                if not s:
                    continue
                ligne = dict(ligne, etiquette={"sentiment": s, "humeur": None,
                                               "themes": None}, source_etiquette="etoiles")
            vus += 1
            if len(reservoir) < n:
                reservoir.append(ligne)
            else:
                j = rng.randrange(vus)
                if j < n:
                    reservoir[j] = ligne
    return ecrire_jsonl(sortie, reservoir)


def importer_apify(fichiers: list[str | Path], etablissement_id: str, sortie: str | Path,
                   metier: str = "restaurant") -> Counter:
    """Export(s) JSON d'un run Apify (console ou dépôt brut Cloud Storage) → JSON Lines.
    Réutilise la normalisation du pipeline (`apify.normaliser`) : mêmes identifiants,
    même dédoublonnage que dans BigQuery.

    Langues : le modèle est bilingue. Français et anglais restent dans leur langue
    d'origine ; les autres langues (espagnol, hébreu…) sont remplacées par la
    traduction française fournie par Google (`textTranslated`). La traduction est
    aussi conservée dans `texte_traduit`."""
    from datetime import UTC, datetime

    from watchmybusiness import apify

    items: list = []
    for chemin in fichiers:
        contenu = json.loads(Path(chemin).read_text(encoding="utf-8"))
        for item in contenu if isinstance(contenu, list) else contenu.get("items", []):
            # Google Maps Scraper : une fiche par lieu, avis dans « reviews ».
            # Reviews Scraper (celui du pipeline) : un item par avis.
            if isinstance(item, dict) and isinstance(item.get("reviews"), list):
                items += item["reviews"]
            else:
                items.append(item)
    compte = Counter(items_bruts=len(items))
    lignes = []
    def nettoyer(texte: str | None) -> str | None:
        return re.sub(r"\s*<br\s*/?>\s*", " ", texte).strip() or None if texte else None

    for l in apify.normaliser(items, etablissement_id, datetime.now(UTC)):
        original = nettoyer(l["brut"].get("text") or l["brut"].get("reviewText"))
        traduit = nettoyer(l["brut"].get("textTranslated"))
        l["texte_traduit"] = traduit
        if original and l["langue"] not in ("fr", "en") and traduit:
            l["texte"] = traduit  # langue hors modèle : traduction française de Google
            compte["traduits"] += 1
        else:
            l["texte"] = original
        compte["avis"] += 1
        if not l["texte"]:
            compte["sans_texte"] += 1
            continue
        compte[f"langue:{l['langue']}"] += 1
        lignes.append({"review_id": l["review_id"], "etablissement_id": etablissement_id,
                       "metier": metier, "texte": l["texte"], "note": l["note"],
                       "langue": l["langue"], "texte_traduit": l["texte_traduit"],
                       "reponse_proprietaire": l["reponse_proprietaire"],
                       "date_avis": l["date_avis"], "etiquette": None,
                       "source_etiquette": None,
                       # Notes Cuisine / Service / Ambiance : étiquettes faibles de thèmes.
                       "notes_detaillees": l["brut"].get("reviewDetailedRating") or None,
                       "contexte": l["brut"].get("reviewContext") or None})
        if lignes[-1]["notes_detaillees"]:
            compte["avec_notes_detaillees"] += 1
    compte["gardes"] = ecrire_jsonl(sortie, lignes)
    return compte


def importer_tripadvisor_apify(fichiers: list[str | Path], etablissement_id: str,
                               sortie: str | Path, exclure: list[str | Path] | None = None,
                               avant: str | None = None, metier: str = "restaurant") -> Counter:
    """Export(s) JSON de l'acteur Apify « Tripadvisor Reviews Scraper » → JSON Lines.

    Titre + texte forment l'avis. Seuls le français et l'anglais sont gardés (pas de
    traduction fournie). Les notes détaillées (Food, Service, Atmosphere, Value)
    deviennent des étiquettes faibles de thèmes. `exclure` : fichiers JSON Lines dont
    les review_id sont déjà connus ; `avant` : ne garder que les avis antérieurs à
    cette date (AAAA-MM-JJ), pour ne pas empiéter sur la période du jeu de test."""
    connus = {l["review_id"] for f in exclure or [] for l in lire_jsonl(f)}
    compte, lignes, vus = Counter(), [], set()
    for chemin in fichiers:
        contenu = json.loads(Path(chemin).read_text(encoding="utf-8"))
        for item in contenu if isinstance(contenu, list) else contenu.get("items", []):
            compte["items_bruts"] += 1
            rid = f"tripadvisor-{item.get('id')}"
            date = (item.get("publishedDate") or "")[:10] or None
            texte = " ".join(filter(None, [(item.get("title") or "").strip(),
                                           (item.get("text") or "").strip()]))
            lang = item.get("lang") or (langue(texte) if texte else None)
            if rid in vus or rid in connus:
                compte["doublons"] += 1
                continue
            vus.add(rid)
            if not texte:
                compte["sans_texte"] += 1
                continue
            if lang not in ("fr", "en"):
                compte["autre_langue"] += 1
                continue
            if avant and date and date >= avant:
                compte["periode_test"] += 1
                continue
            notes = {s["name"]: s["value"] for s in item.get("subratings") or []
                     if isinstance(s, dict) and s.get("name") and s.get("value")}
            compte[f"langue:{lang}"] += 1
            lignes.append({"review_id": rid, "etablissement_id": etablissement_id,
                           "metier": metier, "texte": texte,
                           "note": int(item["rating"]) if item.get("rating") else None,
                           "langue": lang, "texte_traduit": None,
                           "reponse_proprietaire": None, "date_avis": date,
                           "etiquette": None, "source_etiquette": None,
                           "notes_detaillees": notes or None, "contexte": None,
                           "source": "tripadvisor"})
    compte["gardes"] = ecrire_jsonl(sortie, lignes)
    return compte


def importer_tripadvisor(fichier: str | Path, sortie: str | Path,
                         toutes_langues: bool = False) -> Counter:
    """Avis d'hôtels TripAdvisor (Kaggle, reviews.csv) → JSON Lines.

    La note globale (`ratings['overall']`) devient `note` : elle sert d'étiquette
    faible de sentiment (étape « etoiles »). Chaque hôtel est un « établissement »,
    pour que le découpage par établissement reste valable. Par défaut, seuls les avis
    détectés en français sont gardés ; `toutes_langues` garde tout (modèle bilingue)."""
    csv.field_size_limit(100_000_000)
    compte = Counter()

    def lignes():
        with open(fichier, encoding="utf-8", errors="replace", newline="") as f:
            for ligne in csv.DictReader(f):
                compte["lus"] += 1
                texte = " ".join(filter(None, [(ligne.get("title") or "").strip("“”\" "),
                                               (ligne.get("text") or "").strip()]))
                lang = langue(texte) if texte else None
                if not texte or (not toutes_langues and lang != "fr"):
                    continue
                try:
                    note = ast.literal_eval(ligne.get("ratings") or "{}").get("overall")
                except (ValueError, SyntaxError):
                    note = None
                compte["gardes"] += 1
                compte[f"langue:{lang}"] += 1
                yield {"review_id": f"tripadvisor-{ligne['id']}",
                       "etablissement_id": f"tripadvisor-{ligne['offering_id']}",
                       "metier": "restaurant", "texte": texte,
                       "note": int(round(note)) if note else None,
                       "langue": lang,
                       "date_avis": ligne.get("date"), "etiquette": None,
                       "source_etiquette": None}

    ecrire_jsonl(sortie, lignes())
    return compte


def construire_corpus(sortie: str | Path, avis: list[str | Path], fichiers_texte: list[str],
                      allocine: int = 0, wikipedia_mo: int = 0,
                      csvs: list[str] | None = None, francais_seulement: bool = False) -> Counter:
    """Assemble : textes d'avis (JSON Lines), fichiers .txt fournis, et en option
    Allociné et Wikipédia FR téléchargés depuis Hugging Face."""
    compte = Counter()
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    with open(sortie, "w", encoding="utf-8") as f:
        def ecrire(source: str, textes: Iterable[str]) -> None:
            for t in textes:
                t = " ".join(str(t).split())
                if len(t) >= 20:
                    f.write(t + "\n")
                    compte[source] += 1

        for chemin in avis:
            ecrire("avis", (l["texte"] for l in lire_jsonl(chemin) if l.get("texte")))
        for chemin in fichiers_texte:
            with open(chemin, encoding="utf-8") as src:
                ecrire(Path(chemin).name, src)
        for spec in csvs or []:  # "fichier.csv:colonne"
            chemin, _, colonne = spec.rpartition(":")
            ecrire(Path(chemin).name, textes_csv(chemin, colonne, francais_seulement))
        if allocine:
            ecrire("allocine", _allocine(allocine))
        if wikipedia_mo:
            ecrire("wikipedia", _wikipedia(wikipedia_mo))
    return compte


# --------------------------------------------------------------------------- #
# Annotation humaine du jeu de test
# --------------------------------------------------------------------------- #
def _colonnes(metier: str) -> list[str]:
    return ["review_id", "texte", "sentiment", "humeur", *taxonomie.themes(metier)]


def exporter_annotation(entree: str | Path, dossier: str | Path, n: int = 300,
                        metier: str = "restaurant") -> list[Path]:
    """Deux CSV identiques, un par annotateur, à remplir SÉPARÉMENT.
    sentiment : POSITIF / NEGATIF / NEUTRE / MIXTE
    humeur    : joie / satisfaction / deception / frustration / colere / neutre
    thèmes    : positif / negatif / neutre, ou vide si le thème n'est pas évoqué"""
    lignes = lire_jsonl(entree)
    random.Random(42).shuffle(lignes)
    echantillon = lignes[:n]
    chemins = []
    for nom in ("annotation_A.csv", "annotation_B.csv"):
        chemin = Path(dossier) / nom
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(chemin, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=_colonnes(metier), delimiter=";")
            w.writeheader()
            for l in echantillon:
                w.writerow({"review_id": l["review_id"], "texte": l["texte"]})
        chemins.append(chemin)
    return chemins


def _lire_annotation(chemin: str | Path, metier: str) -> dict[str, dict]:
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))
    resultat = {}
    for l in lignes:
        resultat[l["review_id"]] = {
            "sentiment": (l.get("sentiment") or "").strip().upper() or None,
            "humeur": (l.get("humeur") or "").strip().lower() or None,
            "themes": {t: (l.get(t) or "").strip().lower()
                       for t in taxonomie.themes(metier) if (l.get(t) or "").strip()},
        }
    return resultat


def kappa(fichier_a: str | Path, fichier_b: str | Path, desaccords: str | Path,
          metier: str = "restaurant") -> dict[str, float]:
    a, b = _lire_annotation(fichier_a, metier), _lire_annotation(fichier_b, metier)
    communs = sorted(set(a) & set(b))
    resultats = {
        "sentiment": metriques.kappa_cohen([a[i]["sentiment"] or "?" for i in communs],
                                           [b[i]["sentiment"] or "?" for i in communs]),
        "humeur": metriques.kappa_cohen([a[i]["humeur"] or "?" for i in communs],
                                        [b[i]["humeur"] or "?" for i in communs]),
    }
    for t in taxonomie.themes(metier):
        resultats[f"theme:{t}"] = metriques.kappa_cohen(
            [a[i]["themes"].get(t, "absent") for i in communs],
            [b[i]["themes"].get(t, "absent") for i in communs])
    with open(desaccords, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["review_id", "champ", "annotateur_A", "annotateur_B"])
        for i in communs:
            for champ in ("sentiment", "humeur"):
                if a[i][champ] != b[i][champ]:
                    w.writerow([i, champ, a[i][champ], b[i][champ]])
            for t in taxonomie.themes(metier):
                va, vb = a[i]["themes"].get(t, "absent"), b[i]["themes"].get(t, "absent")
                if va != vb:
                    w.writerow([i, t, va, vb])
    return resultats


def importer_annotation(fichier_final: str | Path, entree: str | Path, sortie: str | Path,
                        metier: str = "restaurant", source: str = "humain") -> int:
    """CSV arbitré (désaccords tranchés à deux) → jeu de test « or ».
    `source` indique qui a annoté : « humain », ou « claude » pour une pré-annotation
    par IA pas encore relue (à ne pas présenter comme une vérité terrain humaine)."""
    annot = _lire_annotation(fichier_final, metier)
    lignes = [dict(l, etiquette=annot[l["review_id"]], source_etiquette=source)
              for l in lire_jsonl(entree) if l["review_id"] in annot]
    return ecrire_jsonl(sortie, lignes)
