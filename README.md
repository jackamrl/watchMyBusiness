# WatchMyBusiness — rapport hebdomadaire de satisfaction client

Les avis Google Maps d'un établissement sont collectés chaque jour, analysés un
par un par Gemini, puis synthétisés chaque lundi par un agent Gemini en un
rapport lisible par le gérant. Tout tourne sur Google Cloud, sans serveur à
administrer et sans fichier manipulé à la main.

Établissement de démonstration : **L'As du Fallafel** (Paris, ~14 700 avis Google).

Architecture fonctionnelle et technique détaillée : [`docs/architecture.md`](docs/architecture.md).

```
Cloud Scheduler (chaque jour 06:00)
  └─▶ Workflows wmb-quotidien
        ├─1─▶ Job wmb-collecte   Apify ─▶ Cloud Storage (brut, immuable) ─▶ MERGE avis_bruts
        └─2─▶ Job wmb-analyse    avis non analysés ─▶ Gemini (JSON imposé) ─▶ avis_analyses

Cloud Scheduler (lundi 08:00)
  └─▶ Job wmb-rapport            KPI en SQL + agent Gemini outillé ─▶ rapports_hebdo (+ e-mail)

Service wmb-web (public)         page + API en lecture seule sur BigQuery
Looker Studio                    vues v_kpi_semaine, v_themes, v_avis
```

## Structure du dépôt

```
app/                     image Docker unique (jobs + service web)
  watchmybusiness/
    __main__.py          point d'entrée : collecte | rejouer | analyse | rapport | web
    apify.py             client Apify et normalisation des avis
    depot_brut.py        zone de dépôt Cloud Storage
    collecte.py          job collecte (et rejeu depuis le dépôt brut)
    gemini.py            analyse d'un avis : prompt, schéma, validation
    analyse.py           job analyse (parallélisme, réessais)
    rapport.py           job rapport : KPI SQL, outils et agent Gemini
    courriel.py          envoi SMTP facultatif
    web.py, static/      tableau de bord et son API
    entrepot.py          accès BigQuery (requêtes paramétrées, MERGE idempotent)
    config.py, secrets.py, taxonomie.py
terraform/               toute l'infrastructure GCP
tests/                   tests unitaires (sans accès réseau)
outils/diagnostic.py     essais locaux contre le vrai projet
deployer.ps1             déploiement de bout en bout
```

## Déployer

Prérequis : `gcloud` connecté, Terraform ≥ 1.6, un projet GCP avec facturation.

```powershell
Copy-Item terraform\terraform.tfvars.example terraform\terraform.tfvars   # à compléter
$env:APIFY_TOKEN = "apify_api_..."
.\deployer.ps1
```

Le script crée le bucket d'état Terraform, construit l'image par Cloud Build,
applique l'infrastructure et range le jeton Apify dans Secret Manager (une seule
fois ; `-RemplacerJetonApify` pour le changer et désactiver l'ancien).

## Exploiter

```powershell
gcloud workflows run wmb-quotidien --location europe-west1        # collecte + analyse
gcloud run jobs execute wmb-rapport --region europe-west1 --wait  # rapport de la semaine écoulée
gcloud run jobs execute wmb-rapport --region europe-west1 --wait --args="rapport,--date-fin,2026-10-18"
gcloud run jobs execute wmb-collecte --region europe-west1 --wait --args="rejouer,--prefixe,as-du-fallafel/"
terraform -chdir=terraform output tableau_de_bord                 # URL du tableau de bord
```

**Ajouter un établissement** : une entrée de plus dans `etablissements`
(`terraform.tfvars`), puis `.\deployer.ps1`. L'URL Maps doit contenir
l'identifiant de lieu `!1s0x…:0x…` : ouvrir le lien `maps.app.goo.gl` dans un
navigateur et copier l'URL finale.

**E-mail** (facultatif) : renseigner `smtp` dans `terraform.tfvars`, puis
`"mot-de-passe-application" | gcloud secrets versions add smtp-mot-de-passe --data-file=-`.

**Faire évoluer l'analyse** : modifier le prompt ou la taxonomie, incrémenter
`VERSION_PROMPT` dans `gemini.py`, redéployer. Le job d'analyse retraite tout
l'historique sous la nouvelle version, sans écraser l'ancienne : on peut comparer.

## Looker Studio

1. [lookerstudio.google.com](https://lookerstudio.google.com) → *Créer* → *Source de données* → **BigQuery**.
2. Projet `watch-my-business-512316` → dataset `watchmybusiness` → `v_kpi_semaine`, puis `v_themes` et `rapports_hebdo`.
3. Graphiques conseillés : `semaine` × `pct_positif` / `pct_negatif` ; `theme` × enregistrements filtré sur `polarite = negatif` ; tableau `semaine_id`, `tendance`, `synthese`.

## Développer

```powershell
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest                       # tests unitaires
.venv\Scripts\ruff check app tests outils            # lint
.venv\Scripts\python outils\diagnostic.py --help     # modeles | analyse | agent | web
```

Les outils de diagnostic utilisent les identifiants `gcloud auth application-default login`.

## Coût

100 avis collectés, 68 analysés, un rapport : quelques centimes (Apify et
Gemini). BigQuery, Cloud Storage, Cloud Run, Scheduler et Workflows restent dans
les quotas gratuits. Un budget de 5 € alerte par e-mail à 50 % et 100 %.
