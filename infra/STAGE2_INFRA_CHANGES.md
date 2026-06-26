# Этап 2 — изменения в инфра-репозитории (Terraform/Ansible)

> Этот файл — **референс-патч** для репозитория `skboyinboxru/Hand-Made`
> (`terraform/` + `Ansible/`). Сам код приложения уже разбит на сервисы в этом
> репозитории; ниже — что нужно изменить в инфраструктуре, чтобы их выкатить.
> Рекомендованный вариант: **несколько контейнеров на той же backend-группе**
> (Terraform почти не меняется, основное — Ansible + Kong).

---

## 1. Образы и порты

Вместо одного `handmade-backend` собираются 6 образов и пушатся в Yandex Container Registry.
На каждом backend-узле запускается по контейнеру на своём порту (контейнер всегда слушает 8000):

| Сервис | Образ | Порт на узле | Команда |
|---|---|---|---|
| identity | `cr.yandex/<reg>/handmade-identity:latest` | 8001 | `web` |
| catalog  | `cr.yandex/<reg>/handmade-catalog:latest`  | 8002 | `web` |
| orders   | `cr.yandex/<reg>/handmade-orders:latest`   | 8003 | `web` |
| sellers  | `cr.yandex/<reg>/handmade-sellers:latest`  | 8004 | `web` |
| platform | `cr.yandex/<reg>/handmade-platform:latest` | 8005 | `web` |
| worker   | `cr.yandex/<reg>/handmade-worker:latest`   | —    | `worker` / `beat` |

Сборка (контекст = корень репозитория приложения):
```bash
docker build -f services/identity/Dockerfile -t cr.yandex/<reg>/handmade-identity:latest .
docker build -f services/catalog/Dockerfile  -t cr.yandex/<reg>/handmade-catalog:latest  .
docker build -f services/orders/Dockerfile   -t cr.yandex/<reg>/handmade-orders:latest   .
docker build -f services/sellers/Dockerfile  -t cr.yandex/<reg>/handmade-sellers:latest  .
docker build -f services/platform/Dockerfile -t cr.yandex/<reg>/handmade-platform:latest .
docker build -f services/worker/Dockerfile   -t cr.yandex/<reg>/handmade-worker:latest   .
```

Env-контракт у всех сервис-контейнеров **тот же**, что и раньше (DATABASE_URL, DB_*, REDIS_URL,
SECRET_KEY, REFRESH_SECRET_KEY, JWT_ALGORITHM, ACCESS/REFRESH_TOKEN_EXPIRE_*). Один сервис требует
доп. флаги TLS к Managed PG: **`DB_SSL=true`** и **`DB_SSL_ROOT_CERT=/app/certs/root.crt`**
(прокинуть CA Yandex в контейнеры) — это распространяется на все сервисы и worker.

## 2. Миграции (один раз, до старта сервисов)

Миграции прогоняются одним job'ом любым сервис-образом (схема общая):
```bash
docker run --rm <env...> cr.yandex/<reg>/handmade-identity:latest migrate
```
Сидирование `settings` остаётся как есть (psql на бастионе) или `... :latest seed`.

## 3. Kong — маршруты по префиксам (главное изменение)

Вместо одного service+route `/api/v1` создаётся **по service+route на префикс**. Каждый top-level
префикс принадлежит ровно одному сервису (разнесено в коде, см. `services/*/main.py`).
`strip_path=false` — путь пробрасывается как есть. Health-check Kong остаётся `/health` на каждом
сервисе.

