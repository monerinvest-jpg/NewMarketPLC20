data "yandex_compute_image" "ubuntu" {
  family = "ubuntu-2204-lts"
}

locals {
  cloud_init_user_data = templatefile("${path.module}/cloud-init.tpl", {
    ssh_public_key = file(var.public_ssh_key_path)
  })
}

# Бастион
resource "yandex_compute_instance" "bastion" {
  name        = "${var.project_name}-bastion"
  platform_id = "standard-v3"
  zone        = var.default_zone

  resources {
    cores         = 2
    memory        = 1
    core_fraction = 20
  }

  boot_disk {
    initialize_params {
      image_id = data.yandex_compute_image.ubuntu.id
      size     = 10
    }
  }

  network_interface {
    subnet_id = yandex_vpc_subnet.public.id
    nat       = true
  }

  metadata = {
    user-data = local.cloud_init_user_data
  }

  scheduling_policy {
    preemptible = true
  }
}

# Группа инстансов Kong Gateway (без встроенной целевой группы)
resource "yandex_compute_instance_group" "kong" {
  name               = "${var.project_name}-kong"
  folder_id          = var.folder_id
  service_account_id = var.service_account_id

  depends_on = [yandex_mdb_postgresql_cluster.main, yandex_mdb_redis_cluster.cache]

  instance_template {
    platform_id = "standard-v3"
    resources {
      cores         = var.kong_cores
      memory        = var.kong_memory
      core_fraction = 20
    }
    boot_disk {
      initialize_params {
        image_id = data.yandex_compute_image.ubuntu.id
        size     = var.disk_size
      }
    }
    network_interface {
      subnet_ids         = [yandex_vpc_subnet.private.id, yandex_vpc_subnet.private_b.id]
      security_group_ids = [yandex_vpc_security_group.kong.id]
      nat                = false
    }
    metadata = {
      user-data = local.cloud_init_user_data
    }
    scheduling_policy {
      preemptible = true
    }
  }

  scale_policy {
    fixed_scale {
      size = var.kong_count
    }
  }

  allocation_policy {
    zones = ["ru-central1-a", "ru-central1-b"]
  }

  deploy_policy {
    max_unavailable = 1
    max_expansion   = 2
  }

  health_check {
    interval = 30
    timeout  = 10
    tcp_options {
      port = 22
    }
  }

  # Блок application_load_balancer удалён

  timeouts {
    create = "20m"
    update = "20m"
    delete = "15m"
  }
}

# Группа инстансов Бэкенда (без изменений, если не используется балансировщиком)
resource "yandex_compute_instance_group" "backend" {
  name               = "${var.project_name}-backend"
  folder_id          = var.folder_id
  service_account_id = var.service_account_id

  depends_on = [yandex_mdb_postgresql_cluster.main, yandex_mdb_redis_cluster.cache]

  instance_template {
    platform_id = "standard-v3"
    resources {
      cores         = var.backend_cores
      memory        = var.backend_memory
      core_fraction = 20
    }
    boot_disk {
      initialize_params {
        image_id = data.yandex_compute_image.ubuntu.id
        size     = var.disk_size
      }
    }
    network_interface {
      subnet_ids         = [yandex_vpc_subnet.private.id, yandex_vpc_subnet.private_b.id]
      security_group_ids = [yandex_vpc_security_group.backend.id]
      nat                = false
    }
    metadata = {
      user-data = local.cloud_init_user_data
    }
    scheduling_policy {
      preemptible = true
    }
  }

  scale_policy {
    fixed_scale {
      size = var.backend_count
    }
  }

  allocation_policy {
    zones = ["ru-central1-a", "ru-central1-b"]
  }

  deploy_policy {
    max_unavailable = 1
    max_expansion   = 2
  }

  health_check {
    interval = 30
    timeout  = 10
    tcp_options {
      port = 22
    }
  }

  application_load_balancer {
    target_group_name = "${var.project_name}-backend-tg"
  }

  timeouts {
    create = "20m"
    update = "20m"
    delete = "15m"
  }
}
