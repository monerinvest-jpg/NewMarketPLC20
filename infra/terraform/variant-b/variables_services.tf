# Per-service scale-out variables (optional growth variant).
#
# Use this WITH compute_services.tf to give each microservice its own instance
# group + ALB target group, instead of multiplexing all services on the existing
# backend group. If you adopt this, switch the Ansible to per-service inventory
# groups and point Kong upstreams at each service's target group address.

variable "services" {
  description = "Marketplace microservices: per-service sizing and replica count."
  type = map(object({
    cores  = number
    memory = number
    count  = number
  }))
  default = {
    identity = { cores = 2, memory = 2, count = 2 }
    catalog  = { cores = 2, memory = 2, count = 2 }
    orders   = { cores = 2, memory = 2, count = 2 }
    sellers  = { cores = 2, memory = 2, count = 2 }
    platform = { cores = 2, memory = 2, count = 2 }
  }
}
