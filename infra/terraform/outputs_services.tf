# Outputs for the per-service scale-out variant — used to wire Kong upstreams.

output "service_instance_groups" {
  description = "Per-service instance group IDs."
  value       = { for k, ig in yandex_compute_instance_group.service : k => ig.id }
}

output "service_target_groups" {
  description = "Per-service ALB target group names (point Kong upstreams at these)."
  value       = { for k, _ in var.services : k => "${var.project_name}-${k}-tg" }
}

output "service_internal_addresses" {
  description = "First instance internal IP per service (handy for a static Kong upstream)."
  value = {
    for k, ig in yandex_compute_instance_group.service :
    k => try(ig.instances[0].network_interface[0].ip_address, null)
  }
}
