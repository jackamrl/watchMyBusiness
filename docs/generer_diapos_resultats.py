"""Ajoute 2 diapos de résultats NLP après la diapo 21 du deck de soutenance."""
import copy
import sys

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

SRC, OUT = sys.argv[1], sys.argv[2]
p = Presentation(SRC)

TX = RGBColor(0x1B, 0x24, 0x30)
GRIS = RGBColor(0x5B, 0x6B, 0x78)
FOND = RGBColor(0xF2, 0xF5, 0xF7)
TEAL = RGBColor(0x23, 0x96, 0x8A)
TEAL_C = RGBColor(0x9F, 0xD3, 0xCD)
ORANGE = RGBColor(0xE5, 0x9F, 0x2F)
VIOLET = RGBColor(0x6A, 0x5A, 0xCD)
BLEU = RGBColor(0x2B, 0x5C, 0x8A)
ROUGE = RGBColor(0xD2, 0x50, 0x4A)
CREME = RGBColor(0xFC, 0xEB, 0xD5)
BLANC = RGBColor(0xFF, 0xFF, 0xFF)

modele = p.slides[22]  # diapo 23 : même gabarit CONTENU
num = next(sh for sh in modele.shapes if sh.is_placeholder and sh.placeholder_format.type == 13)


def nouvelle(titre, notes):
    s = p.slides.add_slide(modele.slide_layout)
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx != 100:
            ph._element.getparent().remove(ph._element)
    t = s.placeholders[100]
    t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.8)
    tf = t.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    r = tf.paragraphs[0].add_run()
    r.text = titre
    r.font.size, r.font.bold, r.font.color.rgb = Pt(34), True, TX
    s.shapes._spTree.append(copy.deepcopy(num._element))
    s.notes_slide.notes_text_frame.text = notes
    return s


def texte(s, x, y, w, h, lignes, taille=14, couleur=TX, gras=False, align=PP_ALIGN.LEFT,
          ancre=MSO_ANCHOR.TOP, marge=0):
    """lignes : liste de str ou de (str, taille, couleur, gras)."""
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = ancre
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(marge)
    for i, l in enumerate(lignes):
        if isinstance(l, str):
            l = (l, taille, couleur, gras)
        par = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        par.alignment = align
        run = par.add_run()
        run.text = l[0]
        run.font.size, run.font.color.rgb, run.font.bold = Pt(l[1]), l[2], l[3]
    return tb


def boite(s, x, y, w, h, couleur):
    b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.adjustments[0] = 0.08
    b.fill.solid()
    b.fill.fore_color.rgb = couleur
    b.line.fill.background()
    b.shadow.inherit = False
    return b


def fleche(s, x1, y1, x2, y2):
    c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = ORANGE
    c.line.width = Pt(1.75)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle"}))


# ---------- Diapo A : la chaîne d'entraînement réellement exécutée ----------
A = nouvelle(
    "Entraînement réel : quatre étapes, de zéro à L'As du Fallafel",
    "Voici ce que nous avons réellement entraîné, sur un MacBook, sans aucun modèle pré-entraîné "
    "externe. Étape 1 : un tokenizer BPE écrit à la main, 16 000 sous-mots, et un mini-GPT taille S "
    "pré-entraîné à prédire le mot suivant sur un corpus français et anglais ; perplexité finale 46,7. "
    "Étape 2 : supervision faible par les étoiles sur des avis publics, Allociné, clapAI et TripAdvisor : "
    "on atteint un F1 de 0,91 sur Allociné et 0,87 sur TripAdvisor. Étape 3 : spécialisation sur "
    "L'As du Fallafel avec 2 804 avis Google et 330 avis TripAdvisor collectés par Apify, découpés par date, en utilisant les "
    "étoiles et les notes Cuisine, Service, Ambiance. Étape 4 : les avis d'entraînement "
    "reçoivent des étiquettes fines, sentiment, humeur et thèmes, produites automatiquement comme "
    "la consigne l'autorise. 2 622 avis d'entraînement étiquetés, dont 330 venus de "
    "TripAdvisor, aucun échec, et surtout 688 avis MIXTE que les étoiles ne pouvaient pas apprendre au modèle.")

