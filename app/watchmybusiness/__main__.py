"""Point d'entrée unique de l'image : `python -m watchmybusiness <commande>`.

Une seule image pour les trois Cloud Run Jobs (collecte, analyse, rapport) et
le service web : seul l'argument change.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from . import analyse, collecte, config, rapport


class _JournalJson(logging.Formatter):
    """Format attendu par Cloud Logging : la sévérité est reconnue."""

    def format(self, enregistrement: logging.LogRecord) -> str:
        return json.dumps(
            {
                "severity": enregistrement.levelname,
                "message": enregistrement.getMessage(),
                "module": enregistrement.module,
            },
            ensure_ascii=False,
        )


def main() -> int:
    analyseur = argparse.ArgumentParser(prog="watchmybusiness")
    sous = analyseur.add_subparsers(dest="job", required=True)
    sous.add_parser("collecte")
    p_rejouer = sous.add_parser("rejouer", help="recharger BigQuery depuis le dépôt brut")
    p_rejouer.add_argument(
        "--prefixe",
        default="",
        help="ex. as-du-fallafel/2026-10-22/ (défaut : tout le dépôt)",
    )
    sous.add_parser("analyse")
    sous.add_parser("web", help="tableau de bord + API (service Cloud Run)")
    p_rapport = sous.add_parser("rapport")
    p_rapport.add_argument("--date-fin", help="dimanche AAAA-MM-JJ (défaut : semaine écoulée)")
    p_rapport.add_argument("--sans-email", action="store_true")
    arguments = analyseur.parse_args()

    gestionnaire = logging.StreamHandler(sys.stdout)
    gestionnaire.setFormatter(_JournalJson())
    logging.basicConfig(level=logging.INFO, handlers=[gestionnaire])
    for bruyant in ("httpx", "urllib3"):
        logging.getLogger(bruyant).setLevel(logging.WARNING)
    # Les modèles « thinking » renvoient une signature de raisonnement à chaque
    # réponse : le SDK le signale en WARNING, sans conséquence.
    logging.getLogger("google_genai").setLevel(logging.ERROR)

    if arguments.job == "web":
        from . import web

        return web.servir()

    cfg = config.charger()
    if arguments.job == "collecte":
        return collecte.executer(cfg)
    if arguments.job == "rejouer":
        return collecte.rejouer(cfg, arguments.prefixe)
    if arguments.job == "analyse":
        return analyse.executer(cfg)
    return rapport.executer(cfg, arguments.date_fin, envoyer=not arguments.sans_email)


if __name__ == "__main__":
    sys.exit(main())
