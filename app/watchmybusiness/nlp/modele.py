"""Transformer de type GPT codé à la main (PyTorch, sans bibliothèque de modèles).

    jetons → embeddings (jeton + position) → N blocs [attention causale, MLP] → LayerNorm
           ├─ tête « langue »  : prédire le jeton suivant (pré-entraînement, rédaction)
           └─ têtes « avis »   : sentiment, humeur, polarité de chaque thème

L'attention est écrite explicitement (produits matriciels + masque causal) plutôt
qu'avec `nn.MultiheadAttention`, pour que chaque étape soit visible et expliquable.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

import torch
from torch import nn
from torch.nn import functional as F

from . import etiquettes

# (couches, dimension, têtes) — ≈ 7 M, 22 M et 50 M de paramètres avec 16 000 jetons.
TAILLES = {"XS": (2, 128, 4), "S": (4, 256, 4), "M": (6, 448, 7), "L": (8, 640, 10)}


@dataclass
class ConfigModele:
    taille_vocab: int
    contexte: int = 256
    couches: int = 4
    dimension: int = 256
    tetes: int = 4
    dropout: float = 0.1
    nb_themes: int = 8

    @classmethod
    def depuis_taille(cls, taille: str, taille_vocab: int, **autres) -> ConfigModele:
        couches, dimension, tetes = TAILLES[taille]
        return cls(taille_vocab=taille_vocab, couches=couches, dimension=dimension,
                   tetes=tetes, **autres)


class AttentionCausale(nn.Module):
    def __init__(self, cfg: ConfigModele):
        super().__init__()
        assert cfg.dimension % cfg.tetes == 0, "dimension doit être divisible par tetes"
        self.tetes = cfg.tetes
        self.qkv = nn.Linear(cfg.dimension, 3 * cfg.dimension)
        self.sortie = nn.Linear(cfg.dimension, cfg.dimension)
        self.dropout = nn.Dropout(cfg.dropout)
        masque = torch.tril(torch.ones(cfg.contexte, cfg.contexte, dtype=torch.bool))
        self.register_buffer("causal", masque.view(1, 1, cfg.contexte, cfg.contexte),
                             persistent=False)

    def forward(self, x: torch.Tensor, masque_pad: torch.Tensor | None) -> torch.Tensor:
        b, t, d = x.shape
        q, k, v = self.qkv(x).split(d, dim=2)
        # (b, t, d) → (b, têtes, t, d/têtes)
        q, k, v = (z.view(b, t, self.tetes, d // self.tetes).transpose(1, 2) for z in (q, k, v))
        scores = (q @ k.transpose(-2, -1)) / math.sqrt(d // self.tetes)
        autorise = self.causal[:, :, :t, :t]
        if masque_pad is not None:  # un jeton ne regarde jamais le remplissage
            autorise = autorise & masque_pad[:, None, None, :t]
        scores = scores.masked_fill(~autorise, torch.finfo(scores.dtype).min)
        poids = self.dropout(F.softmax(scores, dim=-1))
        y = (poids @ v).transpose(1, 2).contiguous().view(b, t, d)
        return self.dropout(self.sortie(y))


class Bloc(nn.Module):
    def __init__(self, cfg: ConfigModele):
        super().__init__()
        self.ln1 = nn.LayerNorm(cfg.dimension)
        self.attention = AttentionCausale(cfg)
        self.ln2 = nn.LayerNorm(cfg.dimension)
        self.mlp = nn.Sequential(
            nn.Linear(cfg.dimension, 4 * cfg.dimension),
            nn.GELU(),
            nn.Linear(4 * cfg.dimension, cfg.dimension),
            nn.Dropout(cfg.dropout),
        )

    def forward(self, x: torch.Tensor, masque_pad: torch.Tensor | None) -> torch.Tensor:
        x = x + self.attention(self.ln1(x), masque_pad)  # connexions résiduelles
        return x + self.mlp(self.ln2(x))


class ModeleAvis(nn.Module):
    def __init__(self, cfg: ConfigModele):
        super().__init__()
        self.cfg = cfg
        self.jetons = nn.Embedding(cfg.taille_vocab, cfg.dimension)
        self.positions = nn.Embedding(cfg.contexte, cfg.dimension)
        self.dropout = nn.Dropout(cfg.dropout)
        self.blocs = nn.ModuleList(Bloc(cfg) for _ in range(cfg.couches))
        self.ln_finale = nn.LayerNorm(cfg.dimension)
        # Tête « langue » liée aux embeddings (moins de paramètres, classique en GPT).
        self.tete_langue = nn.Linear(cfg.dimension, cfg.taille_vocab, bias=False)
        self.tete_langue.weight = self.jetons.weight
        self.tete_sentiment = nn.Linear(cfg.dimension, len(etiquettes.SENTIMENTS))
        self.tete_humeur = nn.Linear(cfg.dimension, len(etiquettes.HUMEURS))
        self.tete_themes = nn.Linear(cfg.dimension, cfg.nb_themes * len(etiquettes.POLARITES))
        self.apply(self._initialiser)

    @staticmethod
    def _initialiser(module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def nb_parametres(self) -> int:
        return sum(p.numel() for p in self.parameters())

    def encoder(self, ids: torch.Tensor, masque_pad: torch.Tensor | None = None) -> torch.Tensor:
        t = ids.shape[1]
        if t > self.cfg.contexte:
            raise ValueError(f"séquence de {t} jetons > contexte {self.cfg.contexte}")
        pos = torch.arange(t, device=ids.device)
        x = self.dropout(self.jetons(ids) + self.positions(pos))
        for bloc in self.blocs:
            x = bloc(x, masque_pad)
        return self.ln_finale(x)

    def langue(self, ids: torch.Tensor, masque_pad: torch.Tensor | None = None) -> torch.Tensor:
        """Logits du jeton suivant, pour chaque position."""
        return self.tete_langue(self.encoder(ids, masque_pad))

    def classer(self, ids: torch.Tensor, masque_pad: torch.Tensor) -> dict[str, torch.Tensor]:
        """Logits des têtes « avis ». Modèle causal : seul le DERNIER vrai jeton a vu
        tout l'avis, c'est donc sa représentation qu'on utilise."""
        h = self.encoder(ids, masque_pad)
        dernier = masque_pad.long().sum(dim=1).clamp(min=1) - 1
        resume = h[torch.arange(h.shape[0], device=h.device), dernier]
        return {
            "sentiment": self.tete_sentiment(resume),
            "humeur": self.tete_humeur(resume),
            "themes": self.tete_themes(resume).view(-1, self.cfg.nb_themes,
                                                    len(etiquettes.POLARITES)),
        }

    @torch.no_grad()
    def generer(self, ids: torch.Tensor, nb_jetons: int, temperature: float = 0.0,
                fin: int | None = None) -> torch.Tensor:
        """Génération jeton par jeton (rédaction). temperature 0 = toujours le plus probable."""
        for _ in range(nb_jetons):
            contexte = ids[:, -self.cfg.contexte:]
            logits = self.langue(contexte)[:, -1, :]
            if temperature <= 0:
                suivant = logits.argmax(dim=-1, keepdim=True)
            else:
                suivant = torch.multinomial(F.softmax(logits / temperature, dim=-1), 1)
            ids = torch.cat([ids, suivant], dim=1)
            if fin is not None and bool((suivant == fin).all()):
                break
        return ids

    # ------------------------------------------------------------------ #
    def sauver(self, chemin, meta: dict | None = None) -> None:
        torch.save({"config": asdict(self.cfg), "poids": self.state_dict(), "meta": meta or {}},
                   chemin)

    @classmethod
    def charger(cls, chemin, appareil: str = "cpu") -> tuple[ModeleAvis, dict]:
        donnees = torch.load(chemin, map_location=appareil, weights_only=False)
        modele = cls(ConfigModele(**donnees["config"]))
        modele.load_state_dict(donnees["poids"])
        return modele.to(appareil).eval(), donnees.get("meta", {})
