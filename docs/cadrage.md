# Document de cadrage — WatchMyBusiness

**Analyse automatique de la satisfaction client par agrégation hebdomadaire d'avis textuels**

Produit **WatchMyBusiness** — module cloud avancé avec apprentissage automatique, architecture AWS serverless
Cas d'étude : *NordicHome*, e-commerce de mobilier et décoration (entreprise fictive)

---

## 1. Contexte

Une PME du commerce en ligne reçoit des avis clients en continu : formulaires
après-achat, marketplaces, réseaux sociaux, tickets de support. Quelques dizaines
par semaine, quelques centaines par mois. Un volume à la fois trop important pour
être lu intégralement par un responsable, et trop faible pour justifier le
recrutement d'un data scientist ou l'achat d'une plateforme d'analyse spécialisée.

Le résultat est une situation très répandue. Les avis sont archivés dans un
tableur ou un back-office. On les consulte quand un client se plaint fort, ou
lors d'un bilan trimestriel. Entre-temps, l'information qu'ils contiennent n'est
pas exploitée. Un problème de transporteur qui s'installe sur trois semaines
peut passer inaperçu jusqu'à ce qu'il se traduise dans le chiffre d'affaires.

Deux constats motivent ce projet.

**Le premier est que la valeur d'un avis isolé est faible.** Savoir qu'un client
donné est mécontent permet, au mieux, de traiter son cas. Cela ne dit rien de
l'entreprise. En revanche, savoir que 46 % des avis de la semaine sont négatifs
et que le motif dominant est le retard de livraison est une information sur
laquelle un responsable peut agir : appeler le transporteur, renforcer une
équipe, ajuster les délais annoncés.

**Le second est que le coût d'entrée dans l'analyse de texte a chuté.** Les
services managés de traitement du langage — Amazon Comprehend en l'occurrence —
fournissent une analyse de sentiment et une extraction de termes saillants par
un simple appel d'API, sans modèle à entraîner, sans jeu d'entraînement à
constituer, sans GPU. Ce qui relevait d'un projet de plusieurs mois il y a
quelques années est devenu une brique d'infrastructure.

## 2. Problématique

> **Comment une entreprise dépourvue d'expertise en science des données et
> d'infrastructure dédiée peut-elle savoir automatiquement, sur une période
> donnée, si ses clients ont été globalement satisfaits, et identifier ce qui a
> bien fonctionné et ce qui a posé problème ?**

Trois exigences se dégagent de cette formulation, et elles structurent tout le
projet.

**« Automatiquement »** — aucune intervention humaine entre l'arrivée d'un avis
et la mise à disposition de la synthèse. Ni script à lancer, ni fichier à
exporter, ni tableau croisé dynamique à rafraîchir.

**« Sur une période donnée »** — c'est l'exigence centrale, et celle qu'il est
le plus facile de manquer. Le livrable n'est pas une analyse avis par avis, mais
une **agrégation périodique**. La question du dirigeant n'est pas « que pense ce
client ? » mais « comment s'est passée la semaine ? ».

**« Identifier ce qui a bien fonctionné et ce qui a posé problème »** — au-delà
du chiffre global, il faut faire ressortir les **thèmes récurrents**, séparément
pour le positif et pour le négatif. Un pourcentage seul indique qu'il y a un
problème ; il ne dit pas lequel.

### 2.1 Ce que le projet n'est pas

Il est utile de délimiter par la négative.

Ce n'est **pas un classifieur de sentiment**. La classification existe dans la
chaîne, mais elle est un moyen, pas une fin — et elle est déléguée à un service
managé. Le travail original du projet se situe en aval : dans l'agrégation.

Ce n'est **pas un outil de réponse aux avis**. Aucune boucle vers le client n'est
prévue. L'objet est le pilotage, pas la relation client individuelle.

Ce n'est **pas un entraînement de modèle**. Aucun corpus d'entraînement, aucune
validation croisée, aucun hyperparamètre. La composante ML est consommée comme
un service. Ce choix est discuté en section 6.

## 3. Réponse apportée

Une chaîne entièrement *serverless* sur AWS, structurée en **deux traitements de
nature différente** — cette séparation est la décision d'architecture centrale
du projet.

### 3.1 Chaîne temps réel : analyser

À chaque avis déposé, une fonction Lambda est déclenchée. Elle appelle Amazon
Comprehend pour obtenir le sentiment et les phrases clés, puis écrit le résultat
dans une table DynamoDB. Traitement unitaire, événementiel, dont le résultat
n'est qu'un état intermédiaire.

### 3.2 Chaîne périodique : synthétiser

