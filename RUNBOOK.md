# 📖 RUNBOOK — эксплуатация маркетплейса

Документ для дежурного: как проверить, что всё живо, где смотреть, что делать
при сбое. Полная инструкция по развёртыванию — в [DEPLOY.md](DEPLOY.md).

---

## 1. Карта системы

```
Пользователь → NLB :80 → Kong :8000 (2 ноды) → upstreams:
                                   ├─ identity :8001 ┐
                                   ├─ catalog  :8002 │  backend-группа (2 ноды),
                                   ├─ orders   :8003 │  + worker/beat/meilisearch
                                   ├─ sellers  :8004 │    (на первой ноде)
                                   ├─ platform :8005 ┘
                                   └─ frontend :3000 (SPA, обе ноды)
Managed PostgreSQL 17 (пулер :6432, TLS) · Managed Redis/Valkey :6379
Бастион (публ. IP): SSH-jump + Grafana :3000 (публ.) · Prometheus :9090,
Loki :3100, Alertmanager :9093 (только VPC)
```

- Все контейнеры — `--restart always`: после перезагрузки ноды поднимаются сами.
- Kong балансирует на обе backend-ноды; упавшая нода выводится health-check'ом.

## 2. Доступы

| Что | Как |
|---|---|
| Ops-ВМ (деплой) | `ssh it@10.0.0.122`, рабочая копия `/home/it/testmarkettoday` |
| Бастион | `ssh ubuntu@<bastion_ip>` (IP: `terraform output bastion_public_ip`) |
| Ноды backend/kong | c ops-ВМ/бастиона: `ssh ubuntu@192.168.x.x` (IP в `infra/terraform/hosts.ini`) |
| Grafana | `http://<bastion_ip>:3000` (просмотр аноним; admin/`changeme` — сменить!) |
| Prometheus/Alertmanager | SSH-туннель: `ssh -L 9090:localhost:9090 ubuntu@<bastion_ip>` |
| Секреты (пароли БД/Redis/S3/Meili) | генерирует Terraform → `infra/terraform/hosts.ini` `[all:vars]` (не в git) |
| Админка сайта | `http://<lb_ip>/admin` — суперадмин из seed (пароль сменить при первом запуске!) |

## 3. Ежедневная проверка (1 минута)

```bash
curl -s http://<lb_ip>/health            # {"status":"ok","service":"identity"}
curl -s http://<lb_ip>/api/v1/products | head -c 200   # каталог отвечает
```
Grafana → дашборд **Marketplace**: 5xx = 0, p95 < 1с, все сервисы up.
Alertmanager (:9093 через туннель) — нет firing-алертов.

## 4. Включить / выключить проект (пауза → экономия)

```bash
cd /home/it/testmarkettoday
./infra/scripts/project-power.sh status|stop|start
```
После **start** (5–10 мин на подъём кластеров):
1. IP бастиона сменился → `cd infra/terraform && terraform apply` (перегенерит hosts.ini);
2. если менялся код — пересобрать образы и передеплоить (см. §5);
3. поправить `grafana_dashboard_url` в админке (Метрики) на новый IP бастиона;
4. проверка §3.

## 5. Деплой обновления

```bash
# на ops-ВМ, из /home/it/testmarkettoday
git pull
bash build-and-push.sh                    # образы: 6 backend + frontend
cd infra/terraform
ansible-playbook ../ansible/deploy-all.yml        # CA → Kong → сервисы+миграции → фронт
ansible-playbook ../ansible/observability.yml     # если менялась наблюдаемость
```
Только фронт: `ansible-playbook ../ansible/deploy-frontend.yml`.
Тесты перед деплоем: `cd shared && python -m pytest tests -q` (26 зелёных).

## 6. Откат релиза

Образы в registry тегируются `latest` — для отката:
```bash
# 1. откатить код и пересобрать
git revert <bad_commit> && bash build-and-push.sh
# 2. передеплой
ansible-playbook ../ansible/deploy-services.yml
```
Миграции БД вперёд-совместимы (ADD COLUMN IF NOT EXISTS); настоящий даунгрейд
схемы не поддерживаем — при аварии восстанавливаемся из бэкапа (§8).

## 7. Инциденты

### Сайт не открывается совсем
1. `project-power.sh status` — всё RUNNING/ACTIVE?
2. `curl -sv http://<lb_ip>/` — если коннект есть, но 502/504 → Kong жив, умерли ноды.
3. На kong-ноде: `docker ps`, `docker logs kong --tail 50`.
4. Kong Admin: `curl localhost:8001/upstreams/identity-upstream/health` (с kong-ноды) —
   видно, какие таргеты DOWN.

