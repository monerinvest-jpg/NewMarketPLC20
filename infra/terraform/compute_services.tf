# Per-service instance groups (scale-out variant).
#
# Mirrors `yandex_compute_instance_group.backend` from compute.tf, one group per
# microservice via for_each. Each group registers its own ALB target group
# "${var.project_name}-<svc>-tg". Reuses the existing subnets, security group,
# image, service account and cloud-init from the current config — keep the
# instance_template in sync with the backend block if you change that one.
#
# Container always listens on 8000; Kong routes per path prefix to each service's
# target group (see infra/STAGE2_INFRA_CHANGES.md §3). Pair with a per-service
# Ansible inventory that runs `docker run ... handmade-<svc>:latest web` on 8000.

resource "yandex_compute_instance_group" "service" {
  for_each = var.services

  name               = "${var.project_name}-${each.key}-ig"
  folder_id          = var.folder_id
  service_account_id = var.service_account_id

  instance_template {
    platform_id = "standard-v3"

    resources {
      cores  = each.value.cores
      memory = each.value.memory
    }

    boot_disk {
      initialize_params {
        image_id = data.yandex_compute_image.ubuntu.id
        size     = var.disk_size
      }
    }

    network_interface {
      # Span both private zones, same as the backend group. No public NAT.
      subnet_ids         = [yandex_vpc_subnet.private.id, yandex_vpc_subnet.private_b.id]
      security_group_ids = [yandex_vpc_security_group.backend.id]
      nat                = false
    }

    metadata = {
      user-data = templatefile("${path.module}/cloud-init.tpl", {
        ssh_public_key = file(var.public_ssh_key_path)
      })
    }

    labels = var.labels
  }

  scale_policy {
    fixed_scale {
      size = each.value.count
    }
  }

  allocation_policy {
    zones = ["ru-central1-a", "ru-central1-b"]
  }

  deploy_policy {
    max_unavailable = 1
    max_expansion   = 2
  }

  # Each service gets its own ALB target group; Kong upstreams point here.
  application_load_balancer {
    target_group_name   = "${var.project_name}-${each.key}-tg"
    target_group_labels = var.labels
  }

  timeouts {
    create = "20m"
    update = "20m"
    delete = "20m"
  }
}
