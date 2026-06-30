# ─── DNS: домен + поддомен кабинета продавца (seller.<домен>) ──────────────────
#
# Кабинет продавца живёт на ОТДЕЛЬНОМ хосте seller.<домен>, но обслуживается тем
# же Kong/NLB и тем же фронтенд-контейнером (catch-all '/' в Kong — host-agnostic,
# маршрутизация по пути). Поэтому на уровне инфраструктуры достаточно DNS: апекс и
# `seller` указывают на ОДИН и тот же IP балансировщика.
#
# Всё опционально и включается переменной `domain_name`:
#   • domain_name = ""                  → DNS-ресурсы не создаются, деплой по IP (как было).
#   • domain_name = "example.com"       → создаётся публичная зона Cloud DNS + A-записи.
#   • manage_dns_zone = false           → зона НЕ создаётся, записи кладутся в существующую
#                                         (dns_zone_id), если домен делегирован в YC заранее.
#
# Требуется роль `dns.editor` у сервис-аккаунта Terraform и включённый Cloud DNS в folder.

locals {
  # Публичный IP NLB (тот же, что в output load_balancer_ip).
  lb_ip = flatten([
    for listener in yandex_lb_network_load_balancer.public.listener :
    [for addr in listener.external_address_spec : addr.address]
  ])[0]

  dns_enabled = var.domain_name != ""
  create_zone = local.dns_enabled && var.manage_dns_zone
  # ID зоны: либо создаём свою, либо используем переданную существующую.
  dns_zone_id = local.create_zone ? yandex_dns_zone.main[0].id : var.dns_zone_id
}

resource "yandex_dns_zone" "main" {
  count = local.create_zone ? 1 : 0

  name   = "${var.project_name}-public"
  zone   = "${var.domain_name}."
  public = true

  labels = var.labels
}

# Апекс-домен (example.com) → NLB.
resource "yandex_dns_recordset" "apex" {
  count = local.dns_enabled ? 1 : 0

  zone_id = local.dns_zone_id
  name    = "${var.domain_name}."
  type    = "A"
  ttl     = var.dns_ttl
  data    = [local.lb_ip]
}

# Поддомен кабинета продавца (seller.example.com) → тот же NLB.
resource "yandex_dns_recordset" "seller" {
  count = local.dns_enabled ? 1 : 0

  zone_id = local.dns_zone_id
  name    = "seller.${var.domain_name}."
  type    = "A"
  ttl     = var.dns_ttl
  data    = [local.lb_ip]
}

# www → апекс (удобство; включается переменной dns_www, по умолчанию off).
resource "yandex_dns_recordset" "www" {
  count = local.dns_enabled && var.dns_www ? 1 : 0

  zone_id = local.dns_zone_id
  name    = "www.${var.domain_name}."
  type    = "CNAME"
  ttl     = var.dns_ttl
  data    = ["${var.domain_name}."]
}
