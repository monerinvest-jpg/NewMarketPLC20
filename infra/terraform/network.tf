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

# Внутренние подсети VPC: бастион (public), приватные A и B. Используются,
# чтобы служебные порты были доступны только изнутри, а не с 0.0.0.0/0.
locals {
  internal_cidrs = [var.public_cidr, var.private_cidr, "192.168.20.0/24"]
}

# Группа безопасности для шлюза Kong
resource "yandex_vpc_security_group" "kong" {
  name        = "${var.project_name}-kong-sg"
  network_id  = yandex_vpc_network.main.id
  description = "Kong API Gateway security group"

  # Публичная точка входа: NLB — passthrough (L4), пакеты приходят с реальных
  # IP клиентов, поэтому 8000 должен быть открыт миру.
  ingress {
    description    = "HTTP from load balancer (public edge)"
    protocol       = "TCP"
    port           = 8000
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "Kong Admin API — in-VPC only (Ansible via bastion, Prometheus)"
    protocol       = "TCP"
    port           = 8001
    v4_cidr_blocks = local.internal_cidrs
  }

  ingress {
    description    = "SSH from the bastion subnet only"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = [var.public_cidr]
  }

  ingress {
    description    = "node-exporter scrape from Prometheus (bastion)"
    protocol       = "TCP"
    port           = 9100
    v4_cidr_blocks = [var.public_cidr]
  }

  egress {
    description    = "Allow all outgoing"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}

# Группа безопасности бастиона (раньше SG не было вовсе — всё, что на нём
# слушало, было доступно из интернета, включая Prometheus :9090).
resource "yandex_vpc_security_group" "bastion" {
  name        = "${var.project_name}-bastion-sg"
  network_id  = yandex_vpc_network.main.id
  description = "Bastion + observability host"

  ingress {
    description    = "SSH (jump host)"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  # Grafana остаётся публичной СОЗНАТЕЛЬНО: на ней держится iframe в админке
  # («Метрики»). Анонимный доступ — только Viewer. Закрыть за VPN/авторизацией
  # при боевом запуске (см. prod-план).
  ingress {
    description    = "Grafana (admin Метрики iframe)"
    protocol       = "TCP"
    port           = 3000
    v4_cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description    = "Prometheus — in-VPC only"
    protocol       = "TCP"
    port           = 9090
    v4_cidr_blocks = local.internal_cidrs
  }

  ingress {
    description    = "Loki push (Alloy agents) — in-VPC only"
    protocol       = "TCP"
    port           = 3100
    v4_cidr_blocks = local.internal_cidrs
  }

  ingress {
    description    = "Alertmanager UI — in-VPC only (SSH-туннель для просмотра)"
    protocol       = "TCP"
    port           = 9093
    v4_cidr_blocks = local.internal_cidrs
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
    description    = "Service ports — Kong subnets + Prometheus (in-VPC only)"
    protocol       = "TCP"
    from_port      = 8001
    to_port        = 8005
    v4_cidr_blocks = local.internal_cidrs
  }

  ingress {
    description    = "Frontend SPA port from Kong (in-VPC only)"
    protocol       = "TCP"
    port           = 3000
    v4_cidr_blocks = local.internal_cidrs
  }

  ingress {
    description    = "SSH from the bastion subnet only"
    protocol       = "TCP"
    port           = 22
    v4_cidr_blocks = [var.public_cidr]
  }

  # MeiliSearch on the first backend node; reachable from the private subnets
  # only (service containers on the OTHER backend node must query it too).
  ingress {
    description    = "MeiliSearch (in-VPC only)"
    protocol       = "TCP"
    port           = 7700
    v4_cidr_blocks = [var.private_cidr, "192.168.20.0/24"]
  }

  ingress {
    description    = "node-exporter scrape from Prometheus (bastion)"
    protocol       = "TCP"
    port           = 9100
    v4_cidr_blocks = [var.public_cidr]
  }

  egress {
    description    = "Allow all outgoing"
    protocol       = "ANY"
    v4_cidr_blocks = ["0.0.0.0/0"]
    from_port      = 0
    to_port        = 65535
  }
}
