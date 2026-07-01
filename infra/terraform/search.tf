# Full-text search (MeiliSearch). The engine itself runs as a container on the
# first backend node (see infra/ansible/deploy-services.yml); Terraform only
# provisions the master key that both the engine and the services share.
resource "random_password" "meili_key" {
  length  = 32
  special = false
}
