"""Classifieur bayésien naïf multinomial codé avec numpy : le PLANCHER.

Tout modèle plus sophistiqué doit faire mieux que lui sur le même jeu de test.
Un classifieur par sortie : sentiment, humeur, et un par thème (polarité).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

import numpy as np

_MOT = re.compile(r"[^\W\d_]+", re.UNICODE)


def mots(texte: str) -> list[str]:
    texte = unicodedata.normalize("NFC", texte.lower())
    return _MOT.findall(texte)


class BayesNaif:
    def __init__(self, lissage: float = 1.0, taille_vocab: int = 20_000):
        self.lissage = lissage
        self.taille_vocab = taille_vocab
        self.vocab: dict[str, int] = {}
        self.classes: list[str] = []
        self.log_priors: np.ndarray | None = None
        self.log_vraisemblances: np.ndarray | None = None

    def _ids(self, texte: str) -> np.ndarray:
        return np.array([self.vocab[m] for m in mots(texte) if m in self.vocab], dtype=np.int64)

    def entrainer(self, textes: Sequence[str], etiquettes: Sequence[str]) -> BayesNaif:
        compte = Counter(m for t in textes for m in mots(t))
        self.vocab = {m: i for i, (m, _) in enumerate(compte.most_common(self.taille_vocab))}
        self.classes = sorted(set(etiquettes))
        y = np.array([self.classes.index(e) for e in etiquettes])
        nb_classes = len(self.classes)
        self.log_priors = np.log(np.bincount(y, minlength=nb_classes) / len(y))
        # comptes[c, m] = occurrences du mot m dans la classe c, + lissage de Laplace
        comptes = np.full((nb_classes, len(self.vocab)), self.lissage)
        for texte, c in zip(textes, y, strict=True):
            np.add.at(comptes[c], self._ids(texte), 1)
        self.log_vraisemblances = np.log(comptes / comptes.sum(axis=1, keepdims=True))
        return self

    def predire(self, textes: Sequence[str]) -> list[str]:
        resultats = []
        for texte in textes:
            scores = self.log_priors + self.log_vraisemblances[:, self._ids(texte)].sum(axis=1)
            resultats.append(self.classes[int(scores.argmax())])
        return resultats

    def etat(self) -> dict:
        return {"vocab": self.vocab, "classes": self.classes,
                "log_priors": self.log_priors.tolist(),
                "log_vraisemblances": self.log_vraisemblances.tolist()}

    @classmethod
    def depuis_etat(cls, etat: dict) -> BayesNaif:
        b = cls()
        b.vocab, b.classes = etat["vocab"], etat["classes"]
        b.log_priors = np.array(etat["log_priors"])
        b.log_vraisemblances = np.array(etat["log_vraisemblances"])
        return b


class BayesAvis:
    """Un BayesNaif par sortie, entraîné uniquement sur les exemples étiquetés."""

    def __init__(self, themes: Sequence[str]):
        self.themes = list(themes)
        self.modeles: dict[str, BayesNaif] = {}

    def entrainer(self, lignes: list[dict]) -> BayesAvis:
        cibles = {"sentiment": lambda e: e.get("sentiment"),
                  "humeur": lambda e: e.get("humeur")}
        for t in self.themes:
            cibles[f"theme:{t}"] = (lambda th: lambda e: (
                None if e.get("themes") is None else e["themes"].get(th, "absent")))(t)
        for nom, extraire in cibles.items():
            couples = [(l["texte"], extraire(l["etiquette"])) for l in lignes
                       if l.get("etiquette") and extraire(l["etiquette"])]
            if len({e for _, e in couples}) >= 2:
                textes, etiquettes = zip(*couples, strict=True)
                self.modeles[nom] = BayesNaif().entrainer(textes, etiquettes)
        return self

    def predire(self, textes: list[str]) -> list[dict]:
        sorties = {nom: m.predire(textes) for nom, m in self.modeles.items()}
        resultats = []
        for k in range(len(textes)):
            themes = {t: sorties[f"theme:{t}"][k] for t in self.themes
                      if f"theme:{t}" in sorties and sorties[f"theme:{t}"][k] != "absent"}
            resultats.append({
                "sentiment": sorties.get("sentiment", [None] * len(textes))[k],
                "humeur": sorties.get("humeur", [None] * len(textes))[k],
                "themes": themes,
            })
        return resultats

    def sauver(self, chemin: str | Path) -> None:
        Path(chemin).write_text(json.dumps(
            {"themes": self.themes, "modeles": {n: m.etat() for n, m in self.modeles.items()}}),
            encoding="utf-8")

    @classmethod
    def charger(cls, chemin: str | Path) -> BayesAvis:
        donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
        b = cls(donnees["themes"])
        b.modeles = {n: BayesNaif.depuis_etat(e) for n, e in donnees["modeles"].items()}
        return b
