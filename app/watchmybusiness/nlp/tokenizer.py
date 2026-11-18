"""Tokenizer BPE (Byte Pair Encoding) codé à la main.

Principe : on part des caractères, puis on fusionne à répétition la paire de
symboles adjacents la plus fréquente du corpus, jusqu'à atteindre la taille de
vocabulaire voulue. Encoder un mot = rejouer ces fusions dans l'ordre appris.

Les espaces font partie des jetons (« ␣bon » ≠ « bon ») : décoder revient à
concaténer les jetons, sans règle supplémentaire.
"""

from __future__ import annotations

import heapq
import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

SPECIAUX = ("<pad>", "<unk>", "<bos>", "<eos>", "<sep>")
PAD, UNK, BOS, EOS, SEP = range(len(SPECIAUX))

# Pré-découpage : mots (lettres, accents compris), nombres, ponctuation/emojis,
# espaces. Une fusion ne traverse jamais la frontière entre deux morceaux.
_DECOUPE = re.compile(r" ?[^\W\d_]+| ?\d+| ?[^\s\w]+|\s+", re.UNICODE)


def normaliser(texte: str) -> str:
    texte = unicodedata.normalize("NFC", texte)
    return re.sub(r"\s+", " ", texte).strip()


def decouper(texte: str) -> list[str]:
    return _DECOUPE.findall(normaliser(texte))


class TokenizerBPE:
    def __init__(self, vocab: list[str], fusions: list[tuple[str, str]]):
        self.vocab = vocab
        self.fusions = fusions
        self.index = {jeton: i for i, jeton in enumerate(vocab)}
        self.rangs = {paire: rang for rang, paire in enumerate(fusions)}
        self._cache: dict[str, list[int]] = {}

    # ------------------------------------------------------------------ #
    # Entraînement
    # ------------------------------------------------------------------ #
    @classmethod
    def entrainer(
        cls, textes: Iterable[str], taille_vocab: int = 8000, freq_min_caractere: int = 2
    ) -> TokenizerBPE:
        mots = Counter()
        for texte in textes:
            mots.update(decouper(texte))

        caracteres = Counter()
        for mot, freq in mots.items():
            for c in mot:
                caracteres[c] += freq
        alphabet = sorted(c for c, f in caracteres.items() if f >= freq_min_caractere)
        connus = set(alphabet)
        vocab = list(SPECIAUX) + alphabet
        deja = set(vocab)

        sequences = [[c if c in connus else "<unk>" for c in mot] for mot in mots]
        freqs = list(mots.values())

        paires: Counter = Counter()
        ou: dict[tuple[str, str], set[int]] = defaultdict(set)
        for i, seq in enumerate(sequences):
            for paire in zip(seq, seq[1:], strict=False):
                paires[paire] += freqs[i]
                ou[paire].add(i)

        # Tas « paresseux » : une entrée périmée est ignorée quand on la dépile.
        tas = [(-n, p) for p, n in paires.items()]
        heapq.heapify(tas)
        fusions: list[tuple[str, str]] = []

        while len(vocab) < taille_vocab and tas:
            moins_n, paire = heapq.heappop(tas)
            if paires.get(paire, 0) != -moins_n:
                continue
            if -moins_n < 2:
                break
            if "<unk>" in paire:
                del paires[paire]
                continue
            a, b = paire
            nouveau = a + b
            fusions.append(paire)
            if nouveau not in deja:
                vocab.append(nouveau)
                deja.add(nouveau)

            modifiees: set[tuple[str, str]] = set()
            for i in list(ou[paire]):
                seq, f = sequences[i], freqs[i]
                for p in zip(seq, seq[1:], strict=False):
                    paires[p] -= f
                    ou[p].discard(i)
                    modifiees.add(p)
                fusionnee, j = [], 0
                while j < len(seq):
                    if j + 1 < len(seq) and seq[j] == a and seq[j + 1] == b:
                        fusionnee.append(nouveau)
                        j += 2
                    else:
                        fusionnee.append(seq[j])
                        j += 1
                sequences[i] = fusionnee
                for p in zip(fusionnee, fusionnee[1:], strict=False):
                    paires[p] += f
                    ou[p].add(i)
                    modifiees.add(p)
            paires.pop(paire, None)
            ou.pop(paire, None)
            for p in modifiees:
                n = paires.get(p, 0)
                if n > 0:
                    heapq.heappush(tas, (-n, p))
                else:
                    paires.pop(p, None)

        return cls(vocab, fusions)

    # ------------------------------------------------------------------ #
    # Encodage / décodage
    # ------------------------------------------------------------------ #
    def _encoder_mot(self, mot: str) -> list[int]:
        if mot in self._cache:
            return self._cache[mot]
        symboles = [c if c in self.index else "<unk>" for c in mot]
        while len(symboles) > 1:
            candidates = [
                (self.rangs[p], k)
                for k, p in enumerate(zip(symboles, symboles[1:], strict=False))
                if p in self.rangs
            ]
            if not candidates:
                break
            rang, _ = min(candidates)
            a, b = self.fusions[rang]
            fusionnes, j = [], 0
            while j < len(symboles):
                if j + 1 < len(symboles) and symboles[j] == a and symboles[j + 1] == b:
                    fusionnes.append(a + b)
                    j += 2
                else:
                    fusionnes.append(symboles[j])
                    j += 1
            symboles = fusionnes
        ids = [self.index.get(s, UNK) for s in symboles]
        if len(self._cache) < 200_000:
            self._cache[mot] = ids
        return ids

    def encoder(self, texte: str, bos: bool = False, eos: bool = False) -> list[int]:
        ids = [BOS] if bos else []
        for mot in decouper(texte):
            ids.extend(self._encoder_mot(mot))
        if eos:
            ids.append(EOS)
        return ids

    def decoder(self, ids: Iterable[int]) -> str:
        return "".join(self.vocab[i] for i in ids if i >= len(SPECIAUX))

    def __len__(self) -> int:
        return len(self.vocab)

    # ------------------------------------------------------------------ #
    # Persistance
    # ------------------------------------------------------------------ #
    def sauver(self, chemin: str | Path) -> None:
        Path(chemin).write_text(
            json.dumps({"version": 1, "vocab": self.vocab, "fusions": self.fusions},
                       ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def charger(cls, chemin: str | Path) -> TokenizerBPE:
        donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
        return cls(donnees["vocab"], [tuple(p) for p in donnees["fusions"]])
