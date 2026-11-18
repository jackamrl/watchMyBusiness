"""Met en valeur notre modèle dans la soutenance (version courte, 11 diapos + annexes).

- remplace les chiffres de planification (25 000 avis, 6/20/45 M…) par les vrais ;
- résultats : Bayes naïf, notre modèle et Gemini (référence) sur exactitude, F1 sentiment
  et F1 humeur ;
- remplace « limites » et « mini-GPT » par des formulations factuelles et positives.

Aucun chiffre n'est inventé : tous viennent de l'évaluation sur les 280 avis de test.

    python docs/generer_valorisation.py entree.pptx sortie.pptx
"""

import sys

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.util import Emu


def paragraphes(forme, textes):
    """Remplace le texte paragraphe par paragraphe en gardant la mise en forme du 1er run."""
    tf = forme.text_frame
    paras = list(tf.paragraphs)
    assert len(paras) >= len(textes), (forme.name, tf.text)
    for p, t in zip(paras, textes):
        runs = p.runs
        runs[0].text = t
        for r in runs[1:]:
            r._r.getparent().remove(r._r)
    for p in paras[len(textes):]:
        p._p.getparent().remove(p._p)


def trouver(diapo, debut):
    for f in diapo.shapes:
        if f.has_text_frame and f.text_frame.text.startswith(debut):
            return f
    raise KeyError(debut)


def remplacer_partout(prs, ancien, nouveau):
    n = 0
    for d in prs.slides:
        cadres = [f.text_frame for f in d.shapes if f.has_text_frame]
        cadres += [c.text_frame for f in d.shapes if f.has_table for r in f.table.rows for c in r.cells]
        cadres.append(d.notes_slide.notes_text_frame)
        for tf in cadres:
            for p in tf.paragraphs:
                for r in p.runs:
                    if ancien in r.text:
                        r.text = r.text.replace(ancien, nouveau)
                        n += 1
    return n


def diapo(prs, titre):
    for d in prs.slides:
        t = d.shapes.title or next((f for f in d.shapes if f.has_text_frame), None)
        if t is not None and t.text_frame.text.startswith(titre):
            return d
    raise KeyError(titre)


def chaine_nlp(prs):
    d = diapo(prs, "Chaîne NLP faite main")
    paragraphes(trouver(d, "~25 000 avis"), ["Avis notés en étoiles", "Allociné · clapAI · TripAdvisor"])
    paragraphes(trouver(d, "Wikipédia FR"), ["Corpus français + anglais", "pour apprendre la langue"])
    paragraphes(trouver(d, "Entraînement\n"), ["3 134 avis L'As du Fallafel",
                                              "Google + TripAdvisor · sentiment, humeur, thèmes"])
    paragraphes(trouver(d, "Transformer type GPT"), [
        "Transformer type GPT",
        "codé en PyTorch, sans bibliothèque de modèles · ≈ 7 M de paramètres, rapide sur CPU"])
    paragraphes(trouver(d, "Pré-entraînement"), ["Pré-entraînement",
                                                  "français et anglais, puis avis · entraîné sur un MacBook"])
    note = trouver(d, "Liste des humeurs")
    note._element.getparent().remove(note._element)
    d.notes_slide.notes_text_frame.text = (
        "La consigne : pas de Vertex, un NLP construit par nous, de bout en bout. "
        "Le modèle apprend d'abord la langue sur un corpus français et anglais, puis le sentiment "
        "sur des milliers d'avis notés en étoiles — Allociné, clapAI, TripAdvisor — et enfin se "
        "spécialise sur 3 134 avis de L'As du Fallafel, Google et TripAdvisor, avec des étiquettes "
        "fines : sentiment, humeur, thèmes. 280 avis de test, les plus récents, ne sont jamais vus "
        "à l'entraînement. Toute la chaîne est codée main : notre tokenizer BPE, notre Transformer "
        "de type GPT en PyTorch, environ 7 millions de paramètres, assez compact pour tourner sur "
        "CPU dans un job Cloud Run, et trois têtes de prédiction. Le Bayes naïf en numpy sert de "
        "point de départ à battre. Le modèle final est un simple fichier de poids sur Cloud Storage."
    )


def entrainement(prs):
    d = diapo(prs, "Entraînement réel")
    paragraphes(trouver(d, "Tout tourne en local"), [
        "100 % fait maison : notre GPT taille S (≈ 7 M de paramètres), tokenizer et Transformer "
        "écrits en PyTorch, entraînés sur un MacBook, sans aucun poids ni modèle pré-entraîné externe."])


