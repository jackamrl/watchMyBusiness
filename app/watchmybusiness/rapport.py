"""Job « rapport » : KPI calculés en SQL + synthèse rédigée par un agent Gemini.

Partage des rôles, volontairement strict :
  * les chiffres (pourcentages, comptes, tendance) viennent du SQL, jamais du modèle ;
  * l'agent choisit quoi regarder via ses outils (comparaison, citations,
    avis actionnables, thèmes émergents) et rédige l'interprétation.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime, timedelta

from . import courriel, entrepot, gemini, taxonomie
from .config import Config
from .entrepot import serialisable

journal = logging.getLogger(__name__)

SEUIL_TENDANCE = 15.0
NB_THEMES = 5


# --------------------------------------------------------------------------- #
# Fenêtre
# --------------------------------------------------------------------------- #


def semaine_ecoulee(aujourd_hui: date) -> tuple[date, date]:
    """Lundi → dimanche de la dernière semaine complète."""
    fin = aujourd_hui - timedelta(days=aujourd_hui.isoweekday())
    return fin - timedelta(days=6), fin


def semaine_id(debut: date) -> str:
    annee, numero, _ = debut.isocalendar()
    return f"{annee}-W{numero:02d}"


def tendance(pct_positif: float, pct_negatif: float) -> str:
    ecart = pct_positif - pct_negatif
    if ecart > SEUIL_TENDANCE:
        return "positive"
    if ecart < -SEUIL_TENDANCE:
        return "negative"
    return "mitigee"


# --------------------------------------------------------------------------- #
# Requêtes (partagées entre le calcul des KPI et les outils de l'agent)
# --------------------------------------------------------------------------- #


class Donnees:
    def __init__(self, config: Config, etablissement_id: str, debut: date, fin: date):
        self.config = config
        self.etab = etablissement_id
        self.debut = debut
        self.fin = fin

    def _fenetre(self, decalage: int) -> dict:
        return {
            "etab": self.etab,
            "debut": self.debut - timedelta(weeks=decalage),
            "fin": self.fin - timedelta(weeks=decalage),
            "version": gemini.VERSION_PROMPT,
        }

    def kpi(self, decalage: int = 0) -> dict:
        c = self.config
        lignes = entrepot.requete(
            c,
            f"""
            WITH b AS (
              SELECT * FROM {c.table('avis_bruts')}
              WHERE etablissement_id = @etab AND date_avis BETWEEN @debut AND @fin
            ), a AS (
              SELECT * FROM {c.table('avis_analyses')}
              WHERE etablissement_id = @etab AND version_prompt = @version
                AND date_avis BETWEEN @debut AND @fin
            )
            SELECT
              (SELECT COUNT(*) FROM b) AS nb_avis,
              (SELECT ROUND(AVG(note), 2) FROM b) AS note_moyenne,
              COUNT(*) AS nb_analyses,
              COUNTIF(sentiment = 'POSITIF') AS nb_positif,
              COUNTIF(sentiment = 'NEGATIF') AS nb_negatif,
              COUNTIF(sentiment = 'NEUTRE')  AS nb_neutre,
              COUNTIF(sentiment = 'MIXTE')   AS nb_mixte,
              ROUND(AVG(score), 3) AS score_moyen,
              COUNTIF(actionnable) AS nb_actionnables
            FROM a
            """,
            self._fenetre(decalage),
        )[0]
        total = lignes["nb_analyses"] or 0
        for cle in ("positif", "negatif", "neutre", "mixte"):
            lignes[f"pct_{cle}"] = round(100 * lignes[f"nb_{cle}"] / total, 1) if total else 0.0
        lignes["tendance"] = (
            tendance(lignes["pct_positif"], lignes["pct_negatif"]) if total else "aucune"
        )
        return serialisable(lignes)

    def themes(self, decalage: int = 0) -> list[dict]:
        c = self.config
        lignes = entrepot.requete(
            c,
            f"""
            SELECT t.theme, t.polarite, COUNT(*) AS occurrences
            FROM {c.table('avis_analyses')}, UNNEST(themes) t
            WHERE etablissement_id = @etab AND version_prompt = @version
              AND date_avis BETWEEN @debut AND @fin
            GROUP BY 1, 2
            ORDER BY occurrences DESC
            """,
            self._fenetre(decalage),
        )
        for ligne in lignes:
            ligne["libelle"] = taxonomie.libelle(ligne["theme"])
        return serialisable(lignes)

    def citations(self, theme: str, polarite: str, limite: int = 3) -> list[dict]:
        c = self.config
        parametres = {
            **self._fenetre(0),
            "theme": theme,
            "polarite": polarite,
            "limite": max(1, min(limite, 10)),
        }
        return serialisable(
            entrepot.requete(
                c,
                f"""
            SELECT a.date_avis, a.note, t.extrait
            FROM {c.table('avis_analyses')} a, UNNEST(themes) t
            WHERE a.etablissement_id = @etab AND a.version_prompt = @version
              AND a.date_avis BETWEEN @debut AND @fin
              AND t.theme = @theme AND t.polarite = @polarite
            ORDER BY ABS(a.score) DESC
            LIMIT @limite
            """,
                parametres,
            )
        )

    def actionnables(self, limite: int = 8) -> list[dict]:
        c = self.config
        return serialisable(
            entrepot.requete(
                c,
                f"""
            SELECT date_avis, note, sentiment, resume
            FROM {c.table('avis_analyses')}
            WHERE etablissement_id = @etab AND version_prompt = @version
              AND date_avis BETWEEN @debut AND @fin AND actionnable
            ORDER BY score
            LIMIT @limite
            """,
                {**self._fenetre(0), "limite": max(1, min(limite, 20))},
            )
        )

    def comparaison(self) -> dict:
        courante, precedente = self.kpi(0), self.kpi(1)
        ecarts = {}
        if precedente["nb_analyses"]:
            for cle in ("nb_avis", "note_moyenne", "pct_positif", "pct_negatif", "pct_mixte"):
                if courante[cle] is not None and precedente[cle] is not None:
                    ecarts[cle] = round(courante[cle] - precedente[cle], 2)
        themes_avant = {(t["theme"], t["polarite"]): t["occurrences"] for t in self.themes(1)}
        themes_maintenant = {(t["theme"], t["polarite"]): t["occurrences"] for t in self.themes(0)}
        evolutions = sorted(
            (
                {
                    "theme": theme,
                    "libelle": taxonomie.libelle(theme),
                    "polarite": polarite,
                    "semaine": themes_maintenant.get((theme, polarite), 0),
                    "precedente": themes_avant.get((theme, polarite), 0),
                }
                for theme, polarite in set(themes_avant) | set(themes_maintenant)
            ),
            key=lambda e: -abs(e["semaine"] - e["precedente"]),
        )
        return {
            "semaine": courante,
            "semaine_precedente": precedente,
            "ecarts": ecarts,
            "evolution_themes": evolutions[:8],
            "precedente_disponible": bool(precedente["nb_analyses"]),
        }

    def emergents(self) -> list[dict]:
        c = self.config
        return serialisable(
            entrepot.requete(
                c,
                f"""
            SELECT theme_emergent, COUNT(*) AS occurrences
            FROM {c.table('avis_analyses')}
            WHERE etablissement_id = @etab AND version_prompt = @version
              AND date_avis BETWEEN @debut AND @fin AND theme_emergent IS NOT NULL
            GROUP BY 1 ORDER BY 2 DESC LIMIT 10
            """,
                self._fenetre(0),
            )
        )


def classement(themes: list[dict], polarite: str) -> list[dict]:
    retenus = [t for t in themes if t["polarite"] == polarite]
    total = sum(t["occurrences"] for t in retenus) or 1
    return [
        {**t, "part": round(100 * t["occurrences"] / total, 1)}
        for t in sorted(retenus, key=lambda t: -t["occurrences"])[:NB_THEMES]
    ]


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #

CONSIGNE_AGENT = """Tu es l'analyste satisfaction client de WatchMyBusiness.
Tu rédiges le rapport hebdomadaire de « {nom} » pour son gérant, en français.

