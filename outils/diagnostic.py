"""Diagnostic local contre le vrai projet GCP (identifiants `gcloud auth application-default`).

    python outils/diagnostic.py modeles                      # modèles Gemini joignables par région
    python outils/diagnostic.py analyse "texte" [--note 2]   # une analyse d'avis réelle
    python outils/diagnostic.py agent --date-fin 2026-10-18  # outils BigQuery de l'agent
    python outils/diagnostic.py agent --rediger              # … et synthèse rédigée par Gemini
    python outils/diagnostic.py web                          # appels de l'API du tableau de bord

La configuration est celle des jobs (variables d'environnement, valeurs par défaut
sinon) : seul GOOGLE_CLOUD_PROJECT est prérempli.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "watch-my-business-512316")

from watchmybusiness import config, gemini, rapport  # noqa: E402

ETABLISSEMENT = "as-du-fallafel"
NOM = "L'As du Fallafel"


def afficher(titre: str, valeur) -> None:
    print(f"\n== {titre}\n{json.dumps(valeur, ensure_ascii=False, indent=1, default=str)}")


def modeles(cfg, arguments) -> None:
    from google import genai

    for region in arguments.regions:
        client = genai.Client(vertexai=True, project=cfg.projet, location=region)
        for modele in arguments.modeles:
            try:
                client.models.generate_content(model=modele, contents="Réponds OK.")
                print(f"OK  {region:<14} {modele}")
            except Exception as erreur:
                print(f"--  {region:<14} {modele:<24} {str(erreur)[:70]}")


def analyse(cfg, arguments) -> None:
    client = gemini.client(cfg.projet, cfg.region_gemini)
    sortie = gemini.analyser(
        client, cfg.modele_gemini, "restaurant", NOM, arguments.texte, arguments.note
    )
    afficher(f"{cfg.modele_gemini} ({cfg.region_gemini})", sortie)


def agent(cfg, arguments) -> None:
    fin = date.fromisoformat(arguments.date_fin)
    donnees = rapport.Donnees(cfg, ETABLISSEMENT, fin - timedelta(days=6), fin)
    kpi = donnees.kpi(0)
    afficher("kpi", kpi)
    afficher("comparer_semaine_precedente", donnees.comparaison())
    afficher("avis_actionnables", donnees.actionnables())
    if arguments.rediger:
        print("\n" + rapport.rediger(cfg, {"nom": NOM}, donnees, kpi))


def web(cfg, arguments) -> None:
    from fastapi.testclient import TestClient

    from watchmybusiness import web as appli

    client = TestClient(appli.creer_application())
    afficher("etablissements", client.get("/api/etablissements").json())
    rapports = client.get("/api/rapports", params={"etablissement": ETABLISSEMENT}).json()[
        "rapports"
    ]
    afficher("rapports", [(r["semaine_id"], r["nb_avis"]) for r in rapports])
    if not rapports:
        return
    detail = client.get(
        f"/api/rapports/{rapports[0]['semaine_id']}", params={"etablissement": ETABLISSEMENT}
    ).json()
    afficher("detail (sans synthèse)", {k: v for k, v in detail.items() if k != "synthese"})
    avis = client.get(
        "/api/avis",
        params={
            "etablissement": ETABLISSEMENT,
            "debut": detail["periode_debut"],
            "fin": detail["periode_fin"],
            "sentiment": "NEGATIF",
        },
    ).json()
    afficher(f"avis négatifs ({avis['nb']})", avis["avis"][:2])


def main() -> None:
    analyseur = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sous = analyseur.add_subparsers(dest="commande", required=True)

    p = sous.add_parser("modeles")
    p.add_argument("--regions", nargs="+", default=["europe-west1", "europe-west3", "global"])
    p.add_argument(
        "--modeles",
        nargs="+",
        default=["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash"],
    )
    p.set_defaults(fonction=modeles)

    p = sous.add_parser("analyse")
    p.add_argument(
        "texte",
        nargs="?",
        default=(
            "Attente d'une heure, servie en cinq minutes. Le falafel était bon mais trop cher."
        ),
    )
    p.add_argument("--note", type=int, default=2)
    p.set_defaults(fonction=analyse)

    p = sous.add_parser("agent")
    p.add_argument("--date-fin", default=rapport.semaine_ecoulee(date.today())[1].isoformat())
    p.add_argument("--rediger", action="store_true", help="appelle aussi l'agent Gemini")
    p.set_defaults(fonction=agent)

    sous.add_parser("web").set_defaults(fonction=web)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = analyseur.parse_args()
    arguments.fonction(config.charger(), arguments)


if __name__ == "__main__":
    main()
