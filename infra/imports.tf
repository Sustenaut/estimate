# These were made by Sustenaut/shared-infra, which forgets them once this stack has
# them. Nothing is created. Remove this file once both stacks have been applied.

import {
  to = module.site.google_service_account.site
  id = "projects/sustenaut/serviceAccounts/sustenaut-estimate-site@sustenaut.iam.gserviceaccount.com"
}

import {
  to = module.site.google_artifact_registry_repository.site
  id = "projects/sustenaut/locations/europe-north1/repositories/estimate-site"
}

import {
  to = module.site.google_cloud_run_v2_service.site
  id = "projects/sustenaut/locations/europe-north1/services/estimate-site"
}

import {
  to = module.site.google_cloud_run_v2_service_iam_member.iap_invoker[0]
  id = "projects/sustenaut/locations/europe-north1/services/estimate-site roles/run.invoker serviceAccount:service-948171295184@gcp-sa-iap.iam.gserviceaccount.com"
}
