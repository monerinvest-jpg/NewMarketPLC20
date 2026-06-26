resource "yandex_vpc_network" "main" {
  name   = "${var.project_name}-${var.environment}-net"
  labels = var.labels
}

# Публичная подсеть для Бастиона и внешнего балансировщика
resource "yandex_vpc_subnet" "public" {
  name           = "${var.project_name}-public"
  zone           = var.default_zone
  network_id     = yandex_vpc_network.main.id
  v4_cidr_blocks = [var.public_cidr]
}

# Приватная подсеть — Зона А
resource "yandex_vpc_subnet" "private" {
  name           = "${var.project_name}-private-a"
  zone           = "ru-central1-a"
  network_id     = yandex_vpc_network.main.id
  v4_cidr_blocks = [var.private_cidr]
  route_table_id = yandex_vpc_route_table.nat.id
}

# Приватная подсеть — Зона Б (Для обеспечения HA продакшена)
resource "yandex_vpc_subnet" "private_b" {
  name           = "${var.project_name}-private-b"
  zone           = "ru-central1-b"
  network_id     = yandex_vpc_network.main.id
  v4_cidr_blocks = ["192.168.20.0/24"]
  route_table_id = yandex_vpc_route_table.nat.id
}

# Единый NAT-шлюз для выхода приватных машин в интернет за Докером
resource "yandex_vpc_gateway" "nat" {
  name = "${var.project_name}-nat"
  lifecycle {
    ignore_changes = all
  }
}

# Таблица маршрутизации для NAT
resource "yandex_vpc_route_table" "nat" {
  name       = "${var.project_name}-nat-route"
  network_id = yandex_vpc_network.main.id

  static_route {
    destination_prefix = "0.0.0.0/0"
    gateway_id         = yandex_vpc_gateway.nat.id
  }

  lifecycle {
    ignore_changes = all
  }
}

# Группа безопасности для шлюза Kong
resource "yandex_vpc_security_group" "kong" {
  name        = "${var.project_name}-kong-sg"
  network_id  = yandex_vpc_network.main.id
  description = "Kong API Gateway security group"

  ingress {
    description    = "HTTP from load balancer"
    protocol       = "TCP"
    port           = 8000
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "Admin API (for Ansible)"
    protocol       = "TCP"
    port           = 8001
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "SSH from Bastion"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description    = "Allow all outgoing"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}

# Группа безопасности для Python-бэкенда (микросервисы)
resource "yandex_vpc_security_group" "backend" {
  name        = "${var.project_name}-backend-sg"
  network_id  = yandex_vpc_network.main.id
  description = "Backend security group"

  # ИЗМЕНЕНО под микросервисы: сервисы слушают порты 8001-8005 на узле
  # (контейнер внутри слушает 8000, наружу маппится 8001..8005). Kong ходит на
  # эти порты. В исходном монолите здесь был только порт 3000 — он больше не
  # используется (см. infra/ansible/deploy-services.yml, маппинг портов).
  ingress {
    description    = "Service ports from Kong (identity/catalog/orders/sellers/platform)"
    protocol       = "TCP"
    from_port      = 8001
    to_port        = 8005
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "SSH from Bastion"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description    = "Allow all outgoing"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}
