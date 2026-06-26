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
4. [Шаг 2 — собрать и запушить образы](#4-шаг-2--собрать-и-запушить-6-образов)
5. [Шаг 3 — CA-сертификат БД](#5-шаг-3--ca-сертификат-managed-postgresql)
6. [Шаг 4 — Ansible: выкатить приложение](#6-шаг-4--ansible-выкатить-приложение)
7. [Шаг 5 — проверка](#7-шаг-5--проверка)
8. [Обновление приложения](#8-обновление-приложения-новый-релиз)
9. [Фронтенд](#9-фронтенд)
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
- **Вариант A** (по умолчанию) — все сервисы на общей backend-группе. **Вариант B**
  (по группе на сервис) — опционально, см. `infra/terraform/variant-b/`.

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

## 4. Шаг 2 — собрать и запушить 6 образов

Реестр по умолчанию — `cr.yandex/crp8b0ggroptcd9dso2t` (зашит в
[deploy-services.yml](infra/ansible/deploy-services.yml), переменная `registry`).
Свой реестр: `yc container registry create --name handmade` → подставьте его id.

Сборка — **из корня репозитория приложения** (контекст `.`, у каждого сервиса свой
Dockerfile; `worker` — тот же образ, запускается командой `worker`/`beat`):

```bash
# из корня marketplace/
yc container registry configure-docker        # один раз: логин docker в cr.yandex
REG=cr.yandex/crp8b0ggroptcd9dso2t

for s in identity catalog orders sellers platform worker; do
  docker build -f services/$s/Dockerfile -t $REG/handmade-$s:latest .
  docker push $REG/handmade-$s:latest
done
```

> Backend-узлы скачивают образы по IAM-токену из метаданных (роль
> `container-registry.images.puller` у СА группы) — отдельный `docker login` на узлах
> не нужен, плейбук делает его сам.

---

## 5. Шаг 3 — CA-сертификат Managed PostgreSQL

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

# Выкат:
ansible-playbook ../ansible/deploy-services.yml
```

Что делает плейбук по шагам:

1. **Секреты:** генерирует общие `SECRET_KEY` / `REFRESH_SECRET_KEY` (по разу на все узлы).
2. **Docker:** ставит при необходимости, логинит в Container Registry по IAM-токену.
3. **CA:** раскладывает `root.crt` → `/opt/handmade/certs/`.
4. **Миграции:** один раз гоняет `migrate` + `seed` образом `handmade-identity`
   (общая схема, супер-админ и дефолтные настройки в таблице `settings`).
5. **Сервисы:** на каждом backend-узле — `handmade-{identity,catalog,orders,sellers,
   platform}` на портах 8001–8005, `--restart always`.
6. **Воркеры:** один `handmade-worker` и один `handmade-beat` на первом узле.
7. **Kong:** по одному service+route на префикс (`strip_path=false`), плюс
   высокоприоритетный маршрут `/api/v1/seller/sub-orders` → orders (чтобы его не
   перехватил широкий `/api/v1/seller`).

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
# 1. Пересобрать и запушить изменённые образы (см. шаг 2)
# 2. Повторно прогнать плейбук — контейнеры пересоздаются (docker rm -f && docker run)
cd infra/terraform
ansible-playbook ../ansible/deploy-services.yml
```

Миграции в плейбуке идемпотентны (`alembic upgrade head`). Изменения инфраструктуры
(сайзинг, число узлов) — через `terraform apply`.

---

## 9. Фронтенд

Фронтенд (`frontend/`) — статика Vite за nginx. Варианты публикации:

- Отдельный контейнер/ВМ с nginx (как сервис `frontend` в
  [docker-compose.yml](docker-compose.yml)); при сборке передайте
  `VITE_API_URL=http://<load_balancer_ip>`.
- Или Object Storage + CDN: `cd frontend && npm ci && VITE_API_URL=http://$LB npm run build`,
  выложить содержимое `frontend/dist/`.

Адрес фронтенда добавьте в `BACKEND_CORS_ORIGINS` (поле `app_env` в плейбуке), иначе
браузер заблокирует запросы CORS.

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
for s in identity catalog orders sellers platform worker; do
  docker build -f services/$s/Dockerfile -t cr.yandex/crp8b0ggroptcd9dso2t/handmade-$s:latest .
  docker push cr.yandex/crp8b0ggroptcd9dso2t/handmade-$s:latest
done

# ── 3. CA БД ──
curl -o infra/ansible/files/root.crt https://storage.yandexcloud.net/cloud-certs/CA.pem

# ── 4. DEPLOY ──
cd infra/terraform
ansible -m ping all
ansible-playbook ../ansible/deploy-services.yml

# ── 5. VERIFY ──
curl http://$(terraform output -raw load_balancer_ip)/health
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
```

Точка входа образа ([shared/entrypoint.sh](shared/entrypoint.sh)) диспетчеризует
команды `migrate | web | worker | beat | seed`.
