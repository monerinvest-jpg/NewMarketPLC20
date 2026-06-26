resource "random_password" "postgres_password" {
  length  = 24
  special = false
}

resource "random_password" "redis_password" {
  length  = 16
  special = false
}

# Кластер PostgreSQL
resource "yandex_mdb_postgresql_cluster" "main" {
  name        = "${var.project_name}-postgres"
  environment = var.environment
  network_id  = yandex_vpc_network.main.id

  config {
    version = var.postgres_version

    resources {
      resource_preset_id = var.postgres_preset
      disk_type_id       = "network-ssd"
      disk_size          = var.postgres_disk
    }
  }

  host {
    zone             = "ru-central1-a"
    subnet_id        = yandex_vpc_subnet.private.id
    assign_public_ip = false
  }

  host {
    zone             = "ru-central1-b"
    subnet_id        = yandex_vpc_subnet.private_b.id
    assign_public_ip = false
  }
}

# База данных приложения
resource "yandex_mdb_postgresql_database" "app" {
  cluster_id = yandex_mdb_postgresql_cluster.main.id
  name       = "${var.project_name}_${var.environment}"
  owner      = yandex_mdb_postgresql_user.app.name
}

# Пользователь приложения
resource "yandex_mdb_postgresql_user" "app" {
  cluster_id = yandex_mdb_postgresql_cluster.main.id
  name       = "${var.project_name}_user"
  password   = random_password.postgres_password.result
  # permission block removed – owner is set on database
}

# === Kong database and user ===
resource "random_password" "kong_password" {
  length  = 16
  special = false
}

resource "yandex_mdb_postgresql_database" "kong" {
  cluster_id = yandex_mdb_postgresql_cluster.main.id
  name       = "kong"
  owner      = yandex_mdb_postgresql_user.kong.name
}

resource "yandex_mdb_postgresql_user" "kong" {
  cluster_id = yandex_mdb_postgresql_cluster.main.id
  name       = "kong_user"
  password   = random_password.kong_password.result
}

# Кластер Redis
resource "yandex_mdb_redis_cluster" "cache" {
  name        = "${var.project_name}-redis"
  environment = var.environment
  network_id  = yandex_vpc_network.main.id

  config {
    version  = var.redis_version
    password = random_password.redis_password.result
  }

  resources {
    resource_preset_id = var.redis_preset
    disk_size          = var.redis_disk
    disk_type_id       = "network-ssd"
  }

  host {
    zone      = "ru-central1-a"
    subnet_id = yandex_vpc_subnet.private.id
  }

  host {
    zone      = "ru-central1-b"
    subnet_id = yandex_vpc_subnet.private_b.id
  }
}
