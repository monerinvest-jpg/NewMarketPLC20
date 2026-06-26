# 🚀 Инструкция по запуску маркетплейса

Подробное руководство: как поднять проект локально через Docker, как запускать
сервисы по отдельности при разработке, как проверить работоспособность и что
делать, когда что-то не заводится.

> ☁️ Развёртывание в **Yandex Cloud** (Terraform + Ansible + образы) — в [DEPLOY.md](DEPLOY.md).
> Этот файл — про **локальный** запуск.

---

## 1. Что это за проект (коротко)

Бэкенд разбит на **общую библиотеку** `shared/` (пакет `app`) и **5 независимо
деплоящихся FastAPI-сервисов** + Celery worker/beat. Все сервисы используют **одну
PostgreSQL** (раздельная логика по доменам) и **один Redis** (брокер Celery +
хранилище счётчиков rate-limit). Запросы снаружи идут на единый **gateway**
(локально — nginx, в проде — Kong), который разводит их по сервисам по префиксу пути.

```
                         ┌──────────────────────────┐
  Браузер ──▶ :3000      │  gateway  :8000          │
  (frontend, nginx) ──▶  │  (nginx локально / Kong) │
                         └─────────────┬────────────┘
            ┌──────────────┬───────────┼───────────┬──────────────┐
            ▼              ▼           ▼           ▼              ▼
        identity        catalog      orders      sellers       platform
       auth/users/2fa  товары/      корзина/    тарифы/       уведомления/
                       магазины/    заказы/     промо/        лояльность/
                       отзывы       возвраты    инвентарь     админка
            └──────────────┴───────────┼───────────┴──────────────┘
                                       ▼
                    ┌──────────────────────────────────┐
                    │  PostgreSQL 17   +   Redis        │  ◀── worker / beat (Celery)
                    └──────────────────────────────────┘
```

| Сервис | Префиксы (через gateway `:8000/api/v1/...`) |
|---|---|
| **identity** | `/auth`, `/users`, `/2fa`, `/security` |
| **catalog** | `/products`, `/shops`, `/reviews`, `/categories`, `/variants`, `/attributes`, `/questions`, `/home`, `/recommendations`, `/favorites`, `/catalog`, `/sitemap.xml`, `/uploads` |
| **orders** | `/cart`, `/orders`, `/returns`, `/sub-orders`, `/product-subscriptions`, `/disputes`, `/addresses`, `/wishlists`, `/recently-viewed`, `/delivery`, `/seller/sub-orders` |
| **sellers** | `/seller/*` (магазин, товары, инвентарь, тарифы, промокоды, выплаты, аналитика) |
| **platform** | `/notifications`, `/loyalty`, `/admin/*`, прочее |

---

## 2. Требования

- **Docker** 24+ и **Docker Compose v2** (`docker compose`, не дефис) — основной путь.
- Для локальной разработки без Docker: **Python 3.11+**, **Node.js 18+**, локальные
  **PostgreSQL 17** и **Redis 7**.
- Свободные порты: `3000` (фронтенд), `8000` (gateway), `5432` (Postgres), `6379` (Redis).

---

## 3. Быстрый старт через Docker (рекомендуется)

```bash
# 1. Перейти в каталог проекта
cd marketplace

# 2. Создать .env из шаблона
cp .env.example .env

# 3. (минимум) сгенерировать секреты — см. раздел 4

# 4. Собрать и поднять весь стек
docker compose up -d --build
```

Что произойдёт по порядку (зависимости прописаны в `docker-compose.yml`):

1. Поднимается **`db`** (Postgres) и **`redis`**, ждут healthcheck.
2. One-shot контейнер **`migrate`** прогоняет `alembic upgrade head`, затем сидинг
   (`seed`) — создаёт супер-админа и дефолтные настройки в таблице `settings`.
3. Только после успешного завершения `migrate` стартуют 5 сервисов, `worker`, `beat`,
   `gateway` и `frontend`.

Проверить, что всё поднялось:

```bash
docker compose ps          # все сервисы кроме migrate должны быть Up/healthy
docker compose logs -f gateway   # логи шлюза
```

---

## 4. Настройка `.env` (что важно заполнить)

Файл `.env` читается всеми контейнерами. Для **локального запуска** дефолтов
почти достаточно, но обязательно поменяйте секреты:

