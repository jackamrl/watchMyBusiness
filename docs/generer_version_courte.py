"""Version courte de la soutenance : 11 diapos dans le fil, le reste en annexes.

Rien n'est supprimé : les diapos détaillées passent après « Merci — questions ? »,
derrière un intercalaire « Annexes », numérotées A1, A2… pour les questions du jury.

    python docs/generer_version_courte.py entree.pptx sortie.pptx
"""

import copy
import sys

from pptx import Presentation
from pptx.oxml.ns import qn

import diapo_archi_fonctionnelle

# Numéros des diapos dans le deck complet (26 diapos).
FIL = [1, 2, 3, 4, 7, 18, 22, 23, 25, 26]
ANNEXES = [5, 6, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 24, 19, 20, 21]


def intercalaire(prs, modele):
    """Diapo « Annexes » sur le gabarit de la diapo de conclusion."""
    nouvelle = prs.slides.add_slide(modele.slide_layout)
    arbre = nouvelle.shapes._spTree
    for ph in list(nouvelle.placeholders):
        arbre.remove(ph._element)
    fond = modele._element.cSld.bg
    if fond is not None:
        nouvelle._element.cSld.insert(0, copy.deepcopy(fond))
    titre, sous_titre = list(modele.shapes)[:2]
    for forme, texte in ((titre, "Annexes"),
                         (sous_titre, "Le détail technique, pour répondre aux questions du jury.")):
        el = copy.deepcopy(forme._element)
        arbre.append(el)
        tf = nouvelle.shapes[-1].text_frame
        para = tf.paragraphs[0]
        for r in para.runs[1:]:
            r._r.getparent().remove(r._r)
        para.runs[0].text = texte
        for p in tf.paragraphs[1:]:
            p._p.getparent().remove(p._p)
    return nouvelle


def numeroter(diapo, libelle):
    for forme in diapo.shapes:
        if forme.name.startswith("Slide Number") and forme.has_text_frame:
            # Le numéro est un champ <a:fld type="slidenum"> : on le fige en texte
            # simple pour afficher « A3 » sur les annexes.
            para = forme.text_frame.paragraphs[0]._p
            for fld in para.findall(qn("a:fld")):
                fld.tag = qn("a:r")
                for attr in list(fld.attrib):
                    del fld.attrib[attr]
            textes = para.findall(f"{qn('a:r')}/{qn('a:t')}")
            for k, t in enumerate(textes):
                t.text = libelle if k == 0 else ""


def main(entree, sortie):
    prs = Presentation(entree)
    diapos = list(prs.slides)
    assert len(diapos) == 26, f"deck inattendu : {len(diapos)} diapos"
    assert sorted(FIL + ANNEXES) == list(range(1, 27))

    sep = intercalaire(prs, diapos[25])
    fonct = diapo_archi_fonctionnelle.ajouter(prs, diapos[5])
    fil = [diapos[n - 1] for n in FIL]
    fil.insert(FIL.index(7), fonct)  # juste avant l'architecture Google Cloud
    ordre = fil + [sep] + [diapos[n - 1] for n in ANNEXES]

    liste = prs.slides._sldIdLst
    par_id = {sid.rId: sid for sid in liste}
    ids = [par_id[prs.part.relate_to(d.part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide")]
           for d in ordre]
    for sid in list(liste):
        liste.remove(sid)
    for sid in ids:
        liste.append(sid)

    for i, d in enumerate(ordre[: len(fil)], 1):
        numeroter(d, str(i))
    for i, d in enumerate(ordre[len(fil) + 1:], 1):
        numeroter(d, f"A{i}")

    prs.save(sortie)
    print(f"{len(fil)} diapos dans le fil + intercalaire + {len(ANNEXES)} annexes -> {sortie}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
