"""Retire Gemini des diapos, sauf comme point de comparaison.
Le relais Gemini devient « avis incertain signalé à vérifier »."""
import sys

from pptx import Presentation

SRC, OUT = sys.argv[1], sys.argv[2]
p = Presentation(SRC)
S = lambda n: p.slides[n - 1]  # noqa: E731


def forme(n, nom):
    return next(sh for sh in S(n).shapes if sh.name == nom)


def paragraphe(n, nom, i, texte):
    """Remplace le texte du paragraphe i en gardant le style de son premier run."""
    par = forme(n, nom).text_frame.paragraphs[i]
    runs = par.runs
    runs[0].text = texte
    for r in runs[1:]:
        r._r.getparent().remove(r._r)


def cellule(n, r, c, texte):
    tableau = next(sh for sh in S(n).shapes if sh.has_table).table
    par = tableau.cell(r, c).text_frame.paragraphs[0]
    par.runs[0].text = texte
    for run in par.runs[1:]:
        run._r.getparent().remove(run._r)


def supprimer(n, *noms):
    for nom in noms:
        el = forme(n, nom)._element
        el.getparent().remove(el)


def note(n, avant, apres):
    tf = S(n).notes_slide.notes_text_frame
    assert avant in tf.text, (n, avant[:50])
    tf.text = tf.text.replace(avant, apres)


A_VERIFIER = "avis signalé « à vérifier »"

# --- diapo 6 : architecture fonctionnelle
paragraphe(6, "texte-131", 1, "confiance faible → " + A_VERIFIER)
note(6, "et signale ceux sur lesquels il hésite, qui passent alors à Gemini.",
     "et signale ceux sur lesquels il hésite, marqués « à vérifier ».")
note(7, "Quand le modèle hésite, l'avis part à l'API Gemini, qui sert aussi de point de comparaison.",
     "Quand le modèle hésite, l'avis est marqué « à vérifier » ; Gemini ne sert que de point de "
     "comparaison.")

# --- diapo 10 : séquence d'analyse, sans la ligne de vie Gemini
supprimer(10, "boite-232", "texte-233", "ligne-vie-234", "fleche-245", "fleche-247", "texte-248")
boucle = forme(10, "boucle-243")
boucle.width = int(914400 * 4.1)
boucle.height = int(914400 * 0.85)
forme(10, "texte-246").text_frame.paragraphs[0].runs[1].text = "confiance stockée · avis signalé « à vérifier »"
forme(10, "texte-246").top = int(914400 * 4.45)
r = forme(10, "texte-250").text_frame.paragraphs[0].runs
r[0].text = r[0].text.replace("7", "6")
r[1].text = "MERGE avis_analyses (confiance, version)"
fl, tx = forme(10, "fleche-249"), forme(10, "texte-250")
fl.top, tx.top = int(914400 * 5.29), int(914400 * 4.99)
note(10, "Si la confiance est sous un seuil, réglé sur le jeu de test, l'avis est envoyé à l'API "
         "Gemini, qui prend le relais.",
     "Si la confiance est sous un seuil, réglé sur la validation, l'avis est gardé mais signalé "
     "« à vérifier ».")

# --- diapo 12 : deux usages
cellule(12, 3, 1, "seuil de confiance : avis incertain signalé « à vérifier »")
cellule(12, 4, 1, "F1 face à Gemini sur 280 avis annotés à part")
note(12, "quand le modèle hésite, Gemini prend le relais.",
     "quand le modèle hésite, l'avis est signalé « à vérifier ».")

# --- diapo 13 : modèle de données
note(13, "et le modèle qui l'a produite, maison ou Gemini : c'est ce qui permet de comparer.",
     "et la version du modèle qui l'a produite : c'est ce qui permet de suivre et de réanalyser.")

# --- diapo 14 : sécurité
paragraphe(14, "texte-363", 0,
           "Secret Manager — jeton Apify et mot de passe SMTP lus à l'exécution, absents du code")
note(14, "jeton Apify, SMTP et la clé de l'API Gemini qui sert de relais —",
     "jeton Apify et SMTP —")

# --- diapo 15 : fiabilité
cellule(15, 5, 1, "résultat gardé avec sa confiance, signalé « à vérifier »")
cellule(15, 6, 0, "Job d'analyse en échec")
cellule(15, 6, 1, "alerte e-mail ; avis non analysés repris au passage suivant")
note(15, "Un avis sur lequel le modèle hésite part à Gemini ; si Gemini est indisponible, on garde "
         "le résultat maison en le marquant incertain.",
     "Un avis sur lequel le modèle hésite est gardé avec sa confiance et signalé « à vérifier ».")