Chaque lundi à 8h00, une seconde fonction relit les avis des sept jours écoulés
et produit un rapport : proportions de positifs, négatifs et neutres, tendance
qualifiée, volume par jour, comparaison avec la semaine précédente, et surtout
**palmarès des thèmes récurrents positifs et négatifs, illustrés par des extraits
d'avis réels**. Le rapport est stocké, puis envoyé par e-mail au responsable.

### 3.3 Pourquoi cette séparation est structurante

Elle ne relève pas du confort d'organisation. Elle a une conséquence économique
directe : **le rejeu de l'agrégation est gratuit, celui de l'analyse ne l'est
pas.** Comprehend est facturé à l'appel ; relire DynamoDB ne coûte
quasiment rien.

Concrètement, la détection des thèmes est effectuée au moment de l'agrégation et
non au moment de l'ingestion. Faire évoluer le vocabulaire métier — ajouter un
thème « problème de montage », affiner la détection des retards — se fait en
modifiant quelques expressions régulières et en relançant la Lambda
d'agrégation. Tout l'historique est réinterprété, sans repasser un seul avis
dans Comprehend.

Si la détection avait été figée à l'ingestion, chaque ajustement du vocabulaire
aurait imposé de retraiter l'intégralité du corpus, à plein tarif.

## 4. Architecture

Le schéma détaillé, le rôle de chaque service et la justification de chaque
choix figurent dans **[`architecture.md`](architecture.md)**. Synthèse :

| Étape | Service | Rôle |
|---|---|---|
| Dépôt | **S3** (`incoming/`) | réception des avis bruts |
| Analyse | **Lambda** `traiter-avis` | orchestration de l'appel ML |
| ML | **Amazon Comprehend** | sentiment + phrases clés, en français |
| Stockage unitaire | **DynamoDB** `Avis` | avis analysés, index par mois |
| Planification | **EventBridge Scheduler** | déclenchement hebdomadaire |
| Agrégation | **Lambda** `generer-rapport-hebdo` | statistiques + thèmes récurrents |
| Stockage synthèse | **DynamoDB** `Rapports` | un élément par semaine |
| Notification | **SES** | e-mail de synthèse HTML |
| API | **API Gateway** (HTTP API) | `GET /rapports`, `GET /avis` |
| Authentification | **Cognito** | accès réservé aux managers |
| Interface | **S3** hébergement statique | tableau de bord |
| Supervision | **CloudWatch** + **SNS** | journaux, métriques, alarmes |

### 4.1 Trois décisions à retenir

**Extraction des thèmes : lexique métier plutôt que classement brut des phrases
clés.** Comprehend renvoie « le colis », « la porte cassée », « une charnière
arrachée » — trois formulations d'un même problème. Un classement direct
produirait une liste plate, illisible, et surtout incomparable d'une semaine à
l'autre puisque les formulations changent. Les phrases clés sont donc
normalisées (minuscules, accents, élisions, déterminants) puis projetées sur six
thèmes stables définis par des motifs. Ce sont ces thèmes qui sont comptés,
classés et suivis dans le temps.

**Le sentiment fait autorité sur la polarité déclarée.** Chaque thème porte une
polarité *attendue*, mais elle ne sert qu'à l'affichage. Le rangement d'un thème
dans le palmarès positif ou négatif dépend exclusivement du sentiment que
Comprehend a attribué à l'avis qui le porte. Un avis négatif évoquant la qualité
produit fera remonter « Qualité des produits » du côté négatif — et c'est
précisément l'information utile : quelque chose s'est dégradé.

**Index secondaire plutôt que `Scan`.** L'agrégation interroge un index
`avis-par-mois` (partition `mois`, tri `date`). Un `Scan` lirait tout
l'historique à chaque exécution, avec un coût croissant sans fin, alors que la
fenêtre analysée reste de sept jours. Le partitionnement mensuel évite par
ailleurs la partition chaude qu'induirait une clé constante.

## 5. Jeu de données et validation

### 5.1 Composition

28 avis synthétiques en français, du lundi 17 au dimanche 23 août 2026
(semaine ISO `2026-W34`), à raison de quatre par jour. Format
`{avis_id, date, client_id, texte}`, disponible en JSON et en 28 fichiers `.txt`
prêts pour le dépôt S3.

| Polarité annotée manuellement | Nombre | Part |
|---|---|---|
| Négatif | 13 | 46 % |
| Positif | 11 | 39 % |
| Neutre | 3 | 11 % |
| Mitigé | 1 | 4 % |