```ini
# Сгенерируйте длинные случайные строки (минимум 32 символа):
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=<случайная-строка>
REFRESH_SECRET_KEY=<другая-случайная-строка>   # пусто = переиспользовать SECRET_KEY

# БД и Redis для docker-compose уже настроены на имена контейнеров:
DB_HOST=db
DB_PORT=5432
REDIS_URL=redis://redis:6379/0
```

**Опциональные интеграции** (без ключей всё работает в mock-режиме, бизнес-логику
можно тестировать):

| Переменная | Без неё |
|---|---|
| `YOOKASSA_SHOP_ID` / `YOOKASSA_SECRET_KEY` | платёж создаётся с пустым `confirmation_url`; вебхук не приходит — статус заказа меняем вручную в админке |
| `CDEK_*`, `OZON_*`, `YANDEX_DELIVERY_TOKEN`, `RUSSIAN_POST_*` | доставка считается по mock-формуле, ПВЗ — mock-точки |
| `SMTP_HOST` | письма (сброс пароля, коды) не отправляются, а пишутся в лог сервиса |
| `FIRST_SUPERUSER_EMAIL` / `_PASSWORD` | дефолт `admin@marketplace.com` / `admin123` — **смените в проде** |

> ⚠️ `DB_SSL=false` локально. В Yandex Managed PostgreSQL — `DB_SSL=true` и путь к
> CA-сертификату в `DB_SSL_ROOT_CERT` (см. раздел 9).

---

## 5. Куда заходить после запуска

| Что | Адрес |
|---|---|
| 🛍️ Витрина (фронтенд) | http://localhost:3000 |
| 📚 Swagger конкретного сервиса | http://localhost:8000/api/v1/docs (отдаётся тем сервисом, чей префикс открыт; у каждого сервиса свой openapi) |
| 👑 Админ-панель | http://localhost:3000/admin |
| ❤️ Health шлюза/сервиса | http://localhost:8000/health |

Вход в админку: `admin@marketplace.com` / `admin123` (или ваши значения из `.env`).

---

## 6. Проверка работоспособности (smoke-test)

```bash
# 1. Health сервисов (через gateway)
curl http://localhost:8000/health

# 2. Регистрация пользователя
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test12345","full_name":"Test"}'

# 3. Логин → получить токены
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test12345"}'

# 4. Каталог
curl http://localhost:8000/api/v1/products
```

Полные пользовательские сценарии (покупка, публикация товара продавцом,
рефералка, модерация) — в [README.md](README.md), раздел «Тестирование основных сценариев».

---

## 7. Частые операции

```bash
# Логи одного сервиса
docker compose logs -f orders

# Перезапустить один сервис после правок (с пересборкой)
docker compose up -d --build orders

# Прогнать миграции вручную (one-shot контейнер)
docker compose run --rm migrate sh -c "/app/entrypoint.sh migrate"

# Пересидить дефолтные настройки/админа
docker compose run --rm migrate sh -c "/app/entrypoint.sh seed"

# Зайти в psql
docker compose exec db psql -U marketplace -d marketplace

# Остановить всё
docker compose down

# Остановить + удалить БД и загруженные файлы (полный сброс)
docker compose down -v
```

Команды контейнера диспетчеризуются через `shared/entrypoint.sh`:
`migrate | web | worker | beat | seed` (любой другой аргумент выполняется как есть).

---

## 8. Локальная разработка без Docker

Понадобятся запущенные локально PostgreSQL 17 и Redis 7.

**Бэкенд** (общая библиотека `shared/` + один сервис):

```bash
cd shared
python -m venv venv
# Linux/macOS:
source venv/bin/activate
# Windows PowerShell:
#   .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# .env в корне проекта; для локали выставьте DB_HOST=localhost, DB_PORT=5432,
# REDIS_URL=redis://localhost:6379/0
cp ../.env.example ../.env

alembic upgrade head
python scripts/seed.py

# Запуск конкретного сервиса из КОРНЯ репозитория.
# PYTHONPATH=shared делает пакет `app` импортируемым;
# --app-dir указывает на каталог с main.py сервиса.
cd ..
PYTHONPATH=shared uvicorn --app-dir services/identity main:app --reload --port 8001
#   (аналогично: catalog / orders / sellers / platform)
```

