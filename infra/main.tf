# The estimate site: the models in estimate/ as marimo notebooks exported to
# WebAssembly, with Pyodide and every wheel they load, served as static files by
# nginx on Cloud Run behind Google's login (IAP), at estimate.sustenaut.eu. The
# models run in the reader's browser; the service reads nothing at run time, so
# it runs as an account with no roles. .github/workflows/deploy.yml builds and
# deploys it on each merge to main.
#
# Who may open the site, its domain and its DNS are Sustenaut/shared-infra's. This
# stack does not read that state: it names what it shares.

locals {
  gcp            = jsondecode(file("${path.module}/../pubkit.json")).hosting.providers["google-cloud"]
  project_number = "948171295184"
}

module "site" {
  source = "github.com/Sustenaut/pubkit//terraform/cloud-run-service?ref=v0.24.4"

  name           = "estimate-site"
  project        = local.gcp.project
  project_number = local.project_number
  region         = local.gcp.region

  account_id           = "sustenaut-estimate-site"
  account_display_name = "Sustenaut estimate-site"
  account_description  = "Estimate site (static pages on Cloud Run): no access to anything; it serves files baked into its image."
  registry_description = "Images of the estimate site."
}

# --- Deploys from GitHub Actions, as the shared account in Sustenaut/shared-infra ---

locals {
  deployer = "serviceAccount:sustenaut-deployer@${local.gcp.project}.iam.gserviceaccount.com"
}

resource "google_artifact_registry_repository_iam_member" "deployer_push" {
  location   = local.gcp.region
  repository = "estimate-site"
  role       = "roles/artifactregistry.writer"
  member     = local.deployer
}

resource "google_cloud_run_v2_service_iam_member" "deployer_deploy" {
  name     = module.site.service
  location = local.gcp.region
  role     = "roles/run.developer"
  member   = local.deployer
}

resource "google_service_account_iam_member" "deployer_acts_as_site" {
  service_account_id = "projects/${local.gcp.project}/serviceAccounts/${module.site.service_account}"
  role               = "roles/iam.serviceAccountUser"
  member             = local.deployer
}
