resource "yandex_lb_network_load_balancer" "public" {
  name = "${var.project_name}-lb"

  listener {
    name = "http"
    port = 80
    target_port = 8000
    external_address_spec {
      ip_version = "ipv4"
    }
  }

  attached_target_group {
    target_group_id = yandex_lb_target_group.kong.id

    healthcheck {
      name                = "kong"
      interval            = 2
      timeout             = 1
      healthy_threshold   = 2
      unhealthy_threshold = 2
      tcp_options {
        port = 8000
      }
    }
  }

  depends_on = [yandex_lb_target_group.kong]
}
