# infra/ — готовые файлы для инфра-репозитория (Yandex Cloud)

Эти файлы предназначены для переноса в `skboyinboxru/Hand-Made` (`terraform/`, `Ansible/`).
Сгенерированы под фактические идентификаторы вашего Terraform (`yandex_compute_instance_group.backend`,
подсети `private`/`private_b`, SG `backend`, `data.yandex_compute_image.ubuntu`, переменные
`var.project_name/folder_id/service_account_id/backend_*/disk_size/public_ssh_key_path/labels`).

> ⚠️ Перед `terraform apply` / прогоном плейбука — просмотрите и сверьте имена с вашим репозиторием.
> Terraform не валидировался против полного стейта (нет доступа к вашему backend и стейту).

## Два варианта развёртывания

### Вариант A (рекомендуется, drop-in) — мультиплекс на существующей backend-группе
- **Terraform не меняется.** Все 5 сервисов + worker/beat запускаются контейнерами на узлах
  текущей `yandex_compute_instance_group.backend`, порты 8001–8005.
- Файл: **`ansible/deploy-services.yml`** — заменяет старый `deploy-backend.yml`.
  Собирает контракт env, гоняет `migrate` (один раз), поднимает контейнеры, настраивает Kong-маршруты.
- Таблица маршрутов и порты — в [STAGE2_INFRA_CHANGES.md](STAGE2_INFRA_CHANGES.md).

### Вариант B (рост) — отдельная instance-группа на сервис
- Файлы: **`terraform/compute_services.tf`**, **`terraform/variables_services.tf`**,
  **`terraform/outputs_services.tf`** — кладутся рядом с вашими `*.tf`.
- Создаёт `${project}-{identity,catalog,orders,sellers,platform}-ig` + per-service ALB target group
  `${project}-<svc>-tg`. Контейнер слушает 8000 (по одному на узел группы).
- При этом варианте: Ansible переводится на per-service inventory (по `docker run ... :latest web`
  на 8000), а Kong `upstream` указывает на адрес/таргет-группу сервиса (см. `outputs_services.tf`).

## Сборка и пуш образов (оба варианта)

Контекст сборки — корень репозитория приложения:
```bash
for s in identity catalog orders sellers platform worker; do
  docker build -f services/$s/Dockerfile -t cr.yandex/<reg>/handmade-$s:latest .
  docker push cr.yandex/<reg>/handmade-$s:latest
done
```

## Что добавить в `group_vars/all` (если ещё нет)
```yaml
registry: "cr.yandex/crp8b0ggroptcd9dso2t"   # ваш реестр
image_tag: "latest"
# уже должны существовать из Terraform outputs:
# postgres_host, postgres_user, postgres_password, postgres_database
# kong_db_user, kong_db_password, kong_db_name, kong_image
# redis_host, redis_password
```

## CA-сертификат Managed PostgreSQL
Плейбук монтирует `/opt/handmade/certs/root.crt` в контейнеры (`DB_SSL=true`,
`DB_SSL_ROOT_CERT=/app/certs/root.crt`). Положите CA Yandex в `Ansible/files/root.crt`
(скачивается из консоли Managed PostgreSQL) — задача `copy` его разложит на узлы.
Если внутри VPC через пулер :6432 TLS не требуется — выставьте `DB_SSL: "false"` в `app_env`.

## Файлы
| Файл | Назначение |
|---|---|
| `ansible/deploy-services.yml` | Полный плейбук (Вариант A): образы, migrate, контейнеры, Kong-маршруты |
| `terraform/compute_services.tf` | Вариант B: per-service instance groups (for_each) |
| `terraform/variables_services.tf` | Вариант B: карта сервисов и сайзинг |
| `terraform/outputs_services.tf` | Вариант B: target-группы/адреса для Kong |
| `STAGE2_INFRA_CHANGES.md` | Таблица маршрутов Kong, порты, чек-лист выката |