Les proportions ont été choisies pour produire une **semaine dégradée mais non
catastrophique** — le cas le plus intéressant à démontrer, puisqu'il donne une
tendance « mitigée » et oblige à regarder les thèmes pour comprendre.

### 5.2 Thèmes injectés volontairement

Trois motifs négatifs et trois motifs positifs sont répartis dans le corpus, avec
des formulations volontairement variées d'un avis à l'autre, pour vérifier que
l'agrégation les regroupe malgré les différences de vocabulaire.

| Négatif | Positif |
|---|---|
| Retards de livraison | Accueil en boutique |
| Colis et produits endommagés | Réactivité du service client |
| Service après-vente difficile à joindre | Qualité des produits |

Chaque avis porte un champ `themes_attendus` : une annotation manuelle qui sert
de référence. Ce champ n'est jamais envoyé à AWS et n'est jamais lu par les
Lambdas — il n'existe que pour la validation.

### 5.3 Validation

**Simulation hors ligne.** `scripts/simulation_locale.py` exécute la chaîne
d'agrégation complète sans qu'aucune ressource AWS n'existe, et compare les
thèmes détectés aux thèmes annotés.

> Thèmes injectés volontairement : 31
> Thèmes retrouvés par le lexique : 31 — **rappel 100 %**
> Thèmes détectés en plus : 2

Les deux détections supplémentaires portent toutes deux sur `AV019`, un avis
neutre (« livrée dans les délais annoncés ») dont le mot « délais » active le
motif du thème « Retards de livraison ». Sans conséquence sur le rapport, les
avis neutres n'alimentant aucun palmarès — mais c'est une limite réelle,
discutée en section 7.

**Tests automatisés.** 41 tests couvrent la normalisation du français, la
détection de chaque thème, le découpage des fenêtres temporelles à cheval sur
deux mois, le calcul de la tendance, le comportement sur corpus vide, la
convention de nommage des fichiers et la troncature UTF-8 aux limites de
Comprehend. Un test verrouille en particulier le fait que le classement suit le
sentiment détecté et non la polarité déclarée.

**Concordance avec Comprehend.** Lancé avec `--comprehend`, le même script
appelle réellement le service et mesure l'écart entre l'annotation manuelle et la
prédiction du modèle. C'est le chiffre à produire pour répondre à « comment
savez-vous que ça marche ? ».

## 6. Pertinence de l'approche

### 6.1 Ce que l'architecture apporte

**L'adéquation du serverless au profil de charge est totale.** Le trafic est
irrégulier et globalement faible : quelques dizaines d'avis par semaine, une
exécution hebdomadaire, une poignée de consultations. Un serveur, même petit,
serait allumé et facturé 168 heures par semaine pour quelques secondes de calcul
utile. Ici, l'absence d'avis coûte exactement zéro.

**Le coût est négligeable.** L'estimation détaillée (section 5 de
`architecture.md`) donne un coût nul sur la durée du projet grâce au free tier,
et de l'ordre de quelques dizaines de centimes par mois au-delà, pour 500 avis
mensuels. À comparer au coût d'une licence d'outil d'analyse d'avis, qui se
compte en centaines d'euros par mois.

**Le ML managé lève la barrière d'entrée.** Aucun corpus annoté à constituer,
aucun modèle à entraîner, aucun réentraînement à planifier, aucune infrastructure
d'inférence à maintenir. Comprehend prend en charge le français nativement. Cela
répond directement au « sans expertise data science » de la problématique.

**Le passage à l'échelle est acquis sans modification.** Passer de 30 à 3 000
avis par semaine ne demande aucun changement : Lambda parallélise, DynamoDB à la
demande absorbe, l'index par mois évite la partition chaude. Seul le coût
Comprehend croît, linéairement.

**L'exploitabilité est réelle.** Le manager reçoit un e-mail. Il n'a rien à
installer, rien à lancer. S'il veut creuser, un tableau de bord lui donne le
détail. C'est la condition pour que l'outil soit effectivement utilisé.

### 6.2 Ce que l'approche coûte

**Un couplage fort à AWS.** Comprehend, Lambda, DynamoDB et EventBridge Scheduler
n'ont pas d'équivalent portable. Migrer signifierait réécrire. Assumé : pour une
PME sans équipe technique, la dépendance à un fournisseur est un moindre mal
comparée à la charge d'exploitation d'une solution auto-hébergée.

**Une opacité du modèle.** Comprehend est une boîte noire. On ne peut ni
inspecter ses décisions, ni le spécialiser sur le vocabulaire du mobilier. La
mesure de concordance avec l'annotation manuelle est la seule prise disponible.
Comprehend Custom Classification permettrait de spécialiser un modèle — au prix
d'un corpus annoté de plusieurs centaines d'avis, ce que la problématique
exclut par construction.

