# WatchMyBusiness — tableau de bord

Tableau de bord de satisfaction client de **L'As du Fallafel** : les vrais avis Google Maps et
TripAdvisor, chacun classé par **notre propre modèle NLP** (Transformer entraîné de zéro) :
sentiment, humeur, thèmes et confiance. Aucune donnée inventée, aucun modèle externe.

- **Rapport du lundi** : synthèse factuelle de la semaine (mêmes règles que le rapport e-mail).
- **Humeur des clients** et **avis à vérifier** (confiance du modèle sous son seuil).
- **Thèmes** positifs / négatifs, évolution sur 12 semaines, flux d'avis filtrable.
- **Watchy** : assistant à règles qui répond uniquement à partir des chiffres de la semaine
  et cite les avis concernés (`AV-0042`).

## Lancer

```bash
npm install
npm run dev        # http://localhost:3000
```

## Mettre à jour les données

Les données sont produites par le module NLP du dépôt (modèle `nlp-S-duo`), depuis la
racine de `watchMyBusiness` :

```bash
.venv/bin/python -m nlp tableau-demo
cp data/demo/tableau.json frontend/src/data/donnees-modele.json
```
