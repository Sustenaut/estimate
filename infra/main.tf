# The estimate site: the models in estimate/ as marimo notebooks exported to
# WebAssembly, with Pyodide and every wheel they load, served as static files by
# nginx on Cloud Run behind Google's login (IAP), at estimate.sustenaut.eu. The
# models run in the reader's browser; the service reads nothing at run time, so
# it runs as an account with no roles. .github/workflows/deploy.yml builds and
# deploys it on each merge to main.
#
# Who may open the site, its domain and its DNS are Sustenaut/shared-infra's. This
# stack does not read that state.

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

  # An account only this repository can act as, which can only deploy this site.
  deploy_repository = "Sustenaut/estimate"
}
