# Этап 2 — разбиение монолита на сервисы (план к согласованию)

> Статус: **черновик для согласования**. Код не меняется до утверждения.
> Предпосылки: Этап 1 (PostgreSQL + адаптация под Yandex-инфру) завершён.
> Решение по гранулярности: **сервисы на ОБЩЕЙ Managed PostgreSQL** (не БД-на-сервис).

---

## 1. Целевая модель

Монолит `app/` распадается на **shared-библиотеку** + **6 независимо деплоящихся сервисов**.
Все сервисы используют одну Managed PostgreSQL (разделение по PostgreSQL-схемам), один
Managed Redis, и публикуются через Kong по префиксам пути.

```
                         ┌────────── Kong (маршрутизация по префиксу) ──────────┐
 NLB:80 → Kong:8000 →    │ /api/v1/auth,/users,/2fa        → identity  :8001     │
                         │ /api/v1/products,/shops,/reviews → catalog   :8002     │
                         │ /api/v1/cart,/orders,/returns    → orders    :8003     │
                         │ /api/v1/seller,/subscriptions    → sellers   :8004     │
                         │ /api/v1/loyalty,/notifications,/admin → platform :8005 │
                         └───────────────────────────────────────────────────────┘
                                   все сервисы → Managed PostgreSQL + Redis
```

### Почему общая БД, а не БД-на-сервис
Монолит имеет плотные перекрёстные FK (`Order`→`User`/`Product`/`Shop`, `Payout`→`Order`…).
Разрыв на отдельные БД потребовал бы межсервисных API/событий и распределённых транзакций —
многонедельная переделка. Общая БД с разделением по схемам даёт независимый деплой и
изоляцию кода при сохранении ссылочной целостности. Это согласованное решение.

---

## 2. Структура репозитория после Этапа 2

```
marketplace/
├── shared/                         # устанавливается в каждый сервис (pip install -e ./shared)
│   ├── pyproject.toml
│   └── marketplace_shared/
│       ├── core/                   # config.py, database.py, security.py, ratelimit.py
│       ├── models/                 # models.py (единый источник схемы для всех сервисов)
│       ├── schemas/                # schemas.py (общие Pydantic-схемы)
│       ├── deps.py                 # JWT/роли (общие зависимости)
│       └── services/               # КРОСС-доменное: settings, email, sms, storage,
│                                   #   notification, audit, rbac, currency
├── services/
│   ├── identity/   app/main.py  Dockerfile  requirements.txt
│   ├── catalog/    app/main.py  Dockerfile  requirements.txt
│   ├── orders/     app/main.py  Dockerfile  requirements.txt
│   ├── sellers/    app/main.py  Dockerfile  requirements.txt
│   └── platform/   app/main.py  Dockerfile  requirements.txt
├── migrations/                     # ЕДИНЫЙ Alembic на общую БД (живёт отдельно от сервисов)
│   ├── alembic.ini  env.py  versions/
├── frontend/                       # без изменений (ходит на /api/v1/* через Kong)
├── docker-compose.yml              # локальный прогон всех сервисов сразу
└── backend/                        # УДАЛЯЕТСЯ после переноса (это и есть «убрать монолит»)
```

> **Миграции:** остаются ЕДИНЫМИ на общую БД (один Alembic), запускаются одним job'ом
> `migrate` до старта сервисов. Сервисы не владеют схемой по отдельности — владеет shared.models.

---

## 3. Распределение роутеров по сервисам

| Сервис | Роутеры (из `app/api/v1/__init__.py`) | Префиксы Kong |
|---|---|---|
| **identity** | auth, users, twofa | `/api/v1/auth`, `/api/v1/users`, `/api/v1/2fa`, `/api/v1/security` |
| **catalog** | products, products_extra, categories, shops, reviews, recommendations, catalog_extra (facets/Q&A/attributes/compare), home, seo, favorites | `/api/v1/products`, `/shops`, `/reviews`, `/categories`, `/catalog`, `/home`, `/sitemap.xml`, `/favorites` |
| **orders** | cart, orders, returns_orders, disputes, delivery, buyer_extra (адреса/вишлисты/просмотры) | `/api/v1/cart`, `/orders`, `/sub-orders`, `/returns`, `/disputes`, `/delivery` |
| **sellers** | seller_tools, seller_inventory, seller_extra, subscription, promo, promotions, promo_rules | `/api/v1/seller`, `/subscriptions`, `/promotions`, `/promo` |
| **platform** | notifications, support, gifts, loyalty, currency, reports, admin | `/api/v1/notifications`, `/support`, `/gifts`, `/loyalty`, `/currencies`, `/reports`, `/admin` |

