"""Diapo « Architecture fonctionnelle » (vue métier, sans nom de service cloud).

Construite en formes natives PowerPoint, aux couleurs du thème du deck, sur le
gabarit d'une diapo CONTENU existante (titre, pied de page, numéro).
"""

import copy

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

NUIT = RGBColor(0x1B, 0x24, 0x30)
TEXTE = RGBColor(0x1F, 0x33, 0x40)
GRIS = RGBColor(0x5B, 0x6B, 0x78)
TRAIT = RGBColor(0x8A, 0x99, 0xA6)
CARTE = RGBColor(0xF2, 0xF5, 0xF7)
BLANC = RGBColor(0xFF, 0xFF, 0xFF)
ORANGE = RGBColor(0xE5, 0x9F, 0x2F)
VIOLET = RGBColor(0x6A, 0x5A, 0xCD)
SARCELLE = RGBColor(0x23, 0x96, 0x8A)
BLEU = RGBColor(0x2B, 0x5C, 0x8A)
VERT = RGBColor(0x3C, 0x9A, 0x4E)

TITRE = "Architecture fonctionnelle : de l'avis à la décision"

ETAPES = [
    ("1", "Collecter", VIOLET, [
        ("Nouveaux avis", "Google Maps et TripAdvisor"),
        ("Réponse brute conservée", "rejouable à tout moment"),
        ("Doublons écartés", "1 avis = 1 identifiant"),
    ]),
    ("2", "Analyser", SARCELLE, [
        ("Notre modèle NLP", "classe chaque avis"),
        ("Sentiment · humeur · thèmes", "8 thèmes, positifs ou négatifs"),
        ("Avis incertains", "signalés « à vérifier »"),
    ]),
    ("3", "Agréger", BLEU, [
        ("Indicateurs de la semaine", "volume, note, % positifs"),
        ("Tendance", "comparée à la semaine d'avant"),
        ("Chiffres calculés", "jamais inventés"),
    ]),
    ("4", "Restituer", VERT, [
        ("Rapport du lundi", "envoyé par e-mail"),
        ("Tableau de bord", "thèmes, humeurs, avis filtrables"),
        ("Watchy", "répond aux questions du gérant"),
    ]),
]

NOTES = (
    "Avant les services cloud, la vue métier : quatre étapes, sans aucune intervention humaine. "
    "À gauche, les sources : les avis publics Google Maps et TripAdvisor, sans nom d'auteur. "
    "Chaque jour à 6 h, on collecte les nouveaux avis, on garde la réponse brute pour pouvoir "
    "rejouer, et on écarte les doublons. Puis notre propre modèle NLP classe chaque avis : "
    "sentiment, humeur, thèmes ; quand il hésite, l'avis est signalé « à vérifier ». "
    "Chaque lundi à 8 h, on agrège la semaine : indicateurs et tendance par rapport à la semaine "
    "précédente. Les chiffres sont toujours calculés, jamais rédigés par un modèle. "
    "Enfin on restitue : le rapport du lundi par e-mail, le tableau de bord, et Watchy pour poser "
    "des questions. Tout l'historique est conservé. Le gérant n'a rien à lancer : il lit, il décide."
)


def _boite(diapo, x, y, w, h, fond, forme=MSO_SHAPE.ROUNDED_RECTANGLE, trait=None, tirets=False):
    b = diapo.shapes.add_shape(forme, Inches(x), Inches(y), Inches(w), Inches(h))
    if forme == MSO_SHAPE.ROUNDED_RECTANGLE:
        b.adjustments[0] = 0.08
    if fond is None:
        b.fill.background()
    else:
        b.fill.solid()
        b.fill.fore_color.rgb = fond
    if trait is None:
        b.line.fill.background()
    else:
        b.line.color.rgb = trait
        b.line.width = Pt(1.25)
        if tirets:
            b.line.dash_style = 4  # tiret
    b.shadow.inherit = False
    return b


def _texte(forme, lignes, align=PP_ALIGN.CENTER, ancre=MSO_ANCHOR.MIDDLE, marge=0.08):
    """lignes : liste de (texte, taille, gras, couleur, espace_apres)."""
    tf = forme.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancre
    for cote in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, cote, Inches(marge))
    for k, (txt, taille, gras, couleur, apres) in enumerate(lignes):
        p = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(apres)
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(taille)
        r.font.bold = gras
        r.font.color.rgb = couleur


