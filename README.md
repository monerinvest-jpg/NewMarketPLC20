# 🪵 Маркетплейс — Wildberries × Etsy (изделия ручной работы)

Полнофункциональный маркетплейс с прямыми продавцами: физические и **цифровые**
товары, **встроенная LMS** (курсы/уроки/тесты/сертификаты), **изготовление на
заказ**, пожизненная реферальная программа, гибкие комиссии, мультидоставка,
оплата частями (BNPL) и глубокая админ-панель. Backend — FastAPI (async,
микросервисы на общей БД), frontend — React + TypeScript (antd), очереди —
Celery + Redis, БД — **PostgreSQL** (Yandex Managed PostgreSQL в проде).

> **Архитектура: микросервисы на общей БД.** Backend разбит на shared-библиотеку
> (`shared/`) и 5 независимо деплоящихся сервисов (`services/identity`, `catalog`,
> `orders`, `sellers`, `platform`) + `worker`. Маршрутизация — через API-gateway
> (**Kong** в проде, **nginx** локально) по префиксам пути. Фронтенд —
> **отдельный контейнер** за тем же edge, обращается к API по относительному
> `/api/v1` (не зашит хост бэка). Развёртывание — Yandex Cloud (Terraform +
> Ansible), БД/Redis/Object Storage/Postbox — managed-сервисы.

---

## 📐 Архитектура

> 📖 Локальный запуск (Docker) — в [RUN.md](RUN.md). Развёртывание в Yandex Cloud
> (Terraform + Ansible) — в [DEPLOY.md](DEPLOY.md). Дорожная карта — в
> [FEATURE_PLAN.md](FEATURE_PLAN.md).

```
Браузер ─▶ NLB:80 ─▶ Kong (единый edge, :8000)
                       ├─ /api/v1/auth,/users,/2fa            → identity
                       ├─ /api/v1/products,/courses,/shops,…   → catalog
                       ├─ /api/v1/cart,/orders,/delivery,…     → orders
                       ├─ /api/v1/seller,/subscription,…       → sellers
                       ├─ /api/v1/admin,/loyalty,/support,…    → platform
                       └─ /  (catch-all)                       → frontend (nginx SPA)
                                   │
        ┌──────────────────────────┼───────────────────────────┐
        ▼                          ▼                            ▼
  PostgreSQL (общая БД)      Redis (Celery + кэш)        Celery worker/beat
        │
        ├─ Object Storage (S3): картинки (public) + цифровые товары/HLS (private)
        ├─ Postbox (SMTP): письма-подтверждения и уведомления
        └─ Prometheus + Grafana + Sentry: метрики и наблюдаемость
   Внешние: YooKassa (оплата) · СДЭК/Ozon/Яндекс/Почта (доставка) · SMSC.ru (SMS)
```

**Стек и решения**
- **FastAPI + SQLAlchemy 2.0 async** — неблокирующий I/O для вебхуков и внешних API.
- **Celery + Redis** — фоновые задачи (автозавершение заказов, рассылки, HLS-упаковка, распад лояльности).
- **Абстрактные шлюзы** (`BasePaymentGateway`, `BaseDeliveryGateway`, BNPL, SMTP) — mock-режим без ключей, реальные интеграции через настройки.
- **Настройки в БД** — комиссии, бонусы, цены VIP/упаковки, службы доставки и т.д. меняются в админке без передеплоя.
- **RBAC** — гранулярные права, привязанные к разделам меню админки; мультиаккаунт магазина (сотрудники с правами).
- **Наблюдаемость из коробки** — `/metrics` (Prometheus) на каждом сервисе, Sentry, Grafana-дашборды.

---

## ✨ Возможности

**Каталог и покупки**
- Товары: физические / **цифровые (мгновенная выдача)** / **курсы**; варианты, атрибуты, дерево категорий, вопросы-ответы.
- Отзывы: премодерация, **фото и видео покупателей**, бейдж «Проверенная покупка», галерея медиа, ответы продавца, голоса «полезно».
- Поиск (БД ILIKE + опц. Meilisearch), рекомендации «с этим покупают», избранное, коллекции, сравнение, недавно просмотренные.
- Корзина, **мультимагазинные заказы**, подписки на товар (back-in-stock / снижение цены).

**Обучение (встроенная LMS)**
- Курсы/модули/уроки, защита контента (вотермарк, запрет скачивания, **HLS + AES-128** видео), **тесты** (серверная проверка), **сертификаты** (PDF, кириллица, проверка по коду).
- **Академия продавца** — бесплатные обучающие курсы от площадки в кабинете продавца.

**Оплата и доставка**
- **YooKassa** + 54-ФЗ фискализация (чеки в ОФД).
- **BNPL / оплата частями («Сплит»)** — провайдер платит площадке сразу, покупатель гасит частями по графику.
- **Мультидоставка**: СДЭК / Ozon / Яндекс / Почта России — **сравнение тарифов**, ПВЗ, трек-номера, ярлыки; включение служб в админке.
- Оплата бонусами, промо-балансом и **реферальным балансом до 100%**; **подарочная упаковка + открытка**.

**Лояльность и маркетинг**
- **Пожизненная реферальная программа**: процент со всех покупок/продаж приглашённых, выводимый баланс, оплата до 100% заказа.
- Подарочные сертификаты (+ отправка получателю), промо-баланс, **уровни лояльности** (кэшбэк, перки, распад по неактивности).
- Купоны, акции/наборы, продвижение (аукцион платных мест), **email/push-кампании с сегментами** (Postbox, отписка).

