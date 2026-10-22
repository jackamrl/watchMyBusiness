<#
.SYNOPSIS
Déploie WatchMyBusiness sur GCP : état Terraform, image, infrastructure, secrets.

.DESCRIPTION
1. Bucket d'état Terraform (versionné) si absent.
2. Terraform, première passe : API + dépôt Artifact Registry.
3. Construction de l'image par Cloud Build (aucun Docker local requis).
4. Terraform, passe complète : stockage, BigQuery, jobs, service web, Workflows,
   Scheduler, alertes, budget.
5. Jeton Apify déposé dans Secret Manager depuis $env:APIFY_TOKEN, seulement si
   le secret est vide ou avec -RemplacerJetonApify (l'ancienne version est alors
   désactivée).

.EXAMPLE
$env:APIFY_TOKEN = "apify_api_..."
.\deployer.ps1

.EXAMPLE
$env:APIFY_TOKEN = "apify_api_nouveau"
.\deployer.ps1 -RemplacerJetonApify
#>
param(
    [string]$Projet = "watch-my-business-512316",
    [string]$Region = "europe-west1",
    [string]$Tag = (Get-Date -Format "yyyyMMdd-HHmmss"),
    [switch]$RemplacerJetonApify
)

# gcloud écrit ses messages d'information sur stderr : sous Windows PowerShell,
# "Stop" les transformerait en erreurs fatales. On contrôle $LASTEXITCODE à la place.
$ErrorActionPreference = "Continue"
$racine = $PSScriptRoot
$dossierTf = Join-Path $racine "terraform"

function Etape([string]$texte) { Write-Host "`n==> $texte" -ForegroundColor Cyan }
function Verifier([string]$quoi) { if ($LASTEXITCODE -ne 0) { throw "$quoi a échoué (code $LASTEXITCODE)." } }

gcloud config set project $Projet --quiet 2>$null | Out-Null

Etape "API socle (nécessaires à Terraform pour activer les autres)"
gcloud services enable cloudresourcemanager.googleapis.com serviceusage.googleapis.com storage.googleapis.com --project $Projet
Verifier "Activation des API socle"

Etape "Bucket d'état Terraform"
$bucket = "$Projet-tfstate"
gcloud storage buckets describe "gs://$bucket" --format="value(name)" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    gcloud storage buckets create "gs://$bucket" --project $Projet --location $Region --uniform-bucket-level-access --public-access-prevention
    Verifier "Création du bucket d'état"
    gcloud storage buckets update "gs://$bucket" --versioning; Verifier "Versioning du bucket"
}

Push-Location $dossierTf
try {
    Etape "terraform init"
    terraform init -input=false -reconfigure -backend-config="bucket=$bucket"; Verifier "terraform init"

    Etape "Première passe : API et dépôt d'images"
    terraform apply -input=false -auto-approve -var "image_tag=$Tag" `
        -target="google_project_service.apis" `
        -target="google_artifact_registry_repository.depot"
    Verifier "terraform apply (amorçage)"
}
finally { Pop-Location }

Etape "Construction de l'image ($Tag) par Cloud Build"
$image = "$Region-docker.pkg.dev/$Projet/watchmybusiness/pipeline:$Tag"
gcloud builds submit (Join-Path $racine "app") --tag $image --region $Region --project $Projet --quiet
Verifier "Cloud Build"

Push-Location $dossierTf
try {
    Etape "Passe complète"
    terraform apply -input=false -auto-approve -var "image_tag=$Tag"; Verifier "terraform apply"
    $sorties = terraform output -json | ConvertFrom-Json
}
finally { Pop-Location }

$versionsActives = gcloud secrets versions list apify-token --project $Projet --filter="state=ENABLED" --format="value(name)" 2>$null
if ($env:APIFY_TOKEN -and ($RemplacerJetonApify -or -not $versionsActives)) {
    Etape "Jeton Apify -> Secret Manager"
    $env:APIFY_TOKEN | gcloud secrets versions add apify-token --data-file=- --project $Projet
    Verifier "Ajout du secret"
    foreach ($ancienne in $versionsActives) {
        gcloud secrets versions disable $ancienne --secret apify-token --project $Projet --quiet 2>$null | Out-Null
    }
}
elseif (-not $versionsActives) {
    Write-Host "`nATTENTION : aucun jeton Apify. Définissez `$env:APIFY_TOKEN puis relancez," -ForegroundColor Yellow
    Write-Host "ou : `"apify_api_...`" | gcloud secrets versions add apify-token --data-file=-" -ForegroundColor Yellow
}

Etape "Déployé"
Write-Host "  image    : $($sorties.image.value)"
Write-Host "  dataset  : $($sorties.dataset.value)"
Write-Host "  workflow : $($sorties.workflow.value)"
Write-Host "  tableau  : $($sorties.tableau_de_bord.value)"
Write-Host ""
Write-Host "Premier passage manuel :" -ForegroundColor Yellow
Write-Host "  gcloud workflows run wmb-quotidien --location $Region"
Write-Host "  gcloud run jobs execute wmb-rapport --region $Region --wait"
