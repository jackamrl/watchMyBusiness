"""Taxonomies de thèmes par métier.

Gemini ne choisit que parmi ces identifiants : c'est ce qui rend deux semaines
comparables. Un sujet hors taxonomie remonte dans `theme_emergent`, que l'on
relit pour faire évoluer la liste (et donc `VERSION_PROMPT`).
"""

from __future__ import annotations

TAXONOMIES: dict[str, dict[str, str]] = {
    "restaurant": {
        "qualite_cuisine": "Goût, fraîcheur, cuisson, portions des plats",
        "regularite": "Constance de la préparation d'une visite à l'autre",
        "attente": "File d'attente, délai avant d'être servi",
        "service_accueil": "Amabilité, rapidité et attitude du personnel",
        "prix": "Prix, rapport qualité-prix",
        "hygiene": "Propreté de la salle, des tables, des toilettes, sécurité sanitaire",
        "cadre_ambiance": "Décor, bruit, affluence, confort, places assises",
        "emporter": "Vente à emporter, emballage, comptoir",
    },
    "mobilier": {
        "retard_livraison": "Retards ou délais de livraison",
        "colis_endommage": "Colis ou produits arrivés abîmés",
        "sav_injoignable": "Service après-vente difficile à joindre",
        "reactivite_service_client": "Réactivité et efficacité du service client",
        "accueil_boutique": "Accueil et conseil en magasin",
        "qualite_produit": "Qualité, finition et solidité des produits",
    },
}

LIBELLES: dict[str, str] = {
    "qualite_cuisine": "Qualité de la cuisine",
    "regularite": "Régularité",
    "attente": "Attente",
    "service_accueil": "Service et accueil",
    "prix": "Prix",
    "hygiene": "Hygiène",
    "cadre_ambiance": "Cadre et ambiance",
    "emporter": "Vente à emporter",
    "retard_livraison": "Retards de livraison",
    "colis_endommage": "Colis endommagés",
    "sav_injoignable": "SAV injoignable",
    "reactivite_service_client": "Réactivité du service client",
    "accueil_boutique": "Accueil en boutique",
    "qualite_produit": "Qualité des produits",
}


def themes(metier: str) -> dict[str, str]:
    try:
        return TAXONOMIES[metier]
    except KeyError as erreur:
        raise ValueError(f"métier inconnu : {metier}") from erreur


def libelle(theme_id: str) -> str:
    return LIBELLES.get(theme_id, theme_id)