def _fleche(diapo, x1, y1, x2, y2, couleur=TEXTE):
    c = diapo.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = couleur
    c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln()
    queue = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(queue)
    return c


def ajouter(prs, modele):
    """Ajoute la diapo en fin de présentation, sur le gabarit de `modele`."""
    d = prs.slides.add_slide(modele.slide_layout)
    arbre = d.shapes._spTree
    for ph in list(d.placeholders):
        arbre.remove(ph._element)
    for forme in modele.shapes:
        if forme.is_placeholder:
            arbre.append(copy.deepcopy(forme._element))
    titre = d.shapes.title or next(f for f in d.shapes if f.is_placeholder)
    runs = titre.text_frame.paragraphs[0].runs
    runs[0].text = TITRE
    for r in runs[1:]:
        r.text = ""

    # Géométrie (pouces) : sources | 4 étapes | gérant
    x0, cote, larg, ecart = 0.6, 1.45, 1.93, 0.3
    xs = [x0 + cote + ecart + i * (larg + ecart) for i in range(4)]
    x_gerant = xs[-1] + larg + ecart
    y_cad, y_ent, y_carte, h_carte = 1.4, 1.95, 2.8, 2.15
    y_hist = y_carte + h_carte + 0.2

    # Cadences
    for (i, j), libelle in (((0, 1), "chaque jour · 06:00"), ((2, 3), "chaque lundi · 08:00")):
        b = _boite(d, xs[i], y_cad, xs[j] + larg - xs[i], 0.4, None, trait=TRAIT, tirets=True)
        _texte(b, [(libelle, 12, True, GRIS, 0)])

    # Étapes
    for x, (num, verbe, couleur, lignes) in zip(xs, ETAPES):
        e = _boite(d, x, y_ent, larg, 0.7, couleur)
        _texte(e, [(f"{num}. {verbe}", 17, True, BLANC, 0)])
        c = _boite(d, x, y_carte, larg, h_carte, CARTE)
        contenu = []
        for fort, detail in lignes:
            contenu.append((fort, 12.5, True, TEXTE, 0))
            contenu.append((detail, 11, False, GRIS, 9))
        _texte(c, contenu, align=PP_ALIGN.LEFT, ancre=MSO_ANCHOR.MIDDLE, marge=0.14)

    # Sources et gérant
    s = _boite(d, x0, y_ent, cote, y_carte + h_carte - y_ent, NUIT)
    _texte(s, [("Clients", 17, True, BLANC, 6),
               ("publient leurs avis", 11.5, False, BLANC, 10),
               ("Google Maps", 11.5, True, ORANGE, 2),
               ("TripAdvisor", 11.5, True, ORANGE, 10),
               ("avis publics, sans nom d'auteur", 10, False, RGBColor(0xC8, 0xD1, 0xD9), 0)])
    g = _boite(d, x_gerant, y_ent, cote, y_carte + h_carte - y_ent, ORANGE)
    _texte(g, [("Gérant", 17, True, BLANC, 6),
               ("lit le rapport,", 11.5, False, BLANC, 0),
               ("interroge Watchy,", 11.5, False, BLANC, 0),
               ("décide et agit", 11.5, True, BLANC, 0)])

    # Flèches du flux
    y_f = y_carte + h_carte / 2 - 0.35
    bords = [x0 + cote] + [x + larg for x in xs]
    debuts = xs + [x_gerant]
    for a, b in zip(bords, debuts):
        _fleche(d, a + 0.03, y_f, b - 0.03, y_f)

    # Historique commun
    h = _boite(d, xs[0], y_hist, xs[-1] + larg - xs[0], 0.5, None, trait=TRAIT)
    _texte(h, [("Historique conservé : avis bruts · analyses · rapports — chaque étape relit l'étape d'avant",
                12, False, TEXTE, 0)])

    # Message clé
    m = _boite(d, x0, y_hist + 0.75, x_gerant + cote - x0, 0.5, NUIT)
    _texte(m, [("Aucune intervention humaine entre la publication d'un avis et le rapport du lundi.",
                14, True, BLANC, 0)])

    d.notes_slide.notes_text_frame.text = NOTES
    return d