> Точные префиксы сверяются с реальными `prefix=`/`tags=` в каждом роутере на шаге реализации.
> Celery worker/beat — отдельный деплой, импортирует задачи из всех доменов через shared
> (или выносится в свой сервис `worker`). По умолчанию: один `worker`-образ на базе shared.

---

## 4. Что меняется в КОДЕ (этот workspace)

1. **Вынести shared-пакет** `marketplace_shared` (модели, core, security, deps, кросс-сервисы).
   `from app.core...` → `from marketplace_shared.core...` по всему коду (механическая замена импортов).
2. **5 сервисных приложений**: каждый `app/main.py` собирает свой `APIRouter` только из своих
   роутеров, свой CORS/limiter, свой `/health`. Слушают :8000 внутри контейнера.
3. **Dockerfile на сервис** (на базе текущего): ставит `shared` + свои requirements,
   тот же `entrypoint.sh` (`web`/`worker`).
4. **Единый Alembic** в `migrations/` (перенести из `backend/alembic`).
5. **docker-compose.yml** — поднимает Postgres + Redis + 5 сервисов + worker/beat локально,
   плюс лёгкий локальный Kong/Nginx для маршрутизации (имитация прода).
6. **Удалить `backend/`** после переноса (монолит убран).
7. **Frontend** — без изменений: продолжает ходить на `/api/v1/*`, Kong разводит по сервисам.

## 5. Что меняется в ИНФРЕ (отдельный репозиторий — нужны ваши правки)

> Этот репозиторий отсюда недоступен для редактирования. Привожу точный список правок.

**Минимально-инвазивный вариант (рекомендуется): несколько контейнеров на той же backend-группе.**
Kong маршрутизирует по префиксу на разные порты одного backend-узла — Terraform почти не меняется.

- **Ansible (`deploy-backend.yml`)**:
  - Собрать/запушить 5 образов вместо одного:
    `cr.yandex/<reg>/handmade-{identity,catalog,orders,sellers,platform}:latest` (+ `handmade-worker`).
  - Запускать на backend-узлах 5 контейнеров на портах 8001–8005 (+ worker) с тем же env-контрактом.
  - Job `migrate` — один раз против общей БД (как сейчас).
  - Kong: вместо одного service/route — **по service+route на каждый префикс** (таблица из §3),
    `upstream` → `localhost:800X` соответствующего сервиса.
- **Terraform**: при варианте «контейнеры на общей IG» — изменения минимальны (health-check
  Kong остаётся :8000). При желании масштабировать сервисы независимо — добавить отдельные
  `yandex_compute_instance_group` + `target_group` на сервис (это вариант роста, не обязателен сразу).
- **Registry**: создать 5–6 репозиториев образов в Yandex Container Registry.

**Вариант роста (позже): отдельная instance-группа на сервис** — полноценная горизонтальная
независимость, но заметные правки Terraform (N групп, N таргет-групп, политики).

---

## 6. Порядок выполнения (поэтапно и проверяемо)

1. Вынести `shared` + перевести монолит на импорты из него (монолит ещё цел, прогон на PG).
2. Поднять **identity** как первый отдельный сервис; Kong-route `/api/v1/auth*` → identity,
   остальное → старый backend. Проверить логин/регистрацию через Kong.
3. Поочерёдно вынести catalog → orders → sellers → platform, каждый раз переключая Kong-route
   и проверяя домен. Монолит «сдувается» по мере переноса.
4. Когда все роутеры мигрированы — **удалить `backend/`** (монолит убран), обновить compose/README.
5. Параллельно инфра-команда заводит образы/маршруты Kong по §5.

**Критерий готовности каждого шага:** `/health` сервиса зелёный через Kong, ключевой сценарий
домена проходит, остальные домены не сломаны (общая БД, единый Alembic).

---

## 7. Риски и решения

| Риск | Решение |
|---|---|
| Дубль кросс-сервисной логики (settings/notifications/auth) | Вынесены в `shared`, импортируются всеми |
| Рассинхрон схемы между сервисами | Единый Alembic + единый `shared.models` — один владелец схемы |
| Kong-маршруты в инфра-репо отстают от кода | Жёсткая таблица префиксов §3 как контракт между репозиториями |
| TLS к Managed PG | Уже решено в Этапе 1 (`DB_SSL`/CA); распространяется на все сервисы через shared |
| Celery-задачи ссылаются на все домены | Worker собирается на shared (видит все модели/задачи) |
```