note(15, "seuls Apify et les relais Gemini sont facturés", "seul Apify est facturé")

# --- diapo 17 : choix d'architecture
cellule(17, 7, 0, "NLP maison")
cellule(17, 7, 1, "confier l'analyse à l'API d'un LLM")
note(17, "notre propre modèle NLP plutôt que Gemini pour l'analyse : c'est la consigne, il ne coûte "
         "rien par avis, et Gemini reste là pour les cas incertains et pour mesurer l'écart.",
     "notre propre modèle NLP plutôt qu'une API de LLM pour l'analyse : c'est la consigne, il ne "
     "coûte rien par avis, et on mesure l'écart avec Gemini.")

# --- diapo 18 : chaîne NLP
paragraphe(18, "texte-443", 1, "étiquettes fines : sentiment, humeur, thèmes")
paragraphe(18, "texte-445", 0, "Test : 280 avis")
paragraphe(18, "texte-445", 1, "annotés à part · les plus récents, jamais vus à l'entraînement")
paragraphe(18, "texte-464", 1, "3 têtes de classification : sentiment, humeur, thèmes")
note(18, "Les avis d'entraînement sont étiquetés par Gemini ; 300 avis de test, de restaurants jamais "
         "vus à l'entraînement, sont annotés par nous deux séparément, et on mesure notre accord "
         "avec le kappa de Cohen.",
     "Les avis d'entraînement reçoivent des étiquettes fines ; 280 avis de test, les plus récents, "
     "jamais vus à l'entraînement, sont annotés à part.")

# --- diapo 19 : module NLP en détail
paragraphe(19, "texte-492", 1, "étiquettes fines → train · 280 avis de test à part")
paragraphe(19, "texte-537", 1, "F1, confusion, coût, latence sur 280 avis")
paragraphe(19, "texte-540", 1, "face à Gemini, analyse d'erreurs")
note(19, "puis annoter : Gemini annote l'entraînement, et nous annotons à deux les 300 avis de test, "
         "en mesurant notre accord avec le kappa de Cohen.",
     "puis annoter : étiquettes fines pour l'entraînement, et 280 avis de test annotés à part.")
note(19, "tous les modèles sont mesurés sur les 300 avis de test, comparés à CamemBERT et à Gemini,",
     "tous les modèles sont mesurés sur les 280 avis de test et comparés à Gemini,")

# --- diapo 21 : comparer, puis production
paragraphe(21, "texte-607", 0, "Mini-GPT")
paragraphe(21, "texte-607", 1, "étoiles seules")
paragraphe(21, "texte-643", 0, "Avis signalé « à vérifier »")
paragraphe(21, "texte-643", 1, "confiance enregistrée, visible au tableau de bord")
bq = next(sh for sh in S(21).shapes if sh.has_text_frame and "champ modele" in sh.text_frame.text)
paragraphe(21, bq.name, 0, "BigQuery avis_analyses · confiance et version du modèle")
paragraphe(21, bq.name, 1, "le tableau de bord met en avant les avis à vérifier")
mini = next(sh for sh in S(21).shapes if sh.has_text_frame and sh.text_frame.text.startswith("Mini-GPT\nmaison"))
paragraphe(21, mini.name, 1, "maison · version finale")
note(21, "le Bayes naïf, nos trois tailles de mini-GPT, CamemBERT comme référence ouverte, et Gemini.",
     "le Bayes naïf, nos versions du mini-GPT, et Gemini comme référence.")
note(21, "S'il est assez sûr de lui, on garde son résultat ; sinon, Gemini prend le relais via son API.",
     "S'il est assez sûr de lui, son résultat est utilisé tel quel ; sinon, l'avis est signalé "
     "« à vérifier » dans le tableau de bord.")

# --- diapo 24 : agent
par = forme(24, "texte-699").text_frame.paragraphs[1]
for run in par.runs:
    run.text = run.text.replace(" produites par Gemini", "")

# --- diapo 25 : limites
paragraphe(25, "texte-728", 0, "plus d'avis annotés, modèle plus grand sur GPU")
note(25, "un mini-GPT moins précis que Gemini, compensé par le relais,",
     "un mini-GPT moins précis que Gemini,")

# --- diapo 26 : questions du jury (notes)
note(26, "seuil de confiance avec relais Gemini,", "seuil de confiance avec signalement des avis incertains,")
note(26, "le seul poste qui croît est le relais Gemini, qu'on réduit en améliorant le modèle.",
     "le seul poste qui croît est la collecte Apify.")

p.save(OUT)
print("ok")