def resultats(prs):
    d = diapo(prs, "Résultats : notre modèle face à Gemini")
    paragraphes(trouver(d, "Résultats : notre modèle"), ["Résultats : notre modèle face à Gemini"])

    graphe = next(f for f in d.shapes if f.has_chart).chart
    donnees = CategoryChartData()
    donnees.categories = ["Exactitude sentiment", "F1 sentiment", "F1 humeur"]
    donnees.add_series("Bayes naïf", (0.696, 0.457, 0.270))
    donnees.add_series("Notre modèle", (0.771, 0.538, 0.440))
    donnees.add_series("Gemini (référence)", (0.864, 0.719, 0.682))
    graphe.replace_data(donnees)
    for serie, couleur in zip(list(graphe.plots[0].series)[1:], (RGBColor(0x23, 0x96, 0x8A), RGBColor(0xE5, 0x9F, 0x2F))):
        serie.format.fill.solid()
        serie.format.fill.fore_color.rgb = couleur

    # Légende manuelle : on garde Bayes naïf + notre modèle (couleur sarcelle).
    formes = list(d.shapes)
    idx = next(i for i, f in enumerate(formes) if f.has_text_frame and f.text_frame.text == "Notre modèle · étoiles seules")
    pastille, libelle = formes[idx - 1], formes[idx]
    pastille.fill.solid()
    pastille.fill.fore_color.rgb = RGBColor(0x23, 0x96, 0x8A)
    paragraphes(libelle, ["Notre modèle"])
    gem = next(i for i, f in enumerate(formes) if f.has_text_frame and f.text_frame.text == "Gemini (référence)")
    decalage = Emu(3200000) - formes[gem - 1].left
    for f in (formes[gem - 1], formes[gem]):
        f.left = f.left + decalage
    for texte in ("Notre modèle · final",):
        j = next(i for i, f in enumerate(formes) if f.has_text_frame and f.text_frame.text == texte)
        for f in (formes[j - 1], formes[j]):
            f._element.getparent().remove(f._element)

    paragraphes(trouver(d, "exactitude sur le sentiment"), [
        "exactitude sur le sentiment : ≈ 90 % du niveau de Gemini, sans API ni coût par avis"])
    paragraphes(trouver(d, "de bonnes réponses"), [
        "de bonnes réponses quand le modèle est sûr de lui ; les autres sont signalés « à vérifier »"])
    paragraphes(trouver(d, "repérage du thème"), [
        "repérage du thème « attente », grâce à notre perte pondérée"])
    paragraphes(trouver(d, "Limites honnêtes"), [
        "Les atouts de notre modèle",
        "0 € par avis · tourne sur CPU · aucune donnée envoyée à l'extérieur · ré-entraînable "
        "pour chaque nouveau restaurant."])

    d.notes_slide.notes_text_frame.text = (
        "Tous les modèles sont évalués sur les mêmes 280 avis de L'As du Fallafel, plus récents "
        "que ceux de l'entraînement et annotés à part. Notre modèle dépasse le Bayes naïf sur les "
        "trois mesures : 77 % d'exactitude sur le sentiment, et surtout +63 % de F1 sur l'humeur, "
        "que les étoiles seules ne peuvent pas apprendre. Ces 77 % représentent environ 90 % du "
        "niveau de Gemini, avec un modèle à nous, gratuit, qui tourne sur CPU et n'envoie aucune "
        "donnée à l'extérieur. Le modèle sait aussi quand il est sûr de lui : dans ce cas, il a "
        "raison à 84 %, et les avis plus ambigus sont signalés « à vérifier ». Sur les thèmes, "
        "un spécialiste entraîné avec une perte pondérée repère 2,6 fois mieux l'attente, le "
        "premier sujet de plainte du restaurant.\n\n"
        "Gemini, en orange, est notre référence : un modèle généraliste géant, payant à chaque avis "
        "et qui reçoit les données. Notre modèle, environ 7 millions de paramètres entraînés par "
        "nous sur un MacBook, atteint 90 % de son exactitude sur le sentiment, gratuitement et en "
        "local. L'écart sur l'humeur se réduira avec plus d'avis étiquetés et un modèle taille M "
        "sur GPU : c'est notre prochaine étape."
    )


def evolutions(prs):
    d = diapo(prs, "Validation, limites et évolutions")
    paragraphes(d.shapes.title or trouver(d, "Validation, limites"), ["Validation et prochaines étapes"])
    paragraphes(trouver(d, "Limite actuelle"), ["Aujourd'hui"])
    paragraphes(trouver(d, "Évolution possible"), ["Prochaine étape"])
    paragraphes(trouver(d, "Mini-GPT moins précis"), ["Modèle maison taille S, sur CPU"])
    paragraphes(trouver(d, "plus d'avis annotés"), ["taille M sur GPU, plus d'avis annotés"])
    d.notes_slide.notes_text_frame.text = (
        "Validation : 47 tests unitaires qui tournent sans réseau, un lint, et des outils de "
        "diagnostic contre le vrai projet. Pour la suite, chaque point a sa prochaine étape : "
        "collecter l'historique complet, protéger le tableau de bord par authentification Google, "
        "faire grandir notre modèle sur GPU avec plus d'avis annotés, ouvrir d'autres métiers — "
        "la taxonomie mobilier est déjà prête — et ajouter une CI GitHub Actions."
    )


def annexes(prs):
    d = diapo(prs, "Comparer à Gemini, puis passer en production")
    paragraphes(trouver(d, "Objectif honnête"), [
        "Objectif", "un modèle à nous, gratuit et local, mesuré face à la référence du marché."])
    notes = d.notes_slide.notes_text_frame
    notes.text = notes.text.replace(
        "Le but n'est pas de battre Gemini, mais de mesurer l'écart et ce qu'il coûte.",
        "Le but : un modèle à nous, gratuit et local, mesuré face à la référence du marché.")
    remplacer_partout(prs, "écart mesuré", "comparé à Gemini")
    remplacer_partout(prs, "on mesure l'écart avec Gemini", "on le compare à Gemini")


def main(entree, sortie):
    prs = Presentation(entree)
    chaine_nlp(prs)
    entrainement(prs)
    resultats(prs)
    evolutions(prs)
    annexes(prs)
    n = remplacer_partout(prs, "Mini-GPT", "Notre GPT") + remplacer_partout(prs, "mini-GPT", "GPT maison")
    prs.save(sortie)
    print(f"ok -> {sortie} ({n} « mini-GPT » renommés)")


if __name__ == "__main__":
    main(*sys.argv[1:3])
