"""Métriques codées à la main (numpy) : exactitude, F1 macro, matrice de confusion,
kappa de Cohen. Aucune dépendance à scikit-learn."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def matrice_confusion(vrais: Sequence[str], predits: Sequence[str],
                      classes: Sequence[str]) -> np.ndarray:
    """Ligne = vraie classe, colonne = classe prédite."""
    index = {c: i for i, c in enumerate(classes)}
    m = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for v, p in zip(vrais, predits, strict=True):
        if v in index and p in index:
            m[index[v], index[p]] += 1
    return m


def exactitude(vrais: Sequence[str], predits: Sequence[str]) -> float:
    if not vrais:
        return 0.0
    return float(np.mean([v == p for v, p in zip(vrais, predits, strict=True)]))


def f1_par_classe(vrais: Sequence[str], predits: Sequence[str],
                  classes: Sequence[str]) -> dict[str, float]:
    m = matrice_confusion(vrais, predits, classes)
    resultats = {}
    for i, c in enumerate(classes):
        vp = m[i, i]
        precision = vp / m[:, i].sum() if m[:, i].sum() else 0.0
        rappel = vp / m[i, :].sum() if m[i, :].sum() else 0.0
        resultats[c] = (2 * precision * rappel / (precision + rappel)
                        if precision + rappel else 0.0)
    return resultats


def f1_macro(vrais: Sequence[str], predits: Sequence[str], classes: Sequence[str]) -> float:
    """Moyenne des F1 des classes PRÉSENTES dans les vraies étiquettes : une classe
    absente du jeu de test ne doit pas faire baisser artificiellement le score."""
    presentes = [c for c in classes if c in set(vrais)]
    if not presentes:
        return 0.0
    f1 = f1_par_classe(vrais, predits, classes)
    return float(np.mean([f1[c] for c in presentes]))


def kappa_cohen(annotateur_a: Sequence[str], annotateur_b: Sequence[str]) -> float:
    """Accord entre deux annotateurs, corrigé du hasard. 1 = accord parfait,
    0 = pas mieux que le hasard. Repères usuels : > 0,6 bon, > 0,8 très bon."""
    if not annotateur_a:
        return 0.0
    classes = sorted(set(annotateur_a) | set(annotateur_b))
    m = matrice_confusion(annotateur_a, annotateur_b, classes).astype(float)
    n = m.sum()
    observe = np.trace(m) / n
    attendu = float((m.sum(axis=1) * m.sum(axis=0)).sum() / (n * n))
    if attendu == 1.0:
        return 1.0
    return float((observe - attendu) / (1 - attendu))


def f1_ensembles(vrais: Sequence[set], predits: Sequence[set]) -> float:
    """F1 « micro » sur des ensembles, par exemple les paires (thème, polarité)
    évoquées dans chaque avis : précision = part des paires prédites qui sont justes,
    rappel = part des vraies paires retrouvées."""
    justes = sum(len(v & p) for v, p in zip(vrais, predits, strict=True))
    nb_predits = sum(len(p) for p in predits)
    nb_vrais = sum(len(v) for v in vrais)
    precision = justes / nb_predits if nb_predits else 0.0
    rappel = justes / nb_vrais if nb_vrais else 0.0
    return 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
