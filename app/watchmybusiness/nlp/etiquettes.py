"""Espaces d'étiquettes du modèle maison, partagés par l'entraînement et la production.

Les identifiants de thèmes viennent de `taxonomie.py` : le modèle maison et Gemini
parlent exactement le même vocabulaire, ce qui rend la comparaison possible.
"""

from __future__ import annotations

from .. import taxonomie

SENTIMENTS = ("POSITIF", "NEGATIF", "NEUTRE", "MIXTE")
HUMEURS = ("joie", "satisfaction", "deception", "frustration", "colere", "neutre")
# Pour chaque thème de la taxonomie, le modèle prédit l'une de ces 4 valeurs.
POLARITES = ("absent", "positif", "negatif", "neutre")

IGNORER = -100  # valeur d'étiquette ignorée par les pertes (étiquette manquante)


def themes(metier: str = "restaurant") -> tuple[str, ...]:
    return tuple(taxonomie.themes(metier))


def depuis_etoiles(note: int | None) -> str | None:
    """Supervision faible : 1-2 étoiles → NEGATIF, 4-5 → POSITIF, 3 → ambigu (None)."""
    if note is None:
        return None
    if note <= 2:
        return "NEGATIF"
    if note >= 4:
        return "POSITIF"
    return None


# Notes détaillées Google (Cuisine / Service / Ambiance) → thèmes de la taxonomie.
NOTES_VERS_THEMES = {"Cuisine": "qualite_cuisine", "Food": "qualite_cuisine",
                     "Service": "service_accueil",
                     "Ambiance": "cadre_ambiance", "Atmosphere": "cadre_ambiance",
                     "Value": "prix"}  # TripAdvisor : rapport qualité-prix


def themes_depuis_notes(notes: dict | None) -> dict[str, str]:
    """Supervision faible des thèmes : note ≤ 2 → negatif, 3 → neutre, ≥ 4 → positif.
    Seuls ces thèmes reçoivent une étiquette ; les autres restent inconnus."""
    resultat = {}
    for cle, valeur in (notes or {}).items():
        theme = NOTES_VERS_THEMES.get(cle)
        try:
            n = int(valeur)
        except (TypeError, ValueError):
            continue
        if theme:
            resultat[theme] = "negatif" if n <= 2 else ("neutre" if n == 3 else "positif")
    return resultat


def encoder(etiquette: dict | None, metier: str = "restaurant") -> dict[str, object]:
    """Étiquette lisible → indices pour les pertes.

    `etiquette` = {"sentiment": "MIXTE", "humeur": "frustration",
                   "themes": {"attente": "negatif", ...}}
    Toute partie absente devient IGNORER (la perte correspondante est sautée).
    """
    etiquette = etiquette or {}
    sentiment = etiquette.get("sentiment")
    humeur = etiquette.get("humeur")
    liste_themes = themes(metier)
    themes_etiq = etiquette.get("themes")
    if themes_etiq is None:
        indices_themes = [IGNORER] * len(liste_themes)
    else:
        indices_themes = []
        for theme in liste_themes:
            polarite = themes_etiq.get(theme, "absent")
            indices_themes.append(POLARITES.index(polarite) if polarite in POLARITES else IGNORER)
    return {
        "sentiment": SENTIMENTS.index(sentiment) if sentiment in SENTIMENTS else IGNORER,
        "humeur": HUMEURS.index(humeur) if humeur in HUMEURS else IGNORER,
        "themes": indices_themes,
    }


def depuis_analyse(analyse: dict) -> dict:
    """Sortie Gemini (format `gemini.valider`) → étiquette lisible du modèle maison."""
    return {
        "sentiment": analyse.get("sentiment"),
        "humeur": analyse.get("humeur"),
        "themes": {t["theme"]: t["polarite"] for t in analyse.get("themes") or []},
    }
