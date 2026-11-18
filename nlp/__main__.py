"""Chaîne complète du NLP maison, depuis la racine du dépôt :

    python -m nlp exporter                       # avis + étiquettes Gemini existantes (BigQuery)
    python -m nlp etiqueter data/avis.jsonl      # étiquettes Gemini avec humeur (GEMINI_API_KEY)
    python -m nlp decouper data/avis_etiquetes.jsonl
    python -m nlp corpus --allocine 50000 --wikipedia-mo 200
    python -m nlp tokenizer
    python -m nlp pretrain --taille S --pas 20000
    python -m nlp finetune --init modeles/pretrain-S.pt --etape etoiles --sortie modeles/etoiles-S
    python -m nlp finetune --init modeles/etoiles-S/modele.pt --sortie modeles/nlp-v1-S
    python -m nlp bayes
    python -m nlp annoter / kappa / importer        # jeu de test « or » annoté à la main
    python -m nlp etiqueter data/test_or.jsonl --sortie data/gemini_test.jsonl
    python -m nlp evaluer --maison modeles/nlp-v1-S --gemini data/gemini_test.jsonl
    python -m nlp predire modeles/nlp-v1-S "Une heure d'attente, mais le falafel est divin"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "app"))

D = "data"
M = "modeles"


def combiner(principal: str | Path, themes: str | Path, sortie: str | Path) -> str:
    """Paquet combiné : modèle principal (sentiment, humeur, confiance) + spécialiste
    des thèmes (`modele_themes.pt`). Les deux doivent partager le même tokenizer."""
    import shutil

    principal, themes, sortie = Path(principal), Path(themes), Path(sortie)
    if (principal / "tokenizer.json").read_bytes() != (themes / "tokenizer.json").read_bytes():
        raise SystemExit("Les deux paquets n'ont pas le même tokenizer.")
    sortie.mkdir(parents=True, exist_ok=True)
    for nom in ("tokenizer.json", "modele.pt"):
        shutil.copyfile(principal / nom, sortie / nom)
    shutil.copyfile(themes / "modele.pt", sortie / "modele_themes.pt")
    return str(sortie)


def main() -> int:
    p = argparse.ArgumentParser(prog="python -m nlp", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sous = p.add_subparsers(dest="commande", required=True)

    c = sous.add_parser("exporter", help="avis_bruts + dernière analyse Gemini → JSON Lines")
    c.add_argument("--projet", default=os.environ.get("GOOGLE_CLOUD_PROJECT",
                                                      "watch-my-business-512316"))
    c.add_argument("--dataset", default="watchmybusiness")
    c.add_argument("--sortie", default=f"{D}/avis.jsonl")

    c = sous.add_parser("etiqueter", help="étiquettes Gemini (sentiment, humeur, thèmes)")
    c.add_argument("entree")
    c.add_argument("--sortie", default=f"{D}/avis_etiquetes.jsonl")
    c.add_argument("--modele", default="gemini-3.5-flash")
    c.add_argument("--nom", default="l'établissement", help="nom du restaurant, pour la consigne")
    c.add_argument("--parallelisme", type=int, default=8)
    c.add_argument("--limite", type=int)

    c = sous.add_parser("decouper", help="train / val / test par restaurant")
    c.add_argument("entree", nargs="?", default=f"{D}/avis_etiquetes.jsonl")
    c.add_argument("--dossier", default=D)
    c.add_argument("--test", help="établissements du test, séparés par des virgules")
    c.add_argument("--val", help="établissements de la validation")
    c.add_argument("--par-date", action="store_true",
                   help="un seul établissement : test = avis les plus récents")

    c = sous.add_parser("allocine", help="critiques Allociné → train/val/test étiquetés")
    c.add_argument("--dossier", default=f"{D}/allocine")
    c.add_argument("--max-train", type=int)

    c = sous.add_parser("clapai", help="clapAI/MultiLingualSentiment (français) → sentiment")
    c.add_argument("--dossier", default=f"{D}/clapai")

    c = sous.add_parser("emotion", help="JusteLeo/French-emotion → humeur")
    c.add_argument("--dossier", default=f"{D}/emotion")

    c = sous.add_parser("apify", help="export(s) JSON Apify → JSON Lines")
    c.add_argument("fichiers", nargs="+")
    c.add_argument("--etablissement", default="as-du-fallafel")
    c.add_argument("--sortie", default=f"{D}/as-du-fallafel/avis.jsonl")

    c = sous.add_parser("tripadvisor", help="avis d'hôtels TripAdvisor (Kaggle) → JSON Lines")
    c.add_argument("--fichier", default=f"{D}/tripadvisor/reviews.csv")
    c.add_argument("--sortie", default=f"{D}/tripadvisor/avis.jsonl")
    c.add_argument("--toutes-langues", action="store_true")

    c = sous.add_parser("tripadvisor-apify",
                        help="export(s) JSON Apify « Tripadvisor Reviews » → JSON Lines")
    c.add_argument("fichiers", nargs="+")
    c.add_argument("--etablissement", default="as-du-fallafel")
    c.add_argument("--sortie", required=True)
    c.add_argument("--exclure", nargs="*", default=[], help="JSON Lines d'avis déjà connus")
    c.add_argument("--avant", help="garder seulement les avis antérieurs (AAAA-MM-JJ)")

    c = sous.add_parser("combiner", help="paquet principal + spécialiste des thèmes")
    c.add_argument("principal", help="paquet pour sentiment, humeur et confiance")
    c.add_argument("themes", help="paquet dont on garde seulement les thèmes")
    c.add_argument("--sortie", required=True)

    c = sous.add_parser("calibrer-themes",
                        help="seuils de détection par thème, choisis sur la validation")
    c.add_argument("paquet")
    c.add_argument("--val", nargs="+", required=True)

    c = sous.add_parser("tableau-demo",
                        help="données du tableau de bord en mode démo (sans BigQuery)")
    c.add_argument("--paquet", default=f"{M}/fallafel/nlp-S-duo")
    c.add_argument("--avis", nargs="+", default=[f"{D}/l'asdefalafel/avis.jsonl",
                                                 f"{D}/l'asdefalafel/tripadvisor/avis.jsonl"])
    c.add_argument("--sortie", default=f"{D}/demo/tableau.json")
    c.add_argument("--semaines", type=int, default=26)

    c = sous.add_parser("vers-bigquery",
                        help="avis + analyses du modèle → fichiers pour BigQuery")
    c.add_argument("--avis", default=f"{D}/l'asdefalafel")
    c.add_argument("--paquet", default=f"{M}/fallafel/nlp-S-duo")
    c.add_argument("--sortie", default=f"{D}/bigquery")
    c.add_argument("--pipeline", action="store_true",
                   help="charger dans avis_bruts / avis_analyses (sans coût Gemini)")
    c.add_argument("--appliquer", action="store_true", help="sans ce drapeau : simulation")

    c = sous.add_parser("echantillon", help="sous-ensemble aléatoire d'un JSON Lines")
    c.add_argument("entree")
    c.add_argument("sortie")
    c.add_argument("-n", type=int, default=3000)
    c.add_argument("--etoiles", action="store_true",
                   help="étiqueter le sentiment depuis les étoiles (3 étoiles exclues)")

    c = sous.add_parser("corpus", help="corpus de pré-entraînement (texte brut)")
    c.add_argument("--avis", nargs="*", default=[f"{D}/train.jsonl"])
    c.add_argument("--texte", nargs="*", default=[], help="fichiers .txt supplémentaires")
    c.add_argument("--allocine", type=int, default=0, help="nb de critiques (pip install datasets)")
    c.add_argument("--wikipedia-mo", type=int, default=0, help="Mo de Wikipédia FR")
    c.add_argument("--csv", nargs="*", default=[],
                   help="fichier.csv:colonne, par ex. un jeu Kaggle téléchargé à la main")
    c.add_argument("--francais-seulement", action="store_true",
                   help="ne garder que les textes détectés en français (pour --csv)")
    c.add_argument("--sortie", default=f"{D}/corpus.txt")

    c = sous.add_parser("tokenizer", help="apprendre le BPE")
    c.add_argument("--corpus", default=f"{D}/corpus.txt")
    c.add_argument("--taille", type=int, default=16000)
    c.add_argument("--max-lignes", type=int, default=300_000)
    c.add_argument("--sortie", default=f"{M}/tokenizer.json")

    c = sous.add_parser("pretrain", help="prédire le jeton suivant")
    c.add_argument("--corpus", default=f"{D}/corpus.txt")
    c.add_argument("--tokenizer", default=f"{M}/tokenizer.json")
    c.add_argument("--taille", default="S", choices=["XS", "S", "M", "L"])
    c.add_argument("--contexte", type=int, default=256)
    c.add_argument("--pas", type=int, default=5000)
    c.add_argument("--lot", type=int, default=32)
    c.add_argument("--accumulation", type=int, default=1)
    c.add_argument("--lr", type=float, default=6e-4)
    c.add_argument("--eval-tous", type=int, default=250)
    c.add_argument("--init", help="reprendre depuis un modèle (ex. pré-entraînement avis "
                                  "après Wikipédia)")
    c.add_argument("--sortie")

    c = sous.add_parser("finetune", help="têtes sentiment / humeur / thèmes")
    c.add_argument("--train", nargs="+", default=[f"{D}/train.jsonl"],
                   help="un ou plusieurs fichiers (étiquettes partielles acceptées)")
    c.add_argument("--val", nargs="+", default=[f"{D}/val.jsonl"])
    c.add_argument("--tokenizer", default=f"{M}/tokenizer.json")
    c.add_argument("--init", help="modèle pré-entraîné (sinon : à partir de zéro)")
    c.add_argument("--taille", default="S", choices=["XS", "S", "M", "L"])
    c.add_argument("--etape", default="etiquettes", choices=["etoiles", "etiquettes"])
    c.add_argument("--epoques", type=int, default=5)
    c.add_argument("--lot", type=int, default=32)
    c.add_argument("--lr", type=float)
    c.add_argument("--version", default="nlp-v1")
    c.add_argument("--precision-cible", type=float, default=0.9)
    c.add_argument("--facteur-themes", type=float, default=1.0,
                   help="poids de la perte des thèmes face au sentiment et à l'humeur")
    c.add_argument("--max-exemples", type=int, help="limiter le jeu d'entraînement (essais)")
    c.add_argument("--sortie", required=True, help="dossier du paquet modèle")

    c = sous.add_parser("bayes", help="plancher : Bayes naïf")
    c.add_argument("--train", nargs="+", default=[f"{D}/train.jsonl"])
    c.add_argument("--sortie", default=f"{M}/bayes.json")

    c = sous.add_parser("annoter", help="CSV d'annotation pour les deux annotateurs")
    c.add_argument("--entree", default=f"{D}/test.jsonl")
    c.add_argument("-n", type=int, default=300)
    c.add_argument("--dossier", default=f"{D}/annotation")

    c = sous.add_parser("kappa", help="accord entre annotateurs + liste des désaccords")
    c.add_argument("--a", default=f"{D}/annotation/annotation_A.csv")
    c.add_argument("--b", default=f"{D}/annotation/annotation_B.csv")
    c.add_argument("--desaccords", default=f"{D}/annotation/desaccords.csv")

    c = sous.add_parser("importer", help="CSV arbitré → jeu de test « or »")
    c.add_argument("finale", help="CSV après arbitrage des désaccords")
    c.add_argument("--entree", default=f"{D}/test.jsonl")
    c.add_argument("--sortie", default=f"{D}/test_or.jsonl")
    c.add_argument("--source", default="humain", help="humain, ou claude (pré-annotation IA)")

    c = sous.add_parser("evaluer", help="tableau comparatif sur le jeu de test")
    c.add_argument("--test", default=f"{D}/test_or.jsonl")
    c.add_argument("--maison", nargs="*", default=[])
    c.add_argument("--bayes", default=f"{M}/bayes.json")
    c.add_argument("--gemini", help="prédictions Gemini sur le test (commande etiqueter)")
    c.add_argument("--sortie", default=f"{D}/resultats.md")

    c = sous.add_parser("predire", help="essayer le modèle sur un texte")
    c.add_argument("dossier")
    c.add_argument("texte")

    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    if a.commande == "exporter":
        from .donnees import exporter_bigquery
        print(f"{exporter_bigquery(a.projet, a.dataset, a.sortie)} avis → {a.sortie}")
    elif a.commande == "etiqueter":
        from .etiquetage import etiqueter
        print(etiqueter(a.entree, a.sortie, a.modele, nom=a.nom, parallelisme=a.parallelisme,
                        limite=a.limite))
    elif a.commande == "decouper":
        from .donnees import decouper, decouper_par_date
        if a.par_date:
            print(decouper_par_date(a.entree, a.dossier))
        else:
            print(decouper(a.entree, a.dossier, a.test.split(",") if a.test else None,
                           a.val.split(",") if a.val else None))
    elif a.commande == "allocine":
        from .donnees import importer_allocine
        print(importer_allocine(a.dossier, a.max_train))
    elif a.commande == "clapai":
        from .donnees import importer_clapai
        print(importer_clapai(a.dossier))
    elif a.commande == "emotion":
        from .donnees import importer_french_emotion
        print(importer_french_emotion(a.dossier))
    elif a.commande == "apify":
        from .donnees import importer_apify
        print(dict(importer_apify(a.fichiers, a.etablissement, a.sortie)))
    elif a.commande == "tripadvisor":
        from .donnees import importer_tripadvisor
        print(dict(importer_tripadvisor(a.fichier, a.sortie, a.toutes_langues)))
    elif a.commande == "tripadvisor-apify":
        from .donnees import importer_tripadvisor_apify
        print(dict(importer_tripadvisor_apify(a.fichiers, a.etablissement, a.sortie,
                                              a.exclure, a.avant)))
    elif a.commande == "combiner":
        print(combiner(a.principal, a.themes, a.sortie))
    elif a.commande == "calibrer-themes":
        from .evaluation import calibrer_themes
        print(json.dumps(calibrer_themes(a.paquet, a.val), ensure_ascii=False, indent=1))
    elif a.commande == "tableau-demo":
        from .tableau_demo import construire
        print(construire(a.paquet, a.avis, a.sortie, nb_semaines=a.semaines))
    elif a.commande == "vers-bigquery":
        from .vers_bigquery import construire, vers_pipeline
        print(vers_pipeline(a.avis, a.paquet, a.appliquer) if a.pipeline
              else construire(a.avis, a.paquet, a.sortie))
    elif a.commande == "echantillon":
        from .donnees import echantillon
        print(f"{echantillon(a.entree, a.sortie, a.n, a.etoiles)} avis → {a.sortie}")
    elif a.commande == "corpus":
        from .donnees import construire_corpus
        print(dict(construire_corpus(a.sortie, a.avis, a.texte, a.allocine, a.wikipedia_mo,
                                     a.csv, a.francais_seulement)))
    elif a.commande == "tokenizer":
        from .entrainement import entrainer_tokenizer
        entrainer_tokenizer(a.corpus, a.sortie, a.taille, a.max_lignes)
    elif a.commande == "pretrain":
        from .entrainement import pretrain
        sortie = a.sortie or f"{M}/pretrain-{a.taille}.pt"
        r = pretrain(a.corpus, a.tokenizer, sortie, a.taille, a.contexte, a.pas, a.lot,
                     a.accumulation, a.lr, a.eval_tous, a.init)
        print(f"meilleure perte de validation {r['perte_val']:.3f} → {sortie}")
    elif a.commande == "finetune":
        from .entrainement import finetune
        r = finetune(a.train, a.val, a.tokenizer, a.sortie, a.init, a.taille, etape=a.etape,
                     epoques=a.epoques, lot=a.lot, lr=a.lr, version=a.version,
                     precision_cible=a.precision_cible, max_exemples=a.max_exemples,
                     facteur_themes=a.facteur_themes)
        print(json.dumps(r["meta"], ensure_ascii=False, indent=1))
    elif a.commande == "bayes":
        from watchmybusiness.nlp.etiquettes import themes

        from .bayes import BayesAvis
        from .donnees import lire_jsonl
        lignes = [l for f in a.train for l in lire_jsonl(f) if l.get("etiquette")]
        Path(a.sortie).parent.mkdir(parents=True, exist_ok=True)
        BayesAvis(themes()).entrainer(lignes).sauver(a.sortie)
        print(f"Bayes naïf entraîné sur {len(lignes)} avis → {a.sortie}")
    elif a.commande == "annoter":
        from .donnees import exporter_annotation
        for chemin in exporter_annotation(a.entree, a.dossier, a.n):
            print(chemin)
    elif a.commande == "kappa":
        from .donnees import kappa
        for champ, k in kappa(a.a, a.b, a.desaccords).items():
            print(f"{champ:28s} κ = {k:.3f}")
        print(f"désaccords à arbitrer : {a.desaccords}")
    elif a.commande == "importer":
        from .donnees import importer_annotation
        print(f"{importer_annotation(a.finale, a.entree, a.sortie, source=a.source)} "
              f"avis → {a.sortie}")
    elif a.commande == "evaluer":
        from .evaluation import comparer
        bayes = a.bayes if a.bayes and Path(a.bayes).exists() else None
        print(comparer(a.test, a.maison, bayes, a.gemini, a.sortie))
    elif a.commande == "predire":
        from watchmybusiness.nlp.service import ModeleMaison
        print(json.dumps(ModeleMaison(a.dossier).predire(a.texte), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
