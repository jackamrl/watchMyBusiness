"""Analyse d'un avis par Gemini, en sortie structurée.

Ce n'est pas un agent : une entrée, une sortie JSON imposée par schéma,
température 0. C'est ce qui rend le résultat reproductible et stockable.
"""

from __future__ import annotations

import json
from typing import Any

from . import taxonomie

# À incrémenter dès que le prompt ou la taxonomie change : chaque analyse
# stockée porte sa version, ce qui permet de réanalyser et de comparer.
VERSION_PROMPT = "v1"

SENTIMENTS = ("POSITIF", "NEGATIF", "NEUTRE", "MIXTE")


def schema(metier: str) -> dict:
    return {
        "type": "OBJECT",
        "properties": {
            "sentiment": {"type": "STRING", "enum": list(SENTIMENTS)},
            "score": {
                "type": "NUMBER",
                "description": "-1 très négatif, 0 neutre, +1 très positif",
            },
            "themes": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "theme": {"type": "STRING", "enum": list(taxonomie.themes(metier))},
                        "polarite": {"type": "STRING", "enum": ["positif", "negatif", "neutre"]},
                        "extrait": {
                            "type": "STRING",
                            "description": (
                                "citation exacte et courte de l'avis justifiant le thème"
                            ),
                        },
                    },
                    "required": ["theme", "polarite", "extrait"],
                },
            },
            "theme_emergent": {
                "type": "STRING",
                "nullable": True,
                "description": "sujet important absent de la taxonomie, sinon null",
            },
            "actionnable": {
                "type": "BOOLEAN",
                "description": "l'avis contient un problème concret que le gérant peut corriger",
            },
            "resume": {"type": "STRING", "description": "une phrase en français"},
        },
        "required": ["sentiment", "score", "themes", "actionnable", "resume"],
    }


def consigne(metier: str, nom: str) -> str:
    liste = "\n".join(f"- {cle} : {desc}" for cle, desc in taxonomie.themes(metier).items())
    return f"""Tu analyses un avis client Google Maps de « {nom} » (métier : {metier}).
Réponds uniquement selon le schéma JSON fourni.

Règles :
- sentiment : MIXTE si l'avis contient à la fois un vrai point positif et un vrai point négatif.
- Le sentiment se juge sur le texte ; la note en étoiles n'est qu'un indice.
- Gère la négation et l'ironie (« pas déçu » est positif).
- themes : uniquement parmi la liste ci-dessous, chacun avec sa propre polarité
  et un extrait cité mot pour mot depuis l'avis (langue d'origine).
- N'invente aucun thème qui n'est pas exprimé dans l'avis.
- resume : une phrase en français, quelle que soit la langue de l'avis.

Thèmes autorisés :
{liste}"""


def client(projet: str, region: str):
    from google import genai

    return genai.Client(vertexai=True, project=projet, location=region)


def analyser(
    client_genai: Any, modele: str, metier: str, nom: str, texte: str, note: int | None
) -> dict:
    from google.genai import types

    contenu = f"Note : {note if note is not None else 'inconnue'}/5\nAvis :\n{texte}"
    reponse = client_genai.models.generate_content(
        model=modele,
        contents=contenu,
        config=types.GenerateContentConfig(
            system_instruction=consigne(metier, nom),
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema(metier),
        ),
    )
    return valider(json.loads(reponse.text), metier)


def valider(sortie: dict, metier: str) -> dict:
    """Défense en profondeur : le schéma contraint Gemini, on revérifie quand même."""
    autorises = set(taxonomie.themes(metier))
    sentiment = str(sortie.get("sentiment", "NEUTRE")).upper()
    if sentiment not in SENTIMENTS:
        sentiment = "NEUTRE"
    score = max(-1.0, min(1.0, float(sortie.get("score") or 0.0)))

    themes, vus = [], set()
    for theme in sortie.get("themes") or []:
        identifiant = theme.get("theme")
        if identifiant not in autorises or identifiant in vus:
            continue
        vus.add(identifiant)
        polarite = theme.get("polarite")
        themes.append(
            {
                "theme": identifiant,
                "polarite": polarite if polarite in ("positif", "negatif", "neutre") else "neutre",
                "extrait": str(theme.get("extrait") or "")[:300],
            }
        )

    emergent = sortie.get("theme_emergent")
    return {
        "sentiment": sentiment,
        "score": score,
        "themes": themes,
        "theme_emergent": str(emergent)[:120] if emergent else None,
        "actionnable": bool(sortie.get("actionnable")),
        "resume": str(sortie.get("resume") or "")[:400],
    }