**Продавцам**
- Магазин, товары, заказы, аналитика/ROI, выводы средств (реквизиты, налоговые режимы), тарифы/подписки, склад, CSV-импорт, флеш-сейлы.
- **Сотрудники магазина** (мультиаккаунт с правами), **KYC + бейджи доверия (Проверенный / VIP)**, **изготовление на заказ** (запрос→оферта→производство).

**Покупателям и доверие**
- Профиль, адреса, 2FA, возвраты, **арбитраж споров**, поддержка (тикеты с SLA), чат с продавцом, мультивалютность.

**Админ-панель**
- 360°-карточки пользователей и магазинов, **полное редактирование** объектов (пользователи/магазины/заказы), управление ролями и **правами↔меню**, корректировка балансов.
- Аналитика платформы с **финансовым блоком** (прибыль, выплаты, обязательства), когорты/LTV, реконсиляция, фискальные чеки.
- Очередь модерации, **верификация продавцов (KYC)**, выплаты с **анти-фрод сигналами**, рассылки, **метрики (Grafana)**, настройки, аудит-лог, feature flags, SMS, валюты.

**Платформа**
- **i18n (RU/EN)** с переключателем, **кэш (Redis)**, **оптимизация изображений (WebP)**, **наблюдаемость** (Sentry/Prometheus/Grafana), **CI/CD** (GitHub Actions).

---

## 📁 Структура

```
marketplace/
├── shared/                      # Общая библиотека backend
│   ├── app/
│   │   ├── core/                # config, database, security, ratelimit
│   │   ├── models/models.py     # Все ORM-модели
│   │   ├── schemas/schemas.py   # Pydantic v2
│   │   ├── services/            # commission, referral, payment, delivery, bnpl,
│   │   │                        #   trust, campaign, cache, image, gift, loyalty…
│   │   ├── api/v1/endpoints/     # auth, products, orders, shops, admin, academy,
│   │   │                        #   custom_orders, reviews, misc, …
│   │   ├── tasks/               # Celery (автозаказы, рассылки, HLS, лояльность)
│   │   └── service_factory.py   # Фабрика FastAPI (CORS, /health, Sentry, /metrics)
│   ├── alembic/versions/        # Миграции 0001 → 0015
│   └── requirements.txt
├── services/                    # 5 сервисов + worker (каждый — свой main.py + Dockerfile)
│   ├── identity/ catalog/ orders/ sellers/ platform/ worker/
├── frontend/                    # React + TS + antd (Vite → nginx)
│   ├── src/ (api, store, components/layout, pages, i18n.ts, types)
│   ├── Dockerfile  nginx.conf
├── gateway/nginx.conf           # Локальное зеркало Kong-маршрутов
├── infra/
│   ├── terraform/               # VPC, Managed PG/Redis, IG, NLB, storage.tf, mail.tf
│   └── ansible/                 # deploy-services.yml, deploy-frontend.yml, observability.yml
├── .github/workflows/           # ci.yml (lint+test+build) · deploy.yml (build&push+deploy)
├── docker-compose.yml           # Локальный запуск всего стека
└── README.md  RUN.md  DEPLOY.md  PROGRESS.md  FEATURE_PLAN.md
```

---

## 🚀 Быстрый старт (локально)

```bash
cp .env.example .env          # заполните SECRET_KEY (ключи YooKassa/CDEK/SMTP — опц.)
docker compose up -d --build  # PG + Redis + gateway + 5 сервисов + worker/beat + frontend
```

- Витрина: `http://localhost:3000` · API: `http://localhost:8000/api/v1/*`
- Миграции + сидинг выполняет one-shot контейнер `migrate` (общая БД); сервисы ждут его.
- Без ключей всё работает в mock-режиме (доставка по формуле, ПВЗ-заглушки, письма в лог).

Подробности локального запуска — в [RUN.md](RUN.md).

---

## ⚙️ CI/CD

- **`.github/workflows/ci.yml`** — на каждый push/PR: backend (compileall + `pytest`), frontend (`npm ci` + `vite build`).
- **`.github/workflows/deploy.yml`** — ручной запуск: сборка и пуш 6 backend-образов + **отдельного frontend-образа** в Yandex Container Registry, опциональный Ansible-редеплой.

---

## 🔑 Ключевые настройки (`.env` / админка)

| Переменная | Назначение |
|---|---|
| `SECRET_KEY` / `REFRESH_SECRET_KEY` | подпись JWT |
| `DATABASE_URL` / `DB_*` | PostgreSQL (пул 6432 в проде, TLS через `DB_SSL`) |
| `REDIS_URL` | Redis (Celery + кэш) |
| `YOOKASSA_*`, `CDEK_*`, `OZON_*`, `YANDEX_DELIVERY_*`, `RUSSIAN_POST_*` | платёж/доставка |
| `S3_*` | Object Storage (картинки + цифровые товары/HLS) |
| `SMTP_*` | Postbox (письма) |
| `SENTRY_DSN`, `METRICS_ENABLED` | наблюдаемость |

Бизнес-настройки (комиссии, бонусы %, цена упаковки, BNPL, VIP/KYC-пороги, службы
доставки, Grafana-URL и др.) хранятся **в БД** и меняются в админке без передеплоя.

---

Полный список реализованного — в [PROGRESS.md](PROGRESS.md). Планы — в [FEATURE_PLAN.md](FEATURE_PLAN.md).