| Префикс пути | Сервис | upstream |
|---|---|---|
| `/api/v1/auth`, `/api/v1/users`, `/api/v1/2fa` | identity | `<node>:8001` |
| `/api/v1/products`, `/shops`, `/reviews`, `/categories`, `/variants`, `/attributes`, `/questions`, `/home`, `/recommendations`, `/favorites`, `/catalog`, `/sitemap.xml`, `/uploads` | catalog | `<node>:8002` |
| `/api/v1/cart`, `/orders`, `/returns`, `/sub-orders`, `/product-subscriptions`, `/disputes`, `/addresses`, `/wishlists`, `/recently-viewed`, `/delivery` | orders | `<node>:8003` |
| `/api/v1/seller/sub-orders` (приоритетнее `/seller`) | orders | `<node>:8003` |
| `/api/v1/seller`, `/subscription`, `/promotions`, `/upload` | sellers | `<node>:8004` |
| `/api/v1/notifications`, `/chat`, `/support`, `/gift-certificates`, `/loyalty`, `/currencies`, `/reports`, `/admin` | platform | `<node>:8005` |

> **Важно:** маршрут `/api/v1/seller/sub-orders` должен иметь **больший `regex_priority`**
> (или быть более специфичным), чем `/api/v1/seller`, иначе он перехватится sellers-сервисом.

### Пример конфигурации Kong (Admin API, как в текущем `deploy-backend.yml`)

```bash
# Шаблон: для каждой строки таблицы
create_service() { # name host port
  curl -s -X PUT http://localhost:8001/services/$1 \
    -d url="http://$2:$3"
}
create_route() {  # service paths... (через запятую)
  curl -s -X POST http://localhost:8001/services/$1/routes \
    -d "paths[]=$2" -d strip_path=false -d "regex_priority=${3:-0}"
}

NODE="<первый backend-узел или внутренний LB сервисов>"

create_service identity $NODE 8001
create_service catalog  $NODE 8002
create_service orders   $NODE 8003
create_service sellers  $NODE 8004
create_service platform $NODE 8005

# identity
for p in /api/v1/auth /api/v1/users /api/v1/2fa; do create_route identity $p; done
# catalog
for p in /api/v1/products /api/v1/shops /api/v1/reviews /api/v1/categories \
         /api/v1/variants /api/v1/attributes /api/v1/questions /api/v1/home \
         /api/v1/recommendations /api/v1/favorites /api/v1/catalog \
         /api/v1/sitemap.xml /uploads; do create_route catalog $p; done
# orders
for p in /api/v1/cart /api/v1/orders /api/v1/returns /api/v1/sub-orders \
         /api/v1/product-subscriptions /api/v1/disputes /api/v1/addresses \
         /api/v1/wishlists /api/v1/recently-viewed /api/v1/delivery; do create_route orders $p; done
create_route orders /api/v1/seller/sub-orders 100   # выше приоритет, чем /seller
# sellers
for p in /api/v1/seller /api/v1/subscription /api/v1/promotions /api/v1/upload; do create_route sellers $p; done
# platform
for p in /api/v1/notifications /api/v1/chat /api/v1/support /api/v1/gift-certificates \
         /api/v1/loyalty /api/v1/currencies /api/v1/reports /api/v1/admin; do create_route platform $p; done
# health (любой сервис)
create_route identity /health
```

## 4. Terraform

- **Минимальный вариант (рекомендуется):** изменений почти нет — все контейнеры живут на
  существующей `backend` instance-group, Kong target-group и NLB не трогаются. Достаточно того,
  что Ansible запускает 6 контейнеров на узлах группы.
- **Вариант масштабирования (позже):** вынести каждый сервис в свою
  `yandex_compute_instance_group` + `yandex_alb_target_group`, чтобы масштабировать независимо.
  Тогда в таблице Kong `upstream` указывает на внутренний адрес соответствующей группы, а не на
  один узел. Это отдельная итерация, не требуется для запуска.

## 5. Чек-лист выката

1. Завести 6 репозиториев образов в Yandex Container Registry.
2. CI/Ansible: собрать и запушить 6 образов.
3. Прогнать `migrate` (один job).
4. Запустить контейнеры сервисов (8001–8005) + worker + beat на backend-группе с env-контрактом
   (+ `DB_SSL`/CA для Managed PG).
5. Сконфигурировать Kong по таблице §3 (не забыть приоритет `/seller/sub-orders`).
6. Проверить `/health` каждого сервиса через Kong и ключевой сценарий каждого домена.
