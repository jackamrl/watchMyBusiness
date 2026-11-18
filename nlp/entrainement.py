"""Entraînement du modèle maison : tokenizer, pré-entraînement, spécialisation.

Prévu pour une RTX 3070 Ti Laptop (8 Go, CUDA, précision mixte) ; fonctionne aussi
sur Mac (MPS) et sur CPU pour les essais.

    1. tokenizer  : apprendre le BPE sur le corpus
    2. pretrain   : prédire le jeton suivant (français général, puis avis)
    3. finetune   : têtes sentiment / humeur / thèmes
                    --etape etoiles    : supervision faible par les étoiles
                    --etape etiquettes : étiquettes Gemini (ou humaines)
"""

from __future__ import annotations

import contextlib
import logging
import math
import shutil
import time
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from watchmybusiness.nlp import etiquettes
from watchmybusiness.nlp.modele import ConfigModele, ModeleAvis
from watchmybusiness.nlp.tokenizer import EOS, PAD, TokenizerBPE

from . import metriques
from .donnees import lire_jsonl

journal = logging.getLogger(__name__)
IGN = etiquettes.IGNORER


# --------------------------------------------------------------------------- #
# Matériel
# --------------------------------------------------------------------------- #
def appareil() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def precision_mixte(dev: str):
    """Sur GPU NVIDIA : bf16 si la carte le permet (RTX 30xx oui), sinon fp16 avec
    mise à l'échelle des gradients. Ailleurs : précision normale (fp32)."""
    if dev == "cuda":
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        scaler = torch.amp.GradScaler("cuda", enabled=dtype == torch.float16)
        return (lambda: torch.autocast("cuda", dtype=dtype)), scaler
    return contextlib.nullcontext, torch.amp.GradScaler("cpu", enabled=False)


def optimiseur(modele: ModeleAvis, lr: float) -> torch.optim.Optimizer:
    """AdamW, avec décroissance des poids seulement sur les matrices (pas sur les
    biais ni les LayerNorm)."""
    decay = [p for p in modele.parameters() if p.requires_grad and p.dim() >= 2]
    sans = [p for p in modele.parameters() if p.requires_grad and p.dim() < 2]
    return torch.optim.AdamW([{"params": decay, "weight_decay": 0.1},
                              {"params": sans, "weight_decay": 0.0}],
                             lr=lr, betas=(0.9, 0.95))


def taux(pas: int, total: int, lr: float, echauffement: int) -> float:
    """Échauffement linéaire puis décroissance en cosinus jusqu'à 10 % de lr."""
    if pas < echauffement:
        return lr * (pas + 1) / echauffement
    avancement = (pas - echauffement) / max(1, total - echauffement)
    return lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, avancement))))


# --------------------------------------------------------------------------- #
# 1. Tokenizer
# --------------------------------------------------------------------------- #
def echantillon_lignes(corpus: str | Path, n: int, graine: int = 0) -> list[str]:
    """Tirage uniforme de n lignes dans tout le fichier, en une passe (échantillonnage
    par réservoir) : le tokenizer voit toutes les sources et toutes les langues, pas
    seulement le début du corpus."""
    rng = np.random.default_rng(graine)
    reservoir: list[str] = []
    with open(corpus, encoding="utf-8") as f:
        for i, ligne in enumerate(f):
            if i < n:
                reservoir.append(ligne)
            else:
                j = rng.integers(0, i + 1)
                if j < n:
                    reservoir[j] = ligne
    return reservoir


def entrainer_tokenizer(corpus: str | Path, sortie: str | Path, taille: int = 16000,
                        max_lignes: int = 300_000) -> TokenizerBPE:
    def lignes():
        return echantillon_lignes(corpus, max_lignes)

    debut = time.time()
    tok = TokenizerBPE.entrainer(lignes(), taille_vocab=taille)
    Path(sortie).parent.mkdir(parents=True, exist_ok=True)
    tok.sauver(sortie)
    journal.info("tokenizer : %d jetons, %d fusions, %.0f s", len(tok), len(tok.fusions),
                 time.time() - debut)
    return tok


