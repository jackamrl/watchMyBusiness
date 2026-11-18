"""Prédiction en production avec le modèle maison.

Le format de sortie est celui de `gemini.valider` (sentiment, score, thèmes,
actionnable…) complété par `humeur` et `confiance` : le job d'analyse et
BigQuery traitent les deux moteurs de la même façon.

Un « paquet modèle » est un dossier contenant :
    tokenizer.json    tokenizer BPE
    modele.pt         poids + configuration + méta (version, métier, seuil)
    modele_themes.pt  (facultatif) spécialiste des thèmes, même tokenizer
Il est produit par `python -m nlp finetune` (et `python -m nlp combiner` pour le
spécialiste) et déposé tel quel sur Cloud Storage.

Pourquoi un spécialiste : entraîné avec une perte des thèmes pondérée, un modèle
repère bien mieux les thèmes rares (attente, cadre, prix) mais perd un peu en
sentiment et en humeur. Le modèle principal garde donc sentiment, humeur et
confiance ; le spécialiste ne fournit que les thèmes.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from . import etiquettes

journal = logging.getLogger(__name__)

FICHIERS = ("tokenizer.json", "modele.pt")
FACULTATIFS = ("modele_themes.pt", "seuils_themes.json")


def polarite_theme(probas: list[float], seuil: float | None = None) -> str:
    """Probabilités [absent, positif, negatif, neutre] → polarité.
    Sans seuil : argmax. Avec seuil : présent dès que P(absent) < seuil, et la
    polarité est alors la plus probable parmi positif / negatif / neutre."""
    if seuil is None:
        return etiquettes.POLARITES[max(range(len(probas)), key=probas.__getitem__)]
    if probas[0] >= seuil:
        return "absent"
    return etiquettes.POLARITES[max(range(1, len(probas)), key=probas.__getitem__)]


def telecharger(uri: str) -> Path:
    """`gs://bucket/nlp-v1/` → dossier local ; un chemin local est renvoyé tel quel."""
    if not uri.startswith("gs://"):
        return Path(uri)
    from google.cloud import storage

    bucket_nom, _, prefixe = uri[5:].partition("/")
    bucket = storage.Client().bucket(bucket_nom)
    dossier = Path(tempfile.mkdtemp(prefix="modele-"))
    for nom in FICHIERS:
        bucket.blob(f"{prefixe.rstrip('/')}/{nom}").download_to_filename(dossier / nom)
    for nom in FACULTATIFS:
        blob = bucket.blob(f"{prefixe.rstrip('/')}/{nom}")
        if blob.exists():
            blob.download_to_filename(dossier / nom)
    return dossier


class ModeleMaison:
    def __init__(self, dossier: str | Path, appareil: str = "cpu"):
        import torch

        from .modele import ModeleAvis
        from .tokenizer import TokenizerBPE

        dossier = Path(dossier)
        self.torch = torch
        self.tokenizer = TokenizerBPE.charger(dossier / "tokenizer.json")
        self.modele, self.meta = ModeleAvis.charger(dossier / "modele.pt", appareil)
        self.appareil = appareil
        self.metier = self.meta.get("metier", "restaurant")
        self.themes = etiquettes.themes(self.metier)
        self.version = self.meta.get("version", "nlp-dev")
        self.seuil = float(self.meta.get("seuil_confiance", 0.6))
        # Têtes réellement entraînées (paquets anciens sans l'information : toutes).
        self.tetes = set(self.meta.get("tetes_entrainees", ["sentiment", "humeur", "themes"]))
        # Thèmes réellement appris (les notes Google n'en couvrent que 3 sur 8).
        self.themes_appris = set(self.meta.get("themes_entraines", self.themes))
        # Spécialiste des thèmes (facultatif).
        self.modele_themes = None
        if (dossier / "modele_themes.pt").exists():
            self.modele_themes, meta_th = ModeleAvis.charger(dossier / "modele_themes.pt",
                                                             appareil)
            self.themes_appris = set(meta_th.get("themes_entraines", self.themes))
            self.tetes.add("themes")
            self.version = f"{self.version}+{meta_th.get('version', 'themes')}"
        # Seuils de détection par thème, calibrés sur la validation (facultatif) :
        # thème présent si P(absent) < seuil, au lieu de l'argmax.
        self.seuils_themes: dict[str, float] = {}
        if (dossier / "seuils_themes.json").exists():
            import json

            self.seuils_themes = json.loads((dossier / "seuils_themes.json").read_text())

    @classmethod
    def depuis_uri(cls, uri: str) -> ModeleMaison:
        return cls(telecharger(uri))

    def _lot(self, textes: list[str]):
        torch = self.torch
        contexte = self.modele.cfg.contexte
        sequences = [self.tokenizer.encoder(t, bos=True)[:contexte] for t in textes]
        longueur = max(len(s) for s in sequences)
        ids = torch.zeros((len(textes), longueur), dtype=torch.long)
        masque = torch.zeros((len(textes), longueur), dtype=torch.bool)
        for i, s in enumerate(sequences):
            ids[i, : len(s)] = torch.tensor(s)
            masque[i, : len(s)] = True
        return ids.to(self.appareil), masque.to(self.appareil)

    def probas_themes(self, textes: list[str]) -> list[list[list[float]]]:
        """[avis][thème][polarité] : probabilités brutes, pour calibrer les seuils."""
        torch = self.torch
        sortie = []
        for i in range(0, len(textes), 64):
            ids, masque = self._lot(textes[i:i + 64])
            with torch.no_grad():
                m = self.modele_themes or self.modele
                sortie += torch.softmax(m.classer(ids, masque)["themes"].float(),
                                        dim=-1).cpu().tolist()
        return sortie

    def predire_lot(self, textes: list[str]) -> list[dict]:
        torch = self.torch
        if not textes:
            return []
        ids, masque = self._lot(textes)
        with torch.no_grad():
            sorties = self.modele.classer(ids, masque)
            logits_themes = (self.modele_themes.classer(ids, masque)["themes"]
                             if self.modele_themes is not None else sorties["themes"])
        p_sent = torch.softmax(sorties["sentiment"].float(), dim=-1).cpu()
        p_hum = torch.softmax(sorties["humeur"].float(), dim=-1).cpu()
        p_the = torch.softmax(logits_themes.float(), dim=-1).cpu()

        i_pos = etiquettes.SENTIMENTS.index("POSITIF")
        i_neg = etiquettes.SENTIMENTS.index("NEGATIF")
        resultats = []
        for k in range(len(textes)):
            confiance, i_sent = p_sent[k].max(dim=-1)
            themes = []
            for j, theme in enumerate(self.themes):
                polarite = polarite_theme(p_the[k, j].tolist(), self.seuils_themes.get(theme))
                if ("themes" in self.tetes and theme in self.themes_appris
                        and polarite != "absent"):
                    themes.append({"theme": theme, "polarite": polarite, "extrait": ""})
            resultats.append({
                "sentiment": etiquettes.SENTIMENTS[int(i_sent)],
                # score « à la Gemini » : P(positif) − P(négatif), entre −1 et +1
                "score": round(float(p_sent[k, i_pos] - p_sent[k, i_neg]), 4),
                "confiance": round(float(confiance), 4),
                "humeur": (etiquettes.HUMEURS[int(p_hum[k].argmax())]
                           if "humeur" in self.tetes else None),
                "themes": themes,
                "theme_emergent": None,
                "actionnable": any(t["polarite"] == "negatif" for t in themes),
                "resume": "",
            })
        return resultats

    def predire(self, texte: str) -> dict:
        return self.predire_lot([texte])[0]