Tu disposes d'outils qui interrogent BigQuery. Avant d'écrire, appelle au minimum
`comparer_semaine_precedente`, puis `citations` pour les principaux thèmes
négatifs, et `avis_actionnables`.

Indicateurs officiels de la semaine (calculés en SQL, font foi) :
{kpi}

Règles strictes :
- La tendance officielle de la semaine est « {tendance} ». Ne la contredis pas.
- N'invente aucun chiffre : ne cite que des valeurs ci-dessus ou renvoyées par les outils.
- Ne dis pas que la semaine précédente est indisponible si
  `comparer_semaine_precedente` renvoie precedente_disponible = true.
- Les citations doivent être reprises telles quelles depuis l'outil `citations`.
- Pas de jargon technique (pas de « sentiment », « score », « version de prompt »).

Format (Markdown, 250 mots maximum) :
## En bref
2 à 3 phrases : comment s'est passée la semaine et pourquoi.
## Ce qui a posé problème
## Ce qui a bien fonctionné
## Évolution par rapport à la semaine précédente
## Actions recommandées
3 actions concrètes au maximum, priorisées.
"""


def rediger(config: Config, etab: dict, donnees: Donnees, kpi: dict) -> str:
    from google.genai import types

    def comparer_semaine_precedente() -> dict:
        """Indicateurs de la semaine du rapport et de la semaine précédente,
        écarts (en points) et évolution du nombre d'occurrences par thème."""
        return donnees.comparaison()

    def themes_semaine() -> list[dict]:
        """Thèmes évoqués dans les avis de la semaine du rapport, avec leur
        polarité (positif/negatif/neutre) et leur nombre d'occurrences."""
        return donnees.themes(0)

    def citations(theme: str, polarite: str, limite: int = 3) -> list[dict]:
        """Extraits d'avis de la semaine du rapport pour un thème (identifiant,
        ex. service_accueil) et une polarité (positif, negatif ou neutre)."""
        return donnees.citations(theme, polarite, int(limite))

    def avis_actionnables(limite: int = 8) -> list[dict]:
        """Résumés des avis de la semaine signalant un problème concret
        corrigeable par le gérant, du plus négatif au moins négatif."""
        return donnees.actionnables(int(limite))

    def themes_emergents() -> list[dict]:
        """Sujets récurrents de la semaine qui ne rentrent dans aucun thème connu."""
        return donnees.emergents()

    client_genai = gemini.client(config.projet, config.region_gemini)
    reponse = client_genai.models.generate_content(
        model=config.modele_gemini,
        contents=(
            f"Rédige le rapport de la semaine du {donnees.debut:%d/%m/%Y} "
            f"au {donnees.fin:%d/%m/%Y}."
        ),
        config=types.GenerateContentConfig(
            system_instruction=CONSIGNE_AGENT.format(
                nom=etab["nom"],
                kpi=json.dumps(kpi, ensure_ascii=False),
                tendance=kpi["tendance"],
            ),
            temperature=0.2,
            tools=[
                comparer_semaine_precedente,
                themes_semaine,
                citations,
                avis_actionnables,
                themes_emergents,
            ],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=15
            ),
        ),
    )
    appels = [
        f"{partie.function_call.name}({dict(partie.function_call.args or {})})"
        for contenu in (reponse.automatic_function_calling_history or [])
        for partie in (contenu.parts or [])
        if partie.function_call
    ]
    journal.info("%s : appels de l'agent %s", etab["nom"], appels)
    return (reponse.text or "").strip()


