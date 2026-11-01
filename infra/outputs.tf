output "site" {
  description = "The site's run.app address and image repository."
  value = {
    url              = module.site.url
    image_repository = module.site.image_repository
    deploy_account   = module.site.deploy_account
  }
}