# --------------------------------------------------------------------------- #
# 2. Pré-entraînement (prédire le jeton suivant)
# --------------------------------------------------------------------------- #
def encoder_corpus(corpus: str | Path, tok: TokenizerBPE, tokenizer: str | Path) -> np.ndarray:
    """Tout le corpus en un seul flux de jetons (documents séparés par <eos>),
    mis en cache à côté du corpus."""
    corpus = Path(corpus)
    cache = corpus.with_suffix(f".{Path(tokenizer).stem}.npy")
    if cache.exists() and cache.stat().st_mtime > max(corpus.stat().st_mtime,
                                                       Path(tokenizer).stat().st_mtime):
        return np.load(cache, mmap_mode="r")
    ids: list[int] = []
    with open(corpus, encoding="utf-8") as f:
        for ligne in f:
            ids.extend(tok.encoder(ligne))
            ids.append(EOS)
    flux = np.array(ids, dtype=np.uint16 if len(tok) < 65_535 else np.int32)
    np.save(cache, flux)
    journal.info("corpus encodé : %d jetons → %s", len(flux), cache.name)
    return flux


def pretrain(corpus: str | Path, tokenizer: str | Path, sortie: str | Path,
             taille: str = "S", contexte: int = 256, pas: int = 5000, lot: int = 32,
             accumulation: int = 1, lr: float = 6e-4, eval_tous: int = 250,
             init: str | Path | None = None, graine: int = 0) -> dict:
    torch.manual_seed(graine)
    rng = np.random.default_rng(graine)
    dev = appareil()
    tok = TokenizerBPE.charger(tokenizer)
    flux = encoder_corpus(corpus, tok, tokenizer)
    coupe = int(len(flux) * 0.99)
    train, val = flux[:coupe], flux[coupe:]
    if len(train) < contexte + 2:
        raise SystemExit(f"Corpus trop petit ({len(flux)} jetons) pour un contexte de {contexte}.")
    if len(val) < contexte + 2:
        val = train

    if init:
        modele, _ = ModeleAvis.charger(init, dev)
    else:
        modele = ModeleAvis(ConfigModele.depuis_taille(taille, len(tok), contexte=contexte)).to(dev)
    modele.train()
    journal.info("pré-entraînement sur %s : %.1f M paramètres, %d jetons", dev,
                 modele.nb_parametres() / 1e6, len(train))
    opt = optimiseur(modele, lr)
    autocast, scaler = precision_mixte(dev)

    def lot_aleatoire(donnees: np.ndarray):
        debuts = rng.integers(0, len(donnees) - contexte - 1, lot)
        x = np.stack([donnees[i:i + contexte] for i in debuts]).astype(np.int64)
        y = np.stack([donnees[i + 1:i + 1 + contexte] for i in debuts]).astype(np.int64)
        return torch.from_numpy(x).to(dev), torch.from_numpy(y).to(dev)

    @torch.no_grad()
    def perte_val(nb: int = 20) -> float:
        modele.eval()
        pertes = []
        for _ in range(nb):
            x, y = lot_aleatoire(val)
            with autocast():
                logits = modele.langue(x)
            pertes.append(F.cross_entropy(logits.float().view(-1, logits.size(-1)),
                                          y.view(-1)).item())
        modele.train()
        return float(np.mean(pertes))

    meilleure, debut, historique = float("inf"), time.time(), []
    echauffement = max(1, min(500, pas // 20))
    for etape in range(pas):
        for groupe in opt.param_groups:
            groupe["lr"] = taux(etape, pas, lr, echauffement)
        for _ in range(accumulation):
            x, y = lot_aleatoire(train)
            with autocast():
                logits = modele.langue(x)
                perte = F.cross_entropy(logits.float().view(-1, logits.size(-1)), y.view(-1))
            scaler.scale(perte / accumulation).backward()
        scaler.unscale_(opt)
        torch.nn.utils.clip_grad_norm_(modele.parameters(), 1.0)
        scaler.step(opt)
        scaler.update()
        opt.zero_grad(set_to_none=True)

        if (etape + 1) % eval_tous == 0 or etape == pas - 1:
            pv = perte_val()
            historique.append({"pas": etape + 1, "perte": perte.item(), "perte_val": pv})
            journal.info("pas %d/%d  perte %.3f  val %.3f  (perplexité %.1f)  %.0f s",
                         etape + 1, pas, perte.item(), pv, math.exp(min(pv, 20)),
                         time.time() - debut)
            if pv < meilleure:
                meilleure = pv
                Path(sortie).parent.mkdir(parents=True, exist_ok=True)
                modele.sauver(sortie, {"etape": "pretrain", "perte_val": pv, "pas": etape + 1,
                                       "taille": taille})
    return {"perte_val": meilleure, "historique": historique}


# --------------------------------------------------------------------------- #
# 3. Spécialisation (têtes « avis »)
# --------------------------------------------------------------------------- #
def exemples(lignes: list[dict], tok: TokenizerBPE, contexte: int, etape: str,
             metier: str) -> list[dict]:
    nb_themes = len(etiquettes.themes(metier))
    resultat = []
    for l in lignes:
        if not l.get("texte"):
            continue
        if etape == "etoiles":
            s = etiquettes.depuis_etoiles(l.get("note"))
            lab = {"sentiment": etiquettes.SENTIMENTS.index(s) if s else IGN,
                   "humeur": IGN, "themes": [IGN] * nb_themes}
            # Notes détaillées Google : étiquettes faibles pour 3 thèmes.
            liste = etiquettes.themes(metier)
            for theme, polarite in etiquettes.themes_depuis_notes(
                    l.get("notes_detaillees")).items():
                if theme in liste:
                    lab["themes"][liste.index(theme)] = etiquettes.POLARITES.index(polarite)
        else:
            lab = etiquettes.encoder(l.get("etiquette"), metier)
        if lab["sentiment"] == IGN and lab["humeur"] == IGN and all(
                t == IGN for t in lab["themes"]):
            continue
        resultat.append({"ids": tok.encoder(l["texte"], bos=True)[:contexte], **lab})
    return resultat


def assembler(lot: list[dict], dev: str):
    longueur = max(len(e["ids"]) for e in lot)
    ids = torch.full((len(lot), longueur), PAD, dtype=torch.long)
    masque = torch.zeros((len(lot), longueur), dtype=torch.bool)
    for i, e in enumerate(lot):
        ids[i, :len(e["ids"])] = torch.tensor(e["ids"])
        masque[i, :len(e["ids"])] = True
    cibles = {
        "sentiment": torch.tensor([e["sentiment"] for e in lot]),
        "humeur": torch.tensor([e["humeur"] for e in lot]),
        "themes": torch.tensor([e["themes"] for e in lot]),
    }
    return ids.to(dev), masque.to(dev), {k: v.to(dev) for k, v in cibles.items()}


def poids_classes(valeurs: list[int], nb: int) -> torch.Tensor:
    """Inverse de la fréquence : les classes rares (NEGATIF, MIXTE) comptent plus."""
    compte = np.bincount([v for v in valeurs if v != IGN], minlength=nb).astype(float)
    poids = np.where(compte > 0, compte.sum() / (nb * np.maximum(compte, 1)), 0.0)
    return torch.tensor(np.clip(poids, 0.0, 10.0), dtype=torch.float32)


def poids_themes(lignes_themes: list[list[int]], nb_themes: int,
                 nb_polarites: int = 4) -> torch.Tensor:
    """Poids par thème et par polarité, [nb_themes, nb_polarites].

    Pour chaque thème, « absent » écrase les autres valeurs (souvent plus de 90 % des
    avis) : sans correction, le modèle apprend à toujours répondre « absent ». On
    pondère par la racine de l'inverse de la fréquence (plus doux que l'inverse simple,
    pour ne pas inventer des thèmes partout), borné à [0, 10]."""
    compte = np.zeros((nb_themes, nb_polarites))
    for ligne in lignes_themes:
        for j, v in enumerate(ligne):
            if v != IGN:
                compte[j, v] += 1
    total = compte.sum(axis=1, keepdims=True)
    poids = np.where(compte > 0,
                     np.sqrt(total / (nb_polarites * np.maximum(compte, 1))), 0.0)
    return torch.tensor(np.clip(poids, 0.0, 10.0), dtype=torch.float32)


def perte_avis(sorties: dict, cibles: dict, poids_sentiment: torch.Tensor,
               poids_th: torch.Tensor | None = None, facteur_themes: float = 1.0) -> torch.Tensor:
    termes = []
    if (cibles["sentiment"] != IGN).any():
        termes.append(F.cross_entropy(sorties["sentiment"].float(), cibles["sentiment"],
                                      weight=poids_sentiment, ignore_index=IGN))
    if (cibles["humeur"] != IGN).any():
        termes.append(F.cross_entropy(sorties["humeur"].float(), cibles["humeur"],
                                      ignore_index=IGN))
    if (cibles["themes"] != IGN).any():
        logits = sorties["themes"].float()
        cib = cibles["themes"]
        brut = F.cross_entropy(logits.reshape(-1, logits.size(-1)), cib.reshape(-1),
                               ignore_index=IGN, reduction="none").view_as(cib)
        valide = cib != IGN
        if poids_th is not None:  # poids[thème, polarité cible]
            idx = torch.arange(cib.size(1), device=cib.device).expand_as(cib)
            w = poids_th[idx, cib.clamp(min=0)] * valide
        else:
            w = valide.float()
        termes.append(facteur_themes * (brut * w).sum() / w.sum().clamp(min=1e-6))
    return sum(termes)


@torch.no_grad()
def predire(modele: ModeleAvis, exs: list[dict], dev: str, lot: int = 64) -> dict[str, list]:
    modele.eval()
    sortie = {"sentiment": [], "confiance": [], "humeur": [], "themes": []}
    for i in range(0, len(exs), lot):
        ids, masque, _ = assembler(exs[i:i + lot], dev)
        s = modele.classer(ids, masque)
        p = torch.softmax(s["sentiment"].float(), dim=-1)
        conf, idx = p.max(dim=-1)
        sortie["sentiment"] += idx.tolist()
        sortie["confiance"] += conf.tolist()
        sortie["humeur"] += s["humeur"].argmax(dim=-1).tolist()
        sortie["themes"] += s["themes"].argmax(dim=-1).tolist()
    return sortie


def scores_validation(pred: dict, exs: list[dict], metier: str) -> dict[str, float]:
    themes = etiquettes.themes(metier)
    res = {}
    ok = [i for i, e in enumerate(exs) if e["sentiment"] != IGN]
    if ok:
        res["f1_sentiment"] = metriques.f1_macro(
            [etiquettes.SENTIMENTS[exs[i]["sentiment"]] for i in ok],
            [etiquettes.SENTIMENTS[pred["sentiment"][i]] for i in ok], etiquettes.SENTIMENTS)
    ok = [i for i, e in enumerate(exs) if e["humeur"] != IGN]
    if ok:
        res["f1_humeur"] = metriques.f1_macro(
            [etiquettes.HUMEURS[exs[i]["humeur"]] for i in ok],
            [etiquettes.HUMEURS[pred["humeur"][i]] for i in ok], etiquettes.HUMEURS)
    ok = [i for i, e in enumerate(exs) if IGN not in e["themes"]]
    if ok:
        def paires(indices):
            return {(themes[j], etiquettes.POLARITES[v]) for j, v in enumerate(indices) if v != 0}
        res["f1_themes"] = metriques.f1_ensembles([paires(exs[i]["themes"]) for i in ok],
                                                  [paires(pred["themes"][i]) for i in ok])
    return res


def calibrer_seuil(pred: dict, exs: list[dict], precision_cible: float) -> tuple[float, float]:
    """Plus petit seuil de confiance tel que les avis gardés par le modèle maison
    (confiance ≥ seuil) soient justes à `precision_cible` au moins. En dessous,
    l'avis part en relais vers Gemini. Renvoie (seuil, part des avis gardés)."""
    couples = sorted(((pred["confiance"][i], pred["sentiment"][i] == e["sentiment"])
                      for i, e in enumerate(exs) if e["sentiment"] != IGN), reverse=True)
    if not couples:
        return 0.6, 0.0
    meilleur, justes = (couples[0][0], 0.0), 0
    for k, (conf, juste) in enumerate(couples, start=1):
        justes += juste
        if justes / k >= precision_cible:
            meilleur = (conf, k / len(couples))
    return round(float(meilleur[0]), 4), round(float(meilleur[1]), 4)


def _lire(chemins: str | Path | list) -> list[dict]:
    """Un ou plusieurs fichiers JSON Lines, concaténés (jeux aux étiquettes partielles)."""
    if isinstance(chemins, str | Path):
        chemins = [chemins]
    return [l for c in chemins for l in lire_jsonl(c)]


def tetes_entrainees(ex_train: list[dict], meta_init: dict) -> list[str]:
    """Têtes qui ont reçu au moins une étiquette, ici ou dans une spécialisation
    précédente (étape « etoiles » puis « etiquettes »). Une tête jamais entraînée
    sort des valeurs aléatoires : la production ne doit pas les afficher."""
    tetes = set(meta_init.get("tetes_entrainees", []))
    if any(e["sentiment"] != IGN for e in ex_train):
        tetes.add("sentiment")
    if any(e["humeur"] != IGN for e in ex_train):
        tetes.add("humeur")
    if any(t != IGN for e in ex_train for t in e["themes"]):
        tetes.add("themes")
    return sorted(tetes)


def themes_entraines(ex_train: list[dict], meta_init: dict, metier: str) -> list[str]:
    """Thèmes qui ont reçu au moins une étiquette (les notes Google n'en couvrent que 3)."""
    liste = etiquettes.themes(metier)
    vus = set(meta_init.get("themes_entraines", []))
    vus |= {liste[j] for e in ex_train for j, t in enumerate(e["themes"]) if t != IGN}
    return [t for t in liste if t in vus]


def finetune(train: str | Path | list, val: str | Path | list, tokenizer: str | Path,
             sortie: str | Path,
             init: str | Path | None = None, taille: str = "S", contexte: int = 256,
             etape: str = "etiquettes", epoques: int = 5, lot: int = 32,
             lr: float | None = None, version: str = "nlp-v1", metier: str = "restaurant",
             precision_cible: float = 0.9, graine: int = 0,
             max_exemples: int | None = None, facteur_themes: float = 1.0) -> dict:
    torch.manual_seed(graine)
    rng = np.random.default_rng(graine)
    dev = appareil()
    tok = TokenizerBPE.charger(tokenizer)
    meta_init: dict = {}
    if init:
        modele, meta_init = ModeleAvis.charger(init, dev)
        contexte = modele.cfg.contexte
    else:
        modele = ModeleAvis(ConfigModele.depuis_taille(
            taille, len(tok), contexte=contexte, nb_themes=len(etiquettes.themes(metier)))).to(dev)
    lr = lr or (1e-4 if init else 3e-4)

    lignes_train = _lire(train)
    if max_exemples and len(lignes_train) > max_exemples:  # échantillon mélangé, toutes sources
        lignes_train = [lignes_train[i] for i in
                        rng.permutation(len(lignes_train))[:max_exemples]]
    ex_train = exemples(lignes_train, tok, contexte, etape, metier)
    ex_val = exemples(_lire(val), tok, contexte, etape, metier)
    if not ex_train or not ex_val:
        raise SystemExit("Aucun exemple étiqueté dans train ou val pour cette étape.")
    poids = poids_classes([e["sentiment"] for e in ex_train], len(etiquettes.SENTIMENTS)).to(dev)
    poids_th = poids_themes([e["themes"] for e in ex_train],
                            len(etiquettes.themes(metier)), len(etiquettes.POLARITES)).to(dev)
    tetes = tetes_entrainees(ex_train, meta_init)
    themes_appris = themes_entraines(ex_train, meta_init, metier)
    journal.info("spécialisation « %s » sur %s : %d exemples train, %d val, %.1f M paramètres",
                 etape, dev, len(ex_train), len(ex_val), modele.nb_parametres() / 1e6)

    opt = optimiseur(modele, lr)
    autocast, scaler = precision_mixte(dev)
    total = epoques * math.ceil(len(ex_train) / lot)
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    meilleur, pas, historique = -1.0, 0, []

    for epoque in range(epoques):
        modele.train()
        ordre = rng.permutation(len(ex_train))
        pertes = []
        for i in range(0, len(ordre), lot):
            for groupe in opt.param_groups:
                groupe["lr"] = taux(pas, total, lr, max(1, total // 20))
            ids, masque, cibles = assembler([ex_train[j] for j in ordre[i:i + lot]], dev)
            with autocast():
                perte = perte_avis(modele.classer(ids, masque), cibles, poids, poids_th,
                                   facteur_themes)
            scaler.scale(perte).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(modele.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            opt.zero_grad(set_to_none=True)
            pertes.append(perte.item())
            pas += 1
        scores = scores_validation(predire(modele, ex_val, dev), ex_val, metier)
        global_ = float(np.mean(list(scores.values()))) if scores else 0.0
        historique.append({"epoque": epoque + 1, "perte": float(np.mean(pertes)), **scores})
        journal.info("époque %d/%d  perte %.3f  %s", epoque + 1, epoques, np.mean(pertes),
                     "  ".join(f"{k} {v:.3f}" for k, v in scores.items()))
        if global_ > meilleur:
            meilleur = global_
            modele.sauver(sortie / "modele.pt", {"version": version, "metier": metier,
                                                  "etape": etape, "taille": taille,
                                                  "validation": scores,
                                                  "tetes_entrainees": tetes,
                                                  "themes_entraines": themes_appris})

    # Seuil de confiance calibré sur la validation, avec le meilleur modèle.
    modele, meta = ModeleAvis.charger(sortie / "modele.pt", dev)
    pred = predire(modele, ex_val, dev)
    seuil, couverture = calibrer_seuil(pred, ex_val, precision_cible)
    meta.update(seuil_confiance=seuil, couverture_val=couverture, precision_cible=precision_cible)
    modele.sauver(sortie / "modele.pt", meta)
    shutil.copy(tokenizer, sortie / "tokenizer.json")
    journal.info("seuil de confiance %.3f : le modèle maison garde %.0f %% des avis de "
                 "validation", seuil, 100 * couverture)
    return {"meta": meta, "historique": historique}
