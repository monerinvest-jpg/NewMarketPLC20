resource "time_sleep" "wait_for_kong" {
  depends_on      = [yandex_compute_instance_group.kong]
  create_duration = "30s"
}

# Целевая группа — только одно объявление!
resource "yandex_lb_target_group" "kong" {
  name      = "${var.project_name}-kong-tg"
  region_id = "ru-central1"

  dynamic "target" {
    for_each = yandex_compute_instance_group.kong.instances
    content {
      subnet_id = target.value.network_interface[0].subnet_id
      address   = target.value.network_interface[0].ip_address
    }
  }

  # Явная зависимость: ждём либо группу напрямую, либо паузу (или оба)
  depends_on = [
    yandex_compute_instance_group.kong,
    time_sleep.wait_for_kong # если используете time_sleep, иначе уберите эту строку
  ]
}
