# NLP maison — mode d'emploi

Tout se lance depuis la racine du dépôt avec `python -m nlp <commande>`.
Plan complet et justification : [`docs/plan-nlp-maison.md`](../docs/plan-nlp-maison.md).

| Où | Contenu |
|---|---|
| `app/watchmybusiness/nlp/` | ce qui part en production : tokenizer BPE, modèle, prédiction (`service.py`) |
| `nlp/` | entraînement, données, étiquetage Gemini, Bayes naïf, évaluation |
| `data/`, `modeles/` | fichiers produits (ignorés par git) |

## Installation (PC d'entraînement, RTX 3070 Ti)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install torch --index-url https://download.pytorch.org/whl/cu124
.venv\Scripts\pip install -r nlp\requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest tests\test_nlp.py
```

## Les étapes

### 1. Données

```powershell
gcloud auth application-default login
python -m nlp exporter                                # data/avis.jsonl (+ étiquettes Gemini déjà en base)
$env:GEMINI_API_KEY = "…"                             # clé AI Studio, pas Vertex
python -m nlp etiqueter data/avis.jsonl --limite 50   # essai sur 50 avis, vérifier le résultat
python -m nlp etiqueter data/avis.jsonl               # tout ; reprend où il s'est arrêté
python -m nlp decouper data/avis_etiquetes.jsonl      # train / val / test PAR RESTAURANT
```

Avant l'exporteur, il faut avoir collecté le corpus : ajouter les ~15 restaurants
dans `terraform.tfvars` (`max_avis` élevé), déployer, lancer la collecte.

### 2. Jeu de test « or » (annotation humaine)

```powershell
python -m nlp annoter -n 300           # data/annotation/annotation_A.csv et _B.csv
# chacun remplit SON fichier, sans regarder l'autre
python -m nlp kappa                    # accord par champ + data/annotation/desaccords.csv
# trancher les désaccords à deux dans une copie de A → annotation_finale.csv
python -m nlp importer data/annotation/annotation_finale.csv   # data/test_or.jsonl
```

### 3. Corpus et tokenizer

```powershell
pip install datasets
python -m nlp corpus --allocine 100000 --wikipedia-mo 300
python -m nlp tokenizer --taille 16000
```

### 4. Entraînement

```powershell
python -m nlp pretrain --taille S --pas 20000 --sortie modeles/pretrain-S.pt
python -m nlp finetune --init modeles/pretrain-S.pt --etape etoiles --sortie modeles/etoiles-S
python -m nlp finetune --init modeles/etoiles-S/modele.pt --sortie modeles/nlp-v1-S
```

Refaire avec `--taille M` puis `L`. Si la mémoire sature : `--lot 16 --accumulation 2`.
La spécialisation calibre le seuil de confiance sur la validation : en dessous,
l'avis part à Gemini en production.

### 5. Évaluation

```powershell
python -m nlp bayes
python -m nlp etiqueter data/test_or.jsonl --sortie data/gemini_test.jsonl
python -m nlp evaluer --maison modeles/nlp-v1-S modeles/nlp-v1-M modeles/nlp-v1-L --gemini data/gemini_test.jsonl
python -m nlp predire modeles/nlp-v1-S "Une heure d'attente mais le falafel est divin"
```

Le tableau est écrit dans `data/resultats.md`.

### 6. Production (cloud)

Si les analyses sont déjà dans BigQuery (`analyses_maison`, `avis_historique`) :

```powershell
# 1) Rapports hebdomadaires pour le tableau de bord (sans rappeler le modèle)
python -m nlp publier-cloud --semaines 52

# 2) Déployer le service web branché sur BigQuery
# terraform.tfvars : moteur_analyse = "maison", version_modele = "fallafel-v3+fallafel-v4"
.\deployer.ps1
terraform -chdir=terraform output tableau_de_bord
```

Pour activer aussi le job d'analyse quotidien avec le modèle maison :

```powershell
gcloud storage cp modeles/fallafel/nlp-S-duo/* gs://watch-my-business-512316-modeles/fallafel-v3+fallafel-v4/
# terraform.tfvars : moteur_analyse = "maison"
"cle_gemini" | gcloud secrets versions add gemini-api-key --data-file=-   # relais optionnel
.\deployer.ps1
```
