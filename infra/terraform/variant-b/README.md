# Variant B — отдельная instance-группа на каждый сервис (опционально)

Эти файлы **не нужны** для обычного запуска (Вариант A: все сервисы мультиплексируются
на общей backend-группе, порты 8001–8005 — см. `infra/ansible/deploy-services.yml`).

Variant B нужен, когда сервисы пора масштабировать независимо: каждый получает свою
`yandex_compute_instance_group` + ALB target-группу, а Kong указывает на адрес группы
сервиса, а не на один backend-узел.

## Как включить

1. Скопируйте эти три файла в рабочий каталог терраформа:
   ```bash
   cp infra/terraform/variant-b/*.tf infra/terraform/
   ```
   Они дополняют базовый конфиг (используют его `var.project_name`, подсети,
   `var.service_account_id`, образ Ubuntu и т.д.).
2. `terraform plan` / `apply` — создадутся группы `${project}-{identity,catalog,orders,
   sellers,platform}-ig` и target-группы `${project}-<svc>-tg`.
3. Переведите Ansible на per-service inventory и Kong `upstream` на адреса/таргет-группы
   сервисов (см. `outputs_services.tf`).

> Перед apply сверьте имена ресурсов/переменных с базовым конфигом — Variant B
> ссылается на них и не является самостоятельным.
