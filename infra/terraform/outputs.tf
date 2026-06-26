output "load_balancer_ip" {
  description = "Public IP of the load balancer"
  value       = flatten([for listener in yandex_lb_network_load_balancer.public.listener : [for addr in listener.external_address_spec : addr.address]])[0]
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

[all:vars]
postgres_host=${yandex_mdb_postgresql_cluster.main.host[0].fqdn}
postgres_password=${random_password.postgres_password.result}
postgres_user=handmade_user
postgres_database=${var.project_name}_${var.environment}
redis_host=${yandex_mdb_redis_cluster.cache.host[0].fqdn}
redis_password=${random_password.redis_password.result}
ansible_ssh_common_args='-o ProxyCommand="ssh -W %h:%p -q -o StrictHostKeyChecking=no ubuntu@${yandex_compute_instance.bastion.network_interface[0].nat_ip_address}" -o StrictHostKeyChecking=no'
EOT
}