# --------------------------------------------------------------------------- #
# Job
# --------------------------------------------------------------------------- #


def executer(config: Config, date_fin: str | None = None, envoyer: bool = True) -> int:
    from zoneinfo import ZoneInfo

    if date_fin:
        fin = date.fromisoformat(date_fin)
        debut = fin - timedelta(days=6)
    else:
        debut, fin = semaine_ecoulee(datetime.now(ZoneInfo(config.fuseau)).date())

    etablissements = entrepot.requete(
        config,
        f"SELECT etablissement_id, nom, email_manager "
        f"FROM {config.table('etablissements')} WHERE actif",
    )
    for etab in etablissements:
        donnees = Donnees(config, etab["etablissement_id"], debut, fin)
        kpi = donnees.kpi(0)
        themes = donnees.themes(0)

        if kpi["nb_analyses"]:
            synthese = rediger(config, etab, donnees, kpi)
        else:
            synthese = "## En bref\nAucun avis commenté cette semaine."

        rapport = {
            "etablissement_id": etab["etablissement_id"],
            "semaine_id": semaine_id(debut),
            "periode_debut": debut.isoformat(),
            "periode_fin": fin.isoformat(),
            **{
                k: kpi[k]
                for k in (
                    "nb_avis",
                    "nb_analyses",
                    "note_moyenne",
                    "nb_positif",
                    "nb_negatif",
                    "nb_neutre",
                    "nb_mixte",
                    "pct_positif",
                    "pct_negatif",
                    "pct_neutre",
                    "pct_mixte",
                    "score_moyen",
                    "nb_actionnables",
                    "tendance",
                )
            },
            "top_negatifs": json.dumps(classement(themes, "negatif"), ensure_ascii=False),
            "top_positifs": json.dumps(classement(themes, "positif"), ensure_ascii=False),
            "synthese": synthese,
            "modele": config.modele_gemini,
            "version_prompt": gemini.VERSION_PROMPT,
            "genere_le": datetime.now(UTC).isoformat(),
            "statut_email": "non_envoye",
        }

        if envoyer and etab.get("email_manager"):
            rapport["statut_email"] = courriel.envoyer_rapport(config, etab, rapport)

        entrepot.fusionner(config, "rapports_hebdo", [rapport], ("etablissement_id", "semaine_id"))
        journal.info(
            "%s %s : %s avis, tendance %s, e-mail %s",
            etab["nom"],
            rapport["semaine_id"],
            kpi["nb_avis"],
            kpi["tendance"],
            rapport["statut_email"],
        )
    return 0