**Un lexique métier à maintenir.** Les six thèmes sont propres à NordicHome. Les
transposer demande de les réécrire. C'est un travail métier — quelques heures
avec un responsable du service client — mais c'est un travail réel, et il devra
être refait quand le vocabulaire des clients évoluera.

### 6.3 Alternatives écartées

| Alternative | Motif du rejet |
|---|---|
| Modèle entraîné sur mesure (BERT, CamemBERT) | demande un corpus annoté et une infrastructure d'inférence ; contredit frontalement l'hypothèse « sans expertise data science » |
| Détection de sujets non supervisée (LDA, clustering d'embeddings) | sur quelques dizaines d'avis, produit des groupes instables, sans nom lisible, et non comparables d'une semaine à l'autre — or la comparabilité est l'objet même du livrable |
| Comprehend Topic Modeling | tâche asynchrone, conçue pour de gros lots ; pertinente au-delà de quelques milliers d'avis, surdimensionnée ici |
| Amazon QuickSight comme interface | facturé par utilisateur, et l'assemblage des thèmes récurrents y serait malaisé |
| Conteneurs sur ECS Fargate | facturés à la durée d'exécution, sans intérêt pour une charge de quelques secondes par semaine |

## 7. Limites et perspectives

**La négation n'est pas traitée.** L'approche par motifs ne distingue pas
« retard de livraison » de « aucun retard de livraison ». Le filtrage par
sentiment limite les dégâts — un avis positif ne peut pas remonter dans le
palmarès négatif — mais la limite est réelle. Une analyse syntaxique
(Comprehend fournit `detect_syntax`) permettrait de détecter les portées de
négation, au prix d'un appel supplémentaire par avis.

**Le volume de validation est faible.** 28 avis suffisent à démontrer le
mécanisme, pas à mesurer une performance statistiquement fondée. Un intervalle
de confiance sur un rappel calculé sur 31 occurrences est très large.

**Une seule langue.** `LanguageCode='fr'` est figé. `detect_dominant_language`
permettrait un routage automatique, pour une unité Comprehend supplémentaire par
avis.

**Pas de détection d'anomalie.** Le rapport compare à la semaine précédente mais
n'alerte pas sur une dégradation brutale. Un seuil — par exemple une chute de 15
points d'avis positifs — pourrait déclencher une notification immédiate sans
attendre le lundi.

**Le tableau de bord est servi en HTTP.** CloudFront avec Origin Access Control
apporterait HTTPS et permettrait de rendre le bucket privé.

## 8. Conclusion

La problématique posait trois exigences : automatisation intégrale, agrégation
sur une période, et identification des thèmes récurrents dans les deux polarités.
L'architecture y répond, et la démonstration le vérifie sur un cas complet :
28 avis déposés sur S3 produisent, sans aucune intervention, un rapport
hebdomadaire indiquant une tendance mitigée à 46 % d'avis négatifs, dominée par
les retards de livraison, tandis que la qualité produit et l'accueil en boutique
ressortent du côté positif.

La pertinence de l'approche tient moins à la sophistication des composants qu'à
leur agencement. Aucune brique n'est difficile prise isolément : Comprehend est
un appel d'API, Lambda une fonction, DynamoDB une table. Ce qui fait la solution,
c'est la **séparation entre analyse unitaire et synthèse périodique**, qui rend
le rejeu de l'agrégation gratuit et permet de faire évoluer la lecture métier
sans jamais repayer l'analyse.

Le point de vigilance principal porte sur l'extraction des thèmes. Le lexique
fonctionne — rappel de 100 % sur le corpus de test — mais il est écrit à la main
et ne comprend pas la négation. C'est le maillon à consolider en priorité si le
projet devait dépasser le cadre de la démonstration.

Pour une PME recevant quelques centaines d'avis par mois, sans équipe technique
et sans budget d'outillage, cette architecture délivre une information
directement actionnable pour un coût réel de quelques dizaines de centimes par
mois. C'est ce rapport entre la valeur produite et le coût d'exploitation qui
fonde la pertinence de l'approche.

---

### Annexes

| Document | Contenu |
|---|---|
| [`architecture.md`](architecture.md) | schéma détaillé, rôle et justification de chaque service, estimation de coût |
| [`deploiement.md`](deploiement.md) | prérequis, déploiement pas à pas, dépannage |
| [`soutenance.md`](soutenance.md) | plan du support, déroulé de la vidéo, questions anticipées |
| `data/avis_test.json` | jeu de données annoté |
| `tests/` | 41 tests automatisés |