etapes = [
    ("1", "Pré-entraînement", "mot suivant, corpus fr + en", VIOLET,
     [("16 000", "sous-mots BPE faits main"), ("46,7", "perplexité finale")]),
    ("2", "Étoiles", "Allociné · clapAI · TripAdvisor", BLEU,
     [("0,91", "F1 sentiment Allociné"), ("0,87", "F1 sentiment TripAdvisor")]),
    ("3", "Spécialisation", "L'As du Fallafel : Google + TripAdvisor", TEAL,
     [("3 134", "avis : 2 804 Google + 330 TripAdvisor"), ("3", "thèmes via notes Cuisine / Service / Ambiance")]),
    ("4", "Étiquettes fines", "sentiment · humeur · thèmes", ORANGE,
     [("2 622", "avis d'entraînement étiquetés, 0 échec"), ("688", "avis MIXTE, invisibles aux étoiles")]),
]
X0, LARG, ECART, Y0 = 0.6, 2.75, 0.367, 1.45
for i, (n, nom, sous, coul, stats) in enumerate(etapes):
    x = X0 + i * (LARG + ECART)
    boite(A, x, Y0, LARG, 1.05, coul)
    texte(A, x, Y0, LARG, 1.05, [(f"{n}. {nom}", 17, BLANC, True), (sous, 12, BLANC, False)],
          align=PP_ALIGN.CENTER, ancre=MSO_ANCHOR.MIDDLE, marge=0.08)
    if i < 3:
        fleche(A, x + LARG + 0.04, Y0 + 0.525, x + LARG + ECART - 0.04, Y0 + 0.525)
    for j, (chiffre, legende) in enumerate(stats):
        y = Y0 + 1.3 + j * 1.35
        boite(A, x, y, LARG, 1.15, FOND)
        texte(A, x + 0.2, y + 0.08, LARG - 0.4, 0.6, [(chiffre, 30, coul, True)])
        texte(A, x + 0.2, y + 0.68, LARG - 0.4, 0.45, [(legende, 12, GRIS, False)])

boite(A, 0.6, 5.55, 12.1, 0.75, CREME)
texte(A, 0.85, 5.55, 11.6, 0.75,
      [("Tout tourne en local : ", 14, TX, True)], ancre=MSO_ANCHOR.MIDDLE)
tb = A.shapes[-1].text_frame.paragraphs[0]
r = tb.add_run()
r.text = ("mini-GPT taille S (≈ 7 M de paramètres), tokenizer et Transformer écrits en PyTorch, "
          "entraînés sur MacBook, aucun poids ni modèle pré-entraîné externe.")
r.font.size, r.font.color.rgb = Pt(14), TX

# ---------- Diapo B : résultats ----------
B = nouvelle(
    "Résultats : notre modèle face à Gemini",
    "Tous les modèles sont évalués sur les mêmes 280 avis de test de L'As du Fallafel, postérieurs à "
    "ceux de l'entraînement et annotés à part. Le Bayes naïf est le plancher. Notre modèle seul "
    "atteint 0,54 de F1 sur le sentiment, 0,44 sur l'humeur et 0,53 sur les thèmes, avec 77 % "
    "d'exactitude sur le sentiment. Il combine deux réseaux : le principal pour le sentiment et "
    "l'humeur, et un spécialiste des thèmes entraîné avec une perte pondérée, car la réponse "
    "« absent » écrasait tout : le repérage de l'attente passe ainsi de 0,16 à 0,42. Face à Gemini, "
    "notre référence : 0,77 d'exactitude contre 0,86, soit environ 90 % de sa qualité sur le "
    "sentiment, avec un modèle des milliers de fois plus petit, gratuit et local. Et sur les 77 % "
    "d'avis où notre modèle est sûr de lui, il a raison à 84 % ; les autres sont signalés « à "
    "vérifier ». Limites honnêtes : Gemini reste devant, surtout sur l'humeur et les thèmes ; la classe NEUTRE, très rare, n'est jamais reconnue ; deux thèmes rares, régularité et "
    "vente à emporter, ne sont pas encore repérés. Prochaines étapes : plus d'avis étiquetés et un "
    "modèle plus grand entraîné sur GPU.")

cd = CategoryChartData()
cd.categories = ["F1 sentiment", "F1 humeur", "F1 thèmes"]
series = [("Bayes naïf", (0.457, 0.270, 0.543), RGBColor(0x8A, 0x97, 0xA3)),
          ("Notre modèle · étoiles seules", (0.425, 0.280, 0.438), TEAL_C),
          ("Notre modèle · final", (0.538, 0.440, 0.529), TEAL),
          ("Gemini (référence)", (0.719, 0.682, 0.868), ORANGE)]