### 5xx / ошибки в API
1. Grafana → «Логи (Loki)» → фильтр по контейнеру (`handmade-orders`…) — стектрейс.
2. Частая причина: недоступность БД/Redis — см. ниже.

### БД недоступна
1. `yc managed-postgresql cluster list` — статус RUNNING? Алертов в консоли нет?
2. С backend-ноды: `docker exec handmade-identity python -c "import socket;socket.create_connection(('<pg_host>',6432),5);print('ok')"`.
3. Если кластер жив, а коннекта нет — проверить SG/подсети; если мёртв — YC-инцидент
   или ресурсы кластера (диск!). Восстановление: §8.

### Redis недоступен
Сервисы деградируют мягко (кэш выключается, rate-limit в память), но Celery
встаёт. Проверить кластер в YC; после восстановления worker сам переподключится.

### Нода backend умерла
Kong сам выведет её из ротации (health-check /health). Инстанс-группа YC
пересоздаст ВМ; после пересоздания контейнеры поднимутся из cloud-init? — НЕТ:
надо прогнать `deploy-services.yml` (+`observability.yml` для alloy/node-exporter)
и `terraform apply` (обновить hosts.ini, IP сменится).

### Забился диск (алерт NodeHighDisk)
Обычно docker-логи/образы: `docker system prune -af --volumes=false` на ноде;
проверить `/var/log/pg-backup.log` и `/opt/handmade/pg-backups` (локальные дампы
чистятся сами, хранится 3 шт.).

### Очередь задач не разгребается / письма не уходят
1. На первой backend-ноде: `docker logs handmade-worker --tail 100`.
2. DLQ: `docker exec -it <redis…>` — у нас Managed Redis, смотреть из контейнера:
   `docker exec handmade-worker python -c "import redis,os;r=redis.Redis.from_url(os.environ['REDIS_URL']);print(r.llen('celery:dlq'));print(r.lrange('celery:dlq',0,3))"`.
3. Повторить упавшие задачи — вручную после устранения причины (задачи в DLQ
   содержат имя/аргументы).

## 8. Бэкапы и восстановление

- **Managed-бэкапы PG**: 7 дней, окно 01:00. Восстановление: консоль YC →
  кластер → «Восстановить» (создаёт новый кластер из снапшота) → переключить
  `postgres_host` (terraform output меняется сам при импорте, иначе руками в
  hosts.ini) → передеплой сервисов.
- **Offsite-дампы**: `s3://<private-bucket>/pg-backups/pg_*.sql.gz` (ночной cron
  02:30 с первой backend-ноды; лог `/var/log/pg-backup.log`). Восстановление:
  `gunzip -c dump.sql.gz | psql "host=<pg> port=6432 dbname=<db> user=<u> sslmode=require"`.
- **Object Storage** — versioning не включён; удаление объекта необратимо
  (бакеты переживают пересоздание ВМ/кластеров).

## 9. Алерты (Prometheus → Alertmanager)

Правила: [infra/ansible/files/alert-rules.yml](infra/ansible/files/alert-rules.yml)
— ServiceDown/KongDown/NodeDown, High5xxRate (>5%), HighLatencyP95 (>2с),
диск/память/CPU. Куда шлются: **Telegram**, если заданы переменные
`telegram_bot_token` / `telegram_chat_id` (в `[all:vars]` hosts.ini или
`-e` при запуске observability.yml); иначе — только UI Alertmanager.

Подключить Telegram: создать бота у @BotFather → токен; узнать свой chat_id
(написать боту, затем `https://api.telegram.org/bot<токен>/getUpdates`) →
добавить обе переменные → перезапустить `observability.yml`.

## 10. Чек-лист первого боевого запуска

- [ ] Сменить пароль суперадмина (`admin@marketplace.com`) и Grafana admin.
- [ ] Заполнить реквизиты в `/info/*` (оферта, политика, контакты) — сейчас шаблоны.
- [ ] Домен + HTTPS + CDN (см. prod-план, этап 2).
- [ ] Закрыть Grafana :3000 от интернета (VPN/авторизация) после перехода iframe.
- [ ] Telegram-алерты (§9).
- [ ] Боевые ключи YooKassa (сейчас заказы висят в pending) и SMTP sender-домен.
- [ ] Прогнать smoke по живому сайту: регистрация → товар → корзина → заказ.