> На Windows PowerShell переменная окружения задаётся отдельно:
> `$env:PYTHONPATH="shared"; uvicorn --app-dir services/identity main:app --reload --port 8001`

Запуск Celery (из корня, с `PYTHONPATH=shared`):

```bash
PYTHONPATH=shared celery -A app.tasks.celery_app worker --loglevel=info
PYTHONPATH=shared celery -A app.tasks.celery_app beat   --loglevel=info
```

**Фронтенд:**

```bash
cd frontend
npm install
cp .env.example .env     # VITE_API_URL=http://localhost:8000
npm run dev              # http://localhost:5173 (Vite dev-server)
```

> Без gateway каждый сервис слушает свой порт. Проще для full-stack локали —
> поднять весь стек через `docker compose up`, а в IDE отлаживать только нужный
> сервис, временно остановив его контейнер.

---

## 9. Заметки для продакшена (Yandex Cloud)

- БД и Redis — **managed-сервисы**; gateway — **Kong**. Инфраструктура (Terraform +
  Ansible) живёт в отдельном репозитории; патч для неё — в
  [infra/STAGE2_INFRA_CHANGES.md](infra/STAGE2_INFRA_CHANGES.md).
- Ansible прокидывает в контейнеры готовый `DATABASE_URL` + `DB_*`, `REDIS_URL`,
  `SECRET_KEY`, `REFRESH_SECRET_KEY`, `JWT_ALGORITHM`, время жизни токенов.
- **TLS к БД:** Managed PostgreSQL требует SSL. Выставьте `DB_SSL=true` и
  `DB_SSL_ROOT_CERT=/app/certs/root.crt` (Yandex CA), либо полагайтесь на in-VPC
  пулер. asyncpg принимает SSL через `connect_args`, а не через `sslmode` в URL —
  это уже учтено в `config.py`.
- Миграции — отдельной one-shot командой `migrate`; сидинг настроек — через psql/Ansible.
- **Rate-limit** теперь общий между репликами (хранилище в Redis) и берёт реальный
  IP из `X-Forwarded-For` — убедитесь, что Kong/nginx прокидывают этот заголовок.

---

## 10. Траблшутинг

| Симптом | Причина / решение |
|---|---|
| Сервисы не стартуют, висят на старте | Не завершился `migrate`. Смотрите `docker compose logs migrate` — обычно недоступна БД или ошибка миграции. |
| `connection refused` к БД локально | `DB_HOST=db` оставлен от docker-режима. Для локали — `DB_HOST=localhost`. |
| 401 на всех запросах после логина | Истёк access-токен — фронтенд сам дёргает `/auth/refresh`. Если refresh-токен невалиден, перелогиньтесь. Проверьте, что `SECRET_KEY`/`REFRESH_SECRET_KEY` не менялись между перезапусками. |
| Платёж создаётся без ссылки оплаты | Не заданы `YOOKASSA_*` — это ожидаемо в mock-режиме. Меняйте статус заказа вручную в `/admin/orders`. |
| Письма не приходят | `SMTP_HOST` пуст — письма пишутся в лог: `docker compose logs identity \| grep -i reset`. |
| Rate-limit срабатывает слишком рано/одинаково на всех | За прокси проверьте, что gateway передаёт `X-Forwarded-For`; счётчики хранятся в Redis (`REDIS_URL` должен быть доступен). |
| Порт занят | Поменяйте маппинг портов в `docker-compose.yml` или освободите 3000/8000/5432/6379. |
| Нужен полный сброс | `docker compose down -v && docker compose up -d --build`. |

---

## 11. Что было недавно укреплено (важно при тестировании заказов)

- **Защита от oversell:** резервирование остатка при оформлении заказа теперь
  атомарно (блокировка строки `SELECT ... FOR UPDATE` + повторная проверка), два
  параллельных заказа на последний товар больше не уводят склад в минус.
- **Идемпотентность вебхука YooKassa:** повторная доставка уведомления не задваивает
  возврат склада/балансов (YooKassa повторяет вебхуки до ответа 200).
- **Единый «реверс» заказа:** при любой отмене (оплаченной и неоплаченной)
  одинаково возвращаются склад, бонусы, промо-баланс и слот купона.

Полный разбор правок и оставшихся рекомендаций — в истории ревью проекта.
