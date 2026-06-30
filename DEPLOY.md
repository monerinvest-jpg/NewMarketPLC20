# 🚀 Развёртывание маркетплейса в Yandex Cloud (Terraform + Ansible)

Подробная пошаговая инструкция: как с нуля поднять прод-инфраструктуру в Yandex
Cloud и выкатить на неё приложение. Вся инфраструктура теперь лежит **внутри этого
репозитория** в каталоге [infra/](infra/) — отдельный инфра-репозиторий копировать
больше не нужно.

> 🖥️ Локальный запуск для разработки (Docker Compose) — в [RUN.md](RUN.md).
> Здесь — про облако.

---

## Содержание

1. [Как всё устроено](#1-как-всё-устроено)
2. [Что понадобится](#2-что-понадобится-prerequisites)
3. [Шаг 1 — Terraform: создать инфраструктуру](#3-шаг-1--terraform-создать-инфраструктуру)
4. [Шаг 2 — собрать и запушить образы (backend + frontend)](#4-шаг-2--собрать-и-запушить-образы-6-backend--frontend)
5. [Шаг 3 — CA-сертификат БД](#5-шаг-3--ca-сертификат-managed-postgresql)
6. [Шаг 4 — Ansible: выкатить приложение](#6-шаг-4--ansible-выкатить-приложение)
7. [Шаг 5 — проверка](#7-шаг-5--проверка)
8. [Обновление приложения](#8-обновление-приложения-новый-релиз)
9. [Фронтенд (отдельный контейнер)](#9-фронтенд-отдельный-контейнер-за-kong) · [9a. Наблюдаемость](#9a-наблюдаемость-prometheus--grafana--опционально)
10. [Шпаргалка «с нуля»](#10-шпаргалка-с-нуля)
11. [Траблшутинг](#11-траблшутинг)
12. [Удаление инфраструктуры](#12-удаление-инфраструктуры)

---

## 1. Как всё устроено

```
            Интернет
               │  :80
        ┌──────▼───────────────┐
        │ NLB (yandex_lb)      │  внешний IP = output load_balancer_ip
        └──────┬───────────────┘
               │  TCP :8000  (health-check :8000)
        ┌──────▼───────────────┐      ┌──────────────┐
        │ Kong instance group  │◀────▶│ PostgreSQL 17 │ (БД kong, пулер :6432)
        │ (2 узла, Postgres)   │      └──────────────┘
        └──────┬───────────────┘
               │  по префиксу пути → :8001..:8005
        ┌──────▼───────────────────────────────────────┐
        │ backend instance group (2 узла)               │
        │  identity:8001 catalog:8002 orders:8003       │
        │  sellers:8004  platform:8005  + worker/beat   │
        └──────┬─────────────────────┬──────────────────┘
               │                     │
     ┌─────────▼────────┐   ┌────────▼─────────┐
     │ PostgreSQL 17    │   │ Redis / Valkey 8 │
     │ db handmade_*    │   │ broker + rate-lim│
     │ pooler :6432 TLS │   └──────────────────┘
     └──────────────────┘
        ▲
        │ SSH (ProxyCommand)
   ┌────┴─────┐
   │ Bastion  │  публичный IP, единственная точка входа по SSH
   └──────────┘
```

- **Terraform** ([infra/terraform/](infra/terraform/)) создаёт сеть, бастион, Managed
  PostgreSQL 17 + Redis/Valkey, группу Kong, backend-группу и внешний балансировщик.
  После `apply` он **сам генерирует `infra/terraform/hosts.ini`** — готовый
  Ansible-инвентарь с приватными IP и реквизитами БД/Redis.
- **Ansible** ([infra/ansible/deploy-services.yml](infra/ansible/deploy-services.yml))
  на каждом backend-узле поднимает 5 сервис-контейнеров (порты 8001–8005) + worker/beat,
  гоняет миграции и настраивает Kong (маршрут на каждый префикс пути).
- Все 5 сервисов + worker/beat работают на общей backend-группе (2 узла), порты 8001–8005.
- **Managed-дополнения:** `storage.tf` — приватный **Object Storage** (картинки +
  цифровые товары/HLS), `mail.tf` — **Postbox** (SMTP). **Фронтенд** деплоится
  отдельным образом/плейбуком ([deploy-frontend.yml](infra/ansible/deploy-frontend.yml))
  за тем же Kong. **Наблюдаемость** (Prometheus+Grafana) — плейбук
  [observability.yml](infra/ansible/observability.yml). Сборка/пуш всех образов —
  [build-and-push.sh](build-and-push.sh) или GitHub Actions.

> ⚠️ Terraform-файлы воссозданы из репозитория `skboyinboxru/Hand-Made` дословно,
> **с одним отличием**: security-группа `backend` в [network.tf](infra/terraform/network.tf)
> открывает порты **8001–8005** (под микросервисы) вместо исходного 3000. Перед боевым
> `apply` рекомендую прогнать `terraform validate` (см. шаг 1.4).

---

## 2. Что понадобится (prerequisites)

**Локальные инструменты:**

| Инструмент | Версия | Зачем |
|---|---|---|
| Terraform | ≥ 1.5 | создание ресурсов |
| Ansible | ≥ 2.14 | выкат приложения |
| Docker | любой свежий | сборка/пуш образов |
| Yandex Cloud CLI (`yc`) | свежий | реестр, id облака/каталога/СА |
| `openssl`, `python3`, `ssh` | — | используются плейбуком/инвентарём |

**Доступы в Yandex Cloud** (получаются один раз):

```bash
yc init                                   # авторизация, выбор облака/каталога
yc resource-manager cloud list            # → cloud_id
yc resource-manager folder list           # → folder_id

# Сервис-аккаунт для instance-групп и пуша образов:
yc iam service-account create --name handmade-deployer
yc iam service-account list               # → service_account_id (aje...)

# Роли СА (минимум):
FOLDER=<folder_id>; SA=<service_account_id>
for role in editor container-registry.images.pusher container-registry.images.puller \
            compute.editor vpc.admin mdb.admin load-balancer.admin iam.serviceAccounts.user; do
  yc resource-manager folder add-access-binding $FOLDER --role $role \
    --service-account-id $SA
done

# Ключ СА для Terraform (попадёт в infra/terraform/key.json):
yc iam key create --service-account-id $SA --output infra/terraform/key.json
```

> `key.json`, `*.tfvars`, `hosts.ini` и `terraform.tfstate*` уже в
> [.gitignore](infra/terraform/.gitignore) — они содержат секреты и не коммитятся.

SSH-ключ: Terraform по умолчанию читает `public_ssh_key_path` (дефолт
`/home/it/.ssh/id_rsa.pub`). Укажите путь к **своему** ключу в `terraform.tfvars`
(шаг 1.1). Приватный ключ от той же пары нужен Ansible для входа через бастион.

---

## 3. Шаг 1 — Terraform: создать инфраструктуру

Все команды — из каталога `infra/terraform/`.

### 1.1. Переменные

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
```

Заполните в `terraform.tfvars` **обязательные** значения (без них apply не пройдёт):

```hcl
cloud_id            = "b1g..."
folder_id           = "b1g..."
service_account_id  = "aje..."
public_ssh_key_path = "/home/youruser/.ssh/id_rsa.pub"
```

Остальное (имена, сайзинг, версии PG/Redis) имеет разумные дефолты —
см. [variables.tf](infra/terraform/variables.tf).

> Не меняйте `project_name` без необходимости: инвентарь в
> [outputs.tf](infra/terraform/outputs.tf) жёстко прописывает `postgres_user=handmade_user`.
> Если переименовали проект — поправьте там же `postgres_user`/`postgres_database`.

### 1.2. Ключ сервис-аккаунта

Убедитесь, что `infra/terraform/key.json` на месте (создан на шаге 2) — провайдер
читает именно его (`service_account_key_file = "key.json"`).

### 1.3. Инициализация

```bash
terraform init
```

Скачает провайдеры `yandex`, `random`, `local`, `time` (последний подтянется
автоматически из-за ресурса `time_sleep`).

### 1.4. Проверка и применение

```bash
terraform validate          # синтаксис и связность (рекомендуется)
terraform plan              # что именно будет создано — просмотрите
terraform apply             # подтвердите "yes" (создание БД/группы занимает ~10-20 мин)
```

Создаётся: VPC + 3 подсети (public, private-a, private-b) + NAT, **бастион** (публичный
IP), **Managed PostgreSQL 17** (база `handmade_production`, пользователь `handmade_user`,
+ отдельные БД/юзер `kong`, пулер **:6432**), **Managed Redis/Valkey 8**, **группа Kong**
(2 узла), **backend-группа** (2 узла), **NLB** с внешним IP.

### 1.5. Выводы и инвентарь

После `apply` Terraform создаёт **`infra/terraform/hosts.ini`** — Ansible-инвентарь
с группами `[bastion]/[kong]/[backend]` и секцией `[all:vars]` (туда подставлены
`postgres_host/user/password/database`, `redis_host/password` и SSH-прокси через бастион).

```bash
terraform output load_balancer_ip        # внешний IP приложения
terraform output bastion_public_ip
terraform output -raw postgres_password   # sensitive
terraform output -raw redis_password      # sensitive
```

---

## 4. Шаг 2 — собрать и запушить образы (6 backend + frontend)

Реестр по умолчанию — `cr.yandex/crp8b0ggroptcd9dso2t` (зашит в
[deploy-services.yml](infra/ansible/deploy-services.yml), переменная `registry`).
Свой реестр: `yc container registry create --name handmade` → подставьте его id.

Самый простой способ — готовый скрипт **[build-and-push.sh](build-and-push.sh)**
(собирает 6 backend-образов из корня + **отдельный frontend-образ** и пушит всё):

```bash
bash build-and-push.sh
```

Или вручную:

```bash
# из корня marketplace/
yc container registry configure-docker        # один раз: логин docker в cr.yandex
REG=cr.yandex/crp8b0ggroptcd9dso2t

# backend (context = корень; worker = тот же образ, команды worker/beat):
for s in identity catalog orders sellers platform worker; do
  docker build -f services/$s/Dockerfile -t $REG/handmade-$s:latest .
  docker push $REG/handmade-$s:latest
done

# frontend (context = frontend/; БЕЗ VITE_API_URL → SPA ходит на относительный /api/v1):
docker build -f frontend/Dockerfile -t $REG/handmade-frontend:latest frontend
docker push $REG/handmade-frontend:latest
```

> **CI/CD-альтернатива:** то же делает GitHub Actions
> [.github/workflows/deploy.yml](.github/workflows/deploy.yml) (ручной запуск:
> сборка/пуш всех образов + опциональный Ansible-редеплой). Нужны секреты
> `YC_SA_KEY_JSON`, `YC_REGISTRY_ID`.

> Узлы скачивают образы по IAM-токену из метаданных (роль
> `container-registry.images.puller` у СА группы) — отдельный `docker login` на узлах
> не нужен, плейбук делает его сам.

---

## 5. Шаг 3 — CA-сертификат Managed PostgreSQL

> При запуске **`deploy-all.yml`** этот шаг можно пропустить — мастер-плейбук
> сам докачает CA в `infra/ansible/files/root.crt`. Ручной вариант ниже.

Сервисы ходят в БД по TLS (`DB_SSL=true`). Положите CA Yandex:

```bash
mkdir -p infra/ansible/files
curl -o infra/ansible/files/root.crt https://storage.yandexcloud.net/cloud-certs/CA.pem
```

Плейбук скопирует его на узлы в `/opt/handmade/certs/root.crt` и смонтирует в контейнеры.

> Если решите ходить в БД внутри VPC через пулер :6432 без TLS — выставьте
> `DB_SSL: "false"` в `app_env` плейбука и пропустите этот шаг.

---

## 6. Шаг 4 — Ansible: выкатить приложение

Ansible запускается **из `infra/terraform/`** — там лежат сгенерированный `hosts.ini`
и [ansible.cfg](infra/terraform/ansible.cfg) (`inventory=./hosts.ini`,
`host_key_checking=False`). Плейбук берём из соседней `../ansible/`.

```bash
cd infra/terraform

# Проверка связи (SSH автоматически идёт через бастион — это в hosts.ini):
ansible -m ping all

# ── Вариант 1 (рекомендуется): всё одной командой ──
# CA БД (скачается сам, шаг 3 можно пропустить) → backend (migrate+сервисы+Kong) → frontend
ansible-playbook ../ansible/deploy-all.yml

# ── Вариант 2: по отдельности (порядок важен!) ──
ansible-playbook ../ansible/kong-setup.yml        # СНАЧАЛА поднять сам Kong (иначе routes-play
                                                  #   упадёт: Connection refused на :8001)
ansible-playbook ../ansible/deploy-services.yml   # backend + маршруты Kong
ansible-playbook ../ansible/deploy-frontend.yml   # frontend
```

> **`deploy-all.yml`** — мастер-плейбук: сам докачивает CA-сертификат БД, затем
> импортирует `deploy-services.yml` + `deploy-frontend.yml`. То есть «настроить все
> сервисы автоматически» = одна команда. (Наблюдаемость — отдельно: `observability.yml`.)

Что делают плейбуки по шагам:

1. **Секреты:** генерирует общие `SECRET_KEY` / `REFRESH_SECRET_KEY` (по разу на все узлы).
2. **Docker:** ставит при необходимости, логинит в Container Registry по IAM-токену.
3. **CA:** раскладывает `root.crt` → `/opt/handmade/certs/`.
4. **Миграции:** один раз гоняет `migrate` + `seed` образом `handmade-identity`
   (общая схема `0001→0015`, супер-админ и дефолтные настройки в таблице `settings`).
5. **Сервисы:** на каждом backend-узле — `handmade-{identity,catalog,orders,sellers,
   platform}` на портах 8001–8005, `--restart always`. В env каждого контейнера, помимо
   БД/Redis/секретов, прокидываются **S3_*** (Object Storage) и **SMTP_*** (Postbox) —
   их значения Terraform подставляет в `[all:vars]` инвентаря (см. `storage.tf`/`mail.tf`).
   Пустые значения → деградация: загрузки идут на локальный диск, письма пишутся в лог.
6. **Воркеры:** один `handmade-worker` и один `handmade-beat` на первом узле.
7. **Kong:** по одному service+route на префикс (`strip_path=false`), плюс
   высокоприоритетный `/api/v1/seller/sub-orders` → orders и включение
   **Prometheus-плагина** Kong (метрики на `:8001/metrics`).

> Если завели зашифрованный `group_vars/all/vault.yml` (шаблон —
> [vault.yml.example](infra/ansible/group_vars/all/vault.yml.example)), добавьте
> `--ask-vault-pass`. Для базового выката он не нужен.

---

## 7. Шаг 5 — проверка

```bash
LB=$(terraform output -raw load_balancer_ip)   # из infra/terraform

curl http://$LB/health                         # {"status":"ok","service":"..."}
curl http://$LB/api/v1/products                 # каталог
curl -X POST http://$LB/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"test12345","full_name":"A"}'
```

Маршруты на Kong-узле: `curl http://localhost:8001/routes` (через SSH на kong-хост).
Логи сервиса на backend-узле: `docker logs handmade-orders`.

Полные пользовательские сценарии (покупка, продавец, рефералка, модерация) —
в [README.md](README.md), раздел «Тестирование основных сценариев».

---

## 8. Обновление приложения (новый релиз)

```bash
# 1. Пересобрать и запушить изменённые образы (bash build-and-push.sh, см. шаг 2)
# 2. Повторно прогнать нужный плейбук — контейнеры пересоздаются (docker rm -f && docker run)
cd infra/terraform
ansible-playbook ../ansible/deploy-services.yml      # backend (миграции накатятся сами)
ansible-playbook ../ansible/deploy-frontend.yml      # только фронт — независимо
```

Миграции в плейбуке идемпотентны (`alembic upgrade head`, цепочка `0001→0015`).
**Backend и frontend катятся независимо** (разные образы и плейбуки). Изменения
инфраструктуры (сайзинг, число узлов, бакет, Postbox) — через `terraform apply`.

---

## 9. Фронтенд (отдельный контейнер за Kong)

Фронтенд деплоится **независимо от backend** своим плейбуком и образом. Образ
собирается **без `VITE_API_URL`** → SPA обращается к API по относительному `/api/v1`
(тот же origin, что и отдаёт страницу). Kong — единый edge: он уже маршрутизирует
`/api/v1/*`, `/health`, `/uploads` на бэкенд, а низкоприоритетный catch-all `/`
отдаёт SPA. Поэтому в образе нет хоста бэкенда и **CORS не нужен**.

```bash
# образ уже собран на шаге 2 (handmade-frontend). Деплой — отдельным плейбуком:
cd infra/terraform
ansible-playbook ../ansible/deploy-frontend.yml
```

Плейбук [deploy-frontend.yml](infra/ansible/deploy-frontend.yml) запускает контейнер
`handmade-frontend` на узле (:3000) и добавляет в Kong catch-all маршрут `/` → фронт.
Фронт можно катить, **не трогая backend** (и наоборот) — релизы независимы.

Открыть приложение: `http://<load_balancer_ip>/`.

---

## 9a. Наблюдаемость (Prometheus + Grafana) — опционально

```bash
# нужен хост [monitoring] в инвентаре (мелкая ВМ или бастион)
cd infra/terraform
ansible-playbook ../ansible/observability.yml
```

[observability.yml](infra/ansible/observability.yml) поднимает Prometheus + Grafana
(анонимный просмотр, embedding) + node_exporter; Prometheus скрейпит `/metrics`
6 сервисов, Kong и node-экспортеры. Затем в админке (раздел **Метрики**) вставьте
URL Grafana-дашборда (настройка `grafana_dashboard_url`) — он встроится по iframe.
Sentry включается переменной `SENTRY_DSN` (по умолчанию выключен).

---

## 10. Шпаргалка «с нуля»

```bash
# ── 0. Доступы ──
yc iam key create --service-account-id <SA> --output infra/terraform/key.json

# ── 1. INFRA ──
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars     # cloud_id, folder_id, service_account_id, ssh key
terraform init && terraform validate && terraform apply   # → ресурсы + hosts.ini

# ── 2. IMAGES (из корня репозитория) ──
cd ../../
yc container registry configure-docker
bash build-and-push.sh        # 6 backend + frontend

# ── 3. CA БД ──
curl -o infra/ansible/files/root.crt https://storage.yandexcloud.net/cloud-certs/CA.pem

# ── 4. DEPLOY (всё одной командой) ──
cd infra/terraform
ansible -m ping all
ansible-playbook ../ansible/deploy-all.yml           # CA → backend+миграции+Kong → frontend
# ansible-playbook ../ansible/observability.yml      # (опц.) Prometheus + Grafana

# ── 5. VERIFY ──
curl http://$(terraform output -raw load_balancer_ip)/health
open  http://$(terraform output -raw load_balancer_ip)/        # витрина (SPA)
```

---

## 11. Траблшутинг

| Симптом | Причина / решение |
|---|---|
| `terraform apply` падает на провайдере / 401 | Нет/неверный `infra/terraform/key.json`, либо у СА не хватает ролей; проверьте `cloud_id`/`folder_id` в `terraform.tfvars`. |
| `time_sleep` / провайдер `time` не найден | Запустите `terraform init` ещё раз — он доустановит `hashicorp/time`. |
| `ansible -m ping` — timeout | SSH идёт через бастион (`ansible_ssh_common_args` в `hosts.ini`). Проверьте, что приватный ключ соответствует `public_ssh_key_path`, бастион доступен, агент ключей запущен (`ssh-add`). |
| Kong отвечает 502/no route | Сервисы не поднялись или закрыты порты. На backend-узле: `docker ps`, `docker logs handmade-<svc>`. Убедитесь, что SG `backend` открывает 8001–8005 (это правка в `network.tf`). |
| Миграции не прошли / 500 у сервисов | Чаще всего БД недоступна или не подложен CA. Проверьте `DB_SSL`/`DB_SSL_ROOT_CERT`, порт **6432**, и что `migrate`-задача отработала (`docker logs` контейнера на первом узле). |
| `/api/v1/seller/sub-orders` уходит не в orders | Маршрут должен иметь `regex_priority=100` (отдельная задача в плейбуке). Проверьте `curl localhost:8001/routes` на Kong-узле. |
| Узел не может скачать образ | У СА backend-группы нет роли `container-registry.images.puller`, либо неверный `registry` в плейбуке. |
| TLS-ошибка к Postgres | Нет/неверный `infra/ansible/files/root.crt`. Либо в VPC через пулер TLS не нужен — `DB_SSL: "false"`. |
| Нужно пересоздать только приложение | Повторный `ansible-playbook ../ansible/deploy-services.yml` (контейнеры пересоздаются). |

---

## 12. Удаление инфраструктуры

```bash
cd infra/terraform
terraform destroy        # снесёт ВМ, кластеры БД/Redis, сеть, балансировщик
```

> ⚠️ `destroy` удалит **Managed PostgreSQL вместе с данными**. Сделайте бэкап
> (или снимите deletion protection осознанно) до этого. `hosts.ini`, `key.json`,
> `terraform.tfstate` остаются локально — не коммитьте их.

---

## Приложение: env-контракт сервисов

Все сервис-контейнеры и worker получают одинаковый набор переменных (поле `app_env`
в [deploy-services.yml](infra/ansible/deploy-services.yml)), который обязан совпадать
с тем, что читает [shared/app/core/config.py](shared/app/core/config.py):

```
DATABASE_URL=postgresql+asyncpg://handmade_user:<pwd>@<pg_host>:6432/handmade_production
DB_HOST=<pg_host>  DB_PORT=6432  DB_USER=handmade_user  DB_PASSWORD=<pwd>  DB_NAME=handmade_production
DB_SSL=true        DB_SSL_ROOT_CERT=/app/certs/root.crt
REDIS_URL=redis://:<pwd>@<redis_host>:6379/0
SECRET_KEY=<gen>   REFRESH_SECRET_KEY=<gen>   JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30   REFRESH_TOKEN_EXPIRE_DAYS=30
# Object Storage (опц. — пусто → локальный диск, только для одной ноды):
S3_ENDPOINT=https://storage.yandexcloud.net  S3_BUCKET=<bucket>  S3_ACCESS_KEY=<k>  S3_SECRET_KEY=<s>  S3_PUBLIC_URL=...
# Postbox SMTP (опц. — пусто → письма в лог):
SMTP_HOST=postbox.cloud.yandex.net  SMTP_PORT=587  SMTP_USER=<key>  SMTP_PASSWORD=<sec>  SMTP_FROM=no-reply@<домен>
FRONTEND_URL=https://<домен>        # для ссылок в письмах
# Наблюдаемость (опц.): SENTRY_DSN=<dsn>  METRICS_ENABLED=true
```

> `S3_*` и `SMTP_*` Terraform кладёт в `[all:vars]` инвентаря (`storage.tf`, `mail.tf`),
> а плейбук прокидывает в каждый контейнер. Sender-домен Postbox (SPF/DKIM) верифицируется
> вручную в консоли/`yc` — это DNS-шаг, Terraform его не делает.

Точка входа образа ([shared/entrypoint.sh](shared/entrypoint.sh)) диспетчеризует
команды `migrate | web | worker | beat | seed`.