for nom, v, _ in series:
    cd.add_series(nom, v)
gf = B.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.45), Inches(1.3),
                        Inches(7.6), Inches(4.3), cd)
ch = gf.chart
ch.font.name, ch.font.size, ch.font.color.rgb = "Calibri", Pt(12), GRIS
ch.has_legend = False
pl = ch.plots[0]
pl.gap_width, pl.overlap = 60, -5
pl.has_data_labels = True
dl = pl.data_labels
dl.number_format, dl.number_format_is_linked = "0.00", False
dl.position = XL_LABEL_POSITION.OUTSIDE_END
dl.font.size, dl.font.color.rgb = Pt(10), GRIS
for (nom, _, coul), s in zip(series, pl.series):
    s.format.fill.solid()
    s.format.fill.fore_color.rgb = coul
va = ch.value_axis
va.maximum_scale, va.minimum_scale, va.major_unit = 1.0, 0, 0.25
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = RGBColor(0xE1, 0xE6, 0xEA)
va.format.line.fill.background()
va.tick_labels.font.size = Pt(11)
va.tick_labels.number_format, va.tick_labels.number_format_is_linked = "0.00", False
ca = ch.category_axis
ca.format.line.color.rgb = RGBColor(0xC8, 0xD0, 0xD6)
ca.tick_labels.font.size, ca.tick_labels.font.color.rgb = Pt(13), TX

x = 0.75
for nom, _, coul in series:
    carre = B.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(5.72), Inches(0.16), Inches(0.16))
    carre.fill.solid()
    carre.fill.fore_color.rgb = coul
    carre.line.fill.background()
    larg = 0.12 + 0.068 * len(nom)
    texte(B, x + 0.24, 5.66, larg, 0.3, [(nom, 12, TX, False)])
    x += 0.24 + larg + 0.25

texte(B, 0.6, 6.12, 7.5, 0.3,
      [("Test : 280 avis de L'As du Fallafel, postérieurs à l'entraînement, annotés à part", 11, GRIS, False)])

cartes = [("0,77", "exactitude sur le sentiment, contre 0,86 pour Gemini (≈ 90 %)", TEAL),
          ("84 %", "de bonnes réponses sur les 77 % d'avis où notre modèle est sûr de lui", VIOLET),
          ("×2,6", "repérage du thème « attente » (0,16 → 0,42) grâce à la perte pondérée", TEAL)]
for i, (chiffre, leg, coul) in enumerate(cartes):
    y = 1.35 + i * 1.12
    boite(B, 8.45, y, 4.25, 0.97, FOND)
    texte(B, 8.65, y, 1.35, 0.97, [(chiffre, 26, coul, True)], ancre=MSO_ANCHOR.MIDDLE)
    texte(B, 10.0, y, 2.55, 0.97, [(leg, 12, TX, False)], ancre=MSO_ANCHOR.MIDDLE)

boite(B, 8.45, 4.71, 4.25, 1.34, CREME)
texte(B, 8.65, 4.81, 3.9, 1.2,
      [("Limites honnêtes", 14, TX, True),
       ("Gemini reste devant, surtout sur l'humeur et les thèmes. NEUTRE (12 avis) n'est jamais reconnu ; "
        "« régularité » et « emporter » ne sont pas encore repérés.", 12, TX, False)])

# ---------- ordre : A et B juste après la diapo 21 ----------
lst = p.slides._sldIdLst
ids = list(lst)
a, b = ids[-2], ids[-1]
lst.remove(a)
lst.remove(b)
lst.insert(21, a)
lst.insert(22, b)

# ---------- mises à jour factuelles ----------
for sh in p.slides[20].shapes:  # diapo 21
    if sh.has_text_frame:
        for par in sh.text_frame.paragraphs:
            for run in par.runs:
                if "300 avis" in run.text:
                    run.text = run.text.replace("300 avis", "280 avis")
val = p.slides[24]  # ancienne diapo 23, maintenant 25
for sh in val.shapes:
    if sh.has_text_frame:
        for par in sh.text_frame.paragraphs:
            for run in par.runs:
                if run.text == "22":
                    run.text = "47"
nt = val.notes_slide.notes_text_frame
nt.text = nt.text.replace("22 tests unitaires", "47 tests unitaires")

p.save(OUT)
print("ok", len(p.slides))
