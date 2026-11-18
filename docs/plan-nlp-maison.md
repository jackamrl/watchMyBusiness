# Remplacer Gemini par un NLP construit par nous

Ce document reprend l'architecture des diapos 18 à 24 de la soutenance et la
transforme en plan de travail concret : quelles données utiliser, quoi coder,
dans quel ordre, et comment le brancher sur le code existant.

Consigne de départ : pas de Vertex AI, un NLP fait main pour le sentiment exact
et l'humeur, comparé à Gemini, et un agent qui répond à une demande écrite
(« fais-moi une analyse de cette semaine sur l'attente »).

Validé : Gemini peut servir à étiqueter les données d'entraînement et de
référence pour la comparaison. Le code correspondant est dans `nlp/` (mode
d'emploi : [`nlp/README.md`](../nlp/README.md)).

---

## 1. Ce que Gemini fait aujourd'hui, et ce qui le remplace

| Où | Ce que fait Gemini aujourd'hui | Ce qui le remplace |
|---|---|---|
| `app/watchmybusiness/gemini.py` + `analyse.py` | classe chaque avis : sentiment, score, thèmes, extraits, actionnable, résumé | **classifieur maison** : Transformer fait main + têtes de sortie |
| `app/watchmybusiness/rapport.py` | agent qui rédige la synthèse du lundi avec 5 outils | **agent maison** : compréhension, outils SQL, rédaction par le mini-GPT, vérificateur |
| `Desktop/watchmybusiness/server.ts` `/api/watchy/chat` | répond aux questions du gérant | **le même agent maison**, appelé depuis le tableau de bord |
| `Desktop/watchmybusiness/server.ts` `/api/watchy/reply` | rédige une réponse à un avis | **mini-GPT spécialisé** sur les vraies réponses des propriétaires |

Gemini ne disparaît pas complètement : il reste la **référence de comparaison**,
il sert à **étiqueter les données d'entraînement**, et il peut prendre le
**relais** quand notre modèle hésite. Il passe par l'API Gemini publique, pas
par Vertex.

---

## 2. Les données : ce qu'on a gratuitement, ce qu'il faut produire

La qualité du modèle dépendra surtout de ce point. L'idée clé : **une grande
partie des étiquettes existe déjà dans les données Apify**, il suffit de les
exploiter.

### 2.1 Ce que donne Apify (`compass~google-maps-reviews-scraper`)

Chaque item brut est déjà stocké tel quel dans Cloud Storage et dans la colonne
`brut` de `avis_bruts`. On peut donc tout réexploiter sans repayer la collecte.

| Champ | Utilisation pour le NLP |
|---|---|
| `text` | le texte à analyser (entrée du modèle) |
| `stars` | **étiquette gratuite de sentiment** (supervision faible, voir 2.2) |
| `originalLanguage`, `textTranslated` | filtrer le français ; les traductions donnent plus de texte français |
| `responseFromOwnerText` | **paires avis → réponse du propriétaire** : données d'entraînement pour rédiger les réponses (Watchy) |
| `publishedAtDate` | découpage temporel, statistiques par semaine |
| notes détaillées (cuisine, service, ambiance) | **étiquettes gratuites de thèmes**, si l'acteur les fournit : à vérifier dans `brut` |

À faire en premier : ouvrir quelques items dans
`gs://<projet>-avis-brut/as-du-fallafel/…` et lister les champs réellement
présents. Ne rien supposer.

### 2.2 Supervision faible : les étoiles comme étiquette

| Étoiles | Étiquette faible |
|---|---|
| 1-2 | NEGATIF |
| 3 | NEUTRE ou MIXTE (ambigu) |
| 4-5 | POSITIF |

C'est bruité (un « 4 étoiles mais l'attente était horrible » est MIXTE), mais
c'est **gratuit et en grande quantité**. Usage prévu : une première étape de
spécialisation sur des dizaines de milliers d'avis, avant d'affiner sur les
étiquettes de meilleure qualité. On mesure aussi le désaccord étoiles / texte :
c'est un résultat intéressant en soi pour la soutenance.

### 2.3 Corpus à collecter

| Source | Volume visé | Rôle | Remarque |
|---|---|---|---|
| Apify, 15 restaurants variés | ~25 000 avis | corpus principal | varier les notes moyennes (pas que des 4,5★) pour avoir assez de négatifs ; vérifier le tarif de l'acteur avant |
| Wikipédia FR (extrait) | quelques centaines de Mo de texte | pré-entraînement : apprendre le français | dump public, libre |
| Allociné (Hugging Face `allocine`) | ~200 000 critiques, positif/négatif | pré-entraînement « opinion » en français | domaine différent (films), utile pour le vocabulaire de l'avis |
| Analyses Gemini déjà en base (`avis_analyses`) | tout ce qui a déjà été analysé | étiquettes riches gratuites | déjà produites par le pipeline actuel |
| Autres plateformes (TripAdvisor via Apify…) | optionnel | plus d'avis de restaurants | vérifier coût et conditions d'utilisation |

Pour l'humeur, il n'existe pas de bon jeu de données français public : elle
viendra de l'étiquetage Gemini et de votre annotation.

### 2.4 Les étiquettes à produire

| Jeu | Taille | Qui étiquette | Usage |
|---|---|---|---|
| **Train « argent »** | ~20 000 avis | Gemini (API publique), prompt et schéma de `gemini.py` + humeur | spécialisation |
| **Validation** | ~1 500 avis | Gemini | réglages, arrêt de l'entraînement, seuil de confiance |
| **Test « or »** | 300 avis | **vous deux, séparément** | évaluation finale ; mesurer votre accord (kappa de Cohen), arbitrer les désaccords |

Règle absolue : **les restaurants du test ne sont jamais vus à l'entraînement**.
Le découpage se fait par restaurant, pas par avis.

Guide d'annotation à écrire avant de commencer (1 page) : définition de chaque
sentiment, de chaque humeur, de chaque thème, avec 2 exemples chacun. Sans ce
guide, le kappa sera mauvais.

---

## 3. Ce que le modèle doit prédire

| Sortie | Valeurs | Type de tête |
|---|---|---|
| Sentiment | POSITIF · NEGATIF · NEUTRE · MIXTE | classification à 4 classes (softmax) |
| Confiance | 0 à 1 | probabilité de la classe choisie, calibrée |
| Humeur | joie · satisfaction · déception · frustration · colère · neutre (proposition) | classification à 6 classes |
| Thèmes | les 8 thèmes restaurant × {absent, positif, négatif, neutre} | 8 classifications à 4 classes |
| Actionnable | oui / non | règle : au moins un thème négatif corrigeable (ou une petite tête binaire) |

Extraits cités et résumé (que Gemini produit aujourd'hui) : abandonnés pour la
classification. Les citations du rapport seront choisies parmi les avis entiers
les plus représentatifs d'un thème.

---

## 4. Le modèle, pièce par pièce

Tout est codé en PyTorch, sans bibliothèque de modèles (pas de `transformers`).

1. **Tokenizer BPE** (`nlp/tokenizer/bpe.py`) : apprendre les fusions sur le
   corpus (Wikipédia + avis), vocabulaire de l'ordre de 8 000 à 16 000 jetons,
   à régler. Gérer les accents et les emojis (fréquents dans les avis).
2. **Embeddings** : jetons + positions (apprises), longueur de contexte 256
   jetons (assez pour la grande majorité des avis ; tronquer au-delà).
3. **Blocs Transformer** (`nlp/modele/`) : attention multi-têtes masquée
   (causale), MLP, LayerNorm, connexions résiduelles. Trois tailles :

   | Taille | Couches | Dimension | Têtes | ≈ Paramètres |
   |---|---|---|---|---|
   | S | 4 | 256 | 4 | ~7 M |
   | M | 6 | 448 | 7 | ~22 M |
   | L | 8 | 640 | 10 | ~50 M |

   (ordres de grandeur, à recalculer selon la taille du vocabulaire)

4. **Têtes de sortie** (`nlp/modele/tetes.py`) : une couche linéaire par sortie,
   branchée sur la représentation du dernier jeton (ou la moyenne des jetons ;
   comparer les deux).

**Pourquoi un modèle de type GPT plutôt qu'un encodeur type BERT ?** Pour la
classification seule, un encodeur bidirectionnel est en général meilleur. On
garde le GPT parce que **le même modèle sert aussi à rédiger** (agent et
réponses aux avis). C'est un compromis à assumer et à mesurer.

---

## 5. L'entraînement, étape par étape

Matériel : RTX 3070 Ti Laptop (8 Go). Précision mixte (bf16 ou fp16),
accumulation de gradient pour simuler de plus gros lots.

| Étape | Données | Tâche | Durée indicative |
|---|---|---|---|
| 1. Pré-entraînement langue | Wikipédia FR | prédire le mot suivant | 1 à 3 h par taille |
| 2. Pré-entraînement domaine | avis Apify + Allociné | prédire le mot suivant | ~1 h |
| 3. Spécialisation faible | ~25 000 avis + étoiles | sentiment depuis les étoiles | < 1 h |
| 4. Spécialisation fine | train « argent » Gemini | toutes les têtes (pertes additionnées) | < 1 h |
| 5. Rédaction | paires faits → synthèse, avis → réponse | prédire le mot suivant sur ces paires | < 1 h |

Pertes de l'étape 4 : entropie croisée pour le sentiment, l'humeur et chaque
thème ; poids de classes pour compenser le déséquilibre (beaucoup de positifs).

Suivi : courbes de perte entraînement / validation, points de sauvegarde, et
graine aléatoire fixée pour que les résultats soient reproductibles.

---

## 6. L'évaluation : la partie qui compte le plus

Tous les modèles sur **le même test « or » de 300 avis** :

| Modèle | Rôle |
|---|---|
| Bayes naïf codé en numpy | plancher : tout doit faire mieux |
| Notre GPT, tailles S, M, L | le travail du projet |
| CamemBERT affiné | référence ouverte (montre ce qu'un bon modèle pré-entraîné atteint) |
| Gemini | la référence haute |

Mesures : F1 macro par sortie (sentiment, humeur, thèmes), matrice de
confusion, coût pour 1 000 avis, latence, et **analyse des erreurs** (ironie,
négation, avis mixtes, langues étrangères). Bonus : courbe « qualité selon la
taille du modèle » et « qualité selon la quantité de données ».

Message pour la soutenance : **le modèle ne battra pas Gemini, ce n'est pas le
but**. On mesure l'écart, ce qu'il coûte de le réduire, et à partir de quand un
modèle maison suffit.

---

## 7. L'agent maison (remplace l'agent Gemini et Watchy)

Pour une demande comme « fais-moi une analyse de cette semaine sur l'attente » :

1. **Comprendre** (`nlp/agent/intention.py`) : petit classifieur d'intention
   (Bayes naïf ou tête sur notre modèle) parmi une dizaine d'intentions
   (`resume_semaine`, `analyse_theme`, `comparer`, `top_problemes`,
   `repondre_avis`…). Données : 500 à 1 000 demandes écrites par vous puis
   reformulées. Extraction par règles : période (« cette semaine », « le mois
   dernier », dates), thème (lexique de synonymes : « queue », « attendre » →
   `attente`), établissement.
2. **Planifier** (`planificateur.py`) : pour chaque intention, la liste des
   outils à appeler (table de règles, pas de modèle).
3. **Outils** (`outils.py`) : les requêtes SQL qui existent déjà dans
   `rapport.py` (`Donnees.kpi`, `comparaison`, `citations`, `actionnables`,
   `emergents`) + une requête « humeurs de la période ». À réutiliser, pas à
   réécrire.
4. **Faits** : un JSON qui rassemble tous les chiffres. Seule source autorisée.
5. **Rédiger** : notre mini-GPT, affiné sur des paires faits → texte. Données :
   les synthèses déjà dans `rapports_hebdo`, plus quelques milliers de paires
   générées par Gemini à partir de faits variés (distillation). Pour la
   comparaison, Gemini rédige aussi à partir des mêmes faits.
6. **Vérifier** (`verificateur.py`) : chaque nombre du texte doit figurer dans
   les faits ; sinon, on remplace par un **gabarit** (texte à trous rempli avec
   les faits). L'agent ne peut donc jamais publier un chiffre faux.

Réponses aux avis (Watchy) : mini-GPT affiné sur les paires
`text` → `responseFromOwnerText` collectées par Apify, avec le ton en entrée.

Attente réaliste : un modèle de 45 M de paramètres rédige des textes courts et
assez répétitifs. Le gabarit garantit un résultat correct ; la comparaison avec
Gemini montre honnêtement l'écart.

---

## 8. Brancher le modèle sur le pipeline GCP

| Élément | Changement |
|---|---|
| `analyse.py` | remplacer l'appel `gemini.analyser(...)` par `nlp.service.predire(...)`, qui renvoie **le même format de dictionnaire** ; le reste du job (MERGE, lots) ne change pas |
| Relais | si `confiance < seuil`, appeler Gemini (API publique, clé dans Secret Manager) ; colonne `modele` = `maison` ou `gemini` (elle existe déjà) |
| `avis_analyses` (`terraform/bigquery.tf`) | ajouter `humeur` (STRING) et `confiance` (FLOAT64) ; `version_prompt` contient désormais la version du modèle (`nlp-v1`) |
| Poids | fichier déposé dans Cloud Storage (`gs://<projet>-modeles/nlp-v1/`), chargé au démarrage du job |
| Image Docker | ajouter PyTorch **version CPU** (pas CUDA) ; passer le job à 2 Gi de mémoire |
| IAM | `wmb-pipeline` : lecture du bucket modèles ; retirer `aiplatform.user` (plus de Vertex) |
| `rapport.py` | remplacer `rediger()` par l'agent maison |
| Watchy | `/api/watchy/chat` et `/reply` appellent un point d'entrée de `wmb-web` qui utilise l'agent maison |

L'entraînement se fait **en local sur la RTX 3070 Ti**, pas sur GCP : seul le
modèle entraîné part en production, sur CPU.

---

## 9. Organisation du code

```
nlp/
  donnees/       collecte · nettoyage · decoupage · annotation · etoiles
  tokenizer/     bpe.py
  modele/        attention · transformer · tetes
  entrainement/  pretrain · finetune · redaction
  evaluation/    bayes_naif · metriques · comparer · erreurs
  service/       predire.py  (utilisé par wmb-analyse)
  agent/         intention · planificateur · outils · verificateur · gabarits
  tests/
```

---

## 10. Planning (10 semaines, indicatif)

| Sem. | Lot | Livrable |
|---|---|---|
| S1 | Corpus | ~25 000 avis en base, champs Apify inventoriés |
| S2 | Annotation | guide d'annotation, 300 avis test annotés, kappa, étiquetage Gemini lancé |
| S3 | Bayes naïf | plancher mesuré sur le test |
| S4 | Tokenizer BPE | tokenizer entraîné et testé |
| S5 | Transformer | modèle qui apprend (perte qui baisse sur un petit corpus) |
| S6 | Pré-entraînement | 3 tailles pré-entraînées |
| S7 | Spécialisation | têtes entraînées, premiers F1 |
| S8 | Évaluation | tableau comparatif complet, analyse d'erreurs |
| S9 | Production + agent | `analyse.py` branché, agent maison dans `rapport.py` et Watchy |
| S10 | Restitution | rapport final, démonstration côte à côte |

Répartition possible dans le binôme : l'un porte données + évaluation, l'autre
modèle + entraînement ; l'agent et la mise en production se font à deux.

---

## 11. Risques et parades

| Risque | Parade |
|---|---|
| Pas assez d'avis négatifs | choisir des restaurants avec des notes moyennes variées ; poids de classes |
| Étiquettes Gemini fausses | elles servent à l'entraînement seulement ; l'évaluation repose sur votre test « or » |
| Kappa faible entre vous deux | guide d'annotation avec exemples, séance d'alignement sur 30 avis avant de commencer |
| Entraînement trop long ou mémoire saturée (8 Go) | commencer par la taille S, précision mixte, accumulation de gradient, contexte de 256 |
| Rédaction de mauvaise qualité | gabarit de secours ; le présenter comme une limite mesurée |
| Coût Apify pour 25 000 avis | vérifier le tarif de l'acteur avant ; commencer à 5 restaurants |
| Interdiction totale de Gemini par la prof | étiquetage par vous + étoiles uniquement ; Gemini retiré du relais |

---

## 12. Premières actions

1. Faire valider ce plan par la prof (en particulier : Gemini autorisé pour
   étiqueter et comparer ?).
2. Inventorier les champs des items Apify déjà collectés.
3. Choisir les 15 restaurants (URL Maps avec identifiant `!1s0x…:0x…`) et les
   ajouter dans `etablissements` (`terraform.tfvars`).
4. Lancer la collecte à grande échelle (augmenter `max_avis`).
5. Écrire le guide d'annotation.
