output "load_balancer_ip" {
  description = "Public IP of the load balancer"
  value       = local.lb_ip
}

output "app_url" {
  description = "URL витрины (домен, если задан, иначе IP)"
  value       = local.dns_enabled ? "http://${var.domain_name}" : "http://${local.lb_ip}"
}

output "seller_url" {
  description = "URL кабинета продавца (поддомен; по IP поддомен недоступен)"
  value       = local.dns_enabled ? "http://seller.${var.domain_name}" : "n/a (нужен domain_name)"
}

output "dns_nameservers" {
  description = "NS-серверы Yandex Cloud DNS — делегируйте на них домен у регистратора (если зона создаётся здесь)"
  value       = local.create_zone ? ["ns1.yandexcloud.net.", "ns2.yandexcloud.net."] : []
}

output "bastion_public_ip" {
  description = "Public IP of the Bastion Host"
  value       = yandex_compute_instance.bastion.network_interface[0].nat_ip_address
}

output "postgres_hosts" {
  description = "FQDNs of PostgreSQL hosts"
  value       = yandex_mdb_postgresql_cluster.main.host[*].fqdn
}

output "postgres_password" {
  description = "PostgreSQL user password"
  value       = random_password.postgres_password.result
  sensitive   = true
}

output "kong_password" {
  description = "Password for Kong database user"
  value       = random_password.kong_password.result
  sensitive   = true
}

output "redis_host" {
  description = "Redis cluster host FQDN"
  value       = yandex_mdb_redis_cluster.cache.host[*].fqdn
}

output "redis_password" {
  description = "Redis cluster password"
  value       = random_password.redis_password.result
  sensitive   = true
}

output "kong_private_ips" {
  description = "Private IPs of Kong instances"
  value       = yandex_compute_instance_group.kong.instances[*].network_interface[0].ip_address
}

output "backend_private_ips" {
  description = "Private IPs of backend instances"
  value       = yandex_compute_instance_group.backend.instances[*].network_interface[0].ip_address
}

resource "local_file" "ansible_inventory" {
  filename = "${path.module}/hosts.ini"
  content  = <<EOT
[bastion]
${yandex_compute_instance.bastion.network_interface[0].nat_ip_address} ansible_user=ubuntu

[kong]
${join("\n", [for ip in yandex_compute_instance_group.kong.instances[*].network_interface[0].ip_address : "${ip} ansible_user=ubuntu"])}

[backend]
${join("\n", [for ip in yandex_compute_instance_group.backend.instances[*].network_interface[0].ip_address : "${ip} ansible_user=ubuntu"])}

# Observability host = the bastion (public IP, in-VPC) — runs Prometheus+Grafana.
[monitoring]
${yandex_compute_instance.bastion.network_interface[0].nat_ip_address} ansible_user=ubuntu

[monitoring:vars]
ansible_ssh_common_args='-o StrictHostKeyChecking=no'

[all:vars]
postgres_host=${yandex_mdb_postgresql_cluster.main.host[0].fqdn}
postgres_password=${random_password.postgres_password.result}
postgres_user=handmade_user
postgres_database=${var.project_name}_${var.environment}
redis_host=${yandex_mdb_redis_cluster.cache.host[0].fqdn}
redis_password=${random_password.redis_password.result}
kong_password=${random_password.kong_password.result}
s3_endpoint=https://storage.yandexcloud.net
s3_bucket=${yandex_storage_bucket.assets.bucket}
s3_private_bucket=${yandex_storage_bucket.private.bucket}
s3_access_key=${yandex_iam_service_account_static_access_key.storage_key.access_key}
s3_secret_key=${yandex_iam_service_account_static_access_key.storage_key.secret_key}
s3_public_url=https://storage.yandexcloud.net/${yandex_storage_bucket.assets.bucket}
smtp_host=postbox.cloud.yandex.net
smtp_port=587
smtp_user=${yandex_iam_service_account_static_access_key.mail_key.access_key}
smtp_password=${yandex_iam_service_account_static_access_key.mail_key.secret_key}
smtp_from=${var.smtp_from}
ansible_ssh_common_args='-o ProxyCommand="ssh -W %h:%p -q -o StrictHostKeyChecking=no ubuntu@${yandex_compute_instance.bastion.network_interface[0].nat_ip_address}" -o StrictHostKeyChecking=no'
EOT
}
