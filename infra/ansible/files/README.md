# Ansible files/

Сюда положите **CA-сертификат Yandex Managed PostgreSQL** под именем `root.crt`:

```
infra/ansible/files/root.crt
```

Плейбук `deploy-services.yml` копирует его на узлы в `/opt/handmade/certs/root.crt`
и монтирует в контейнеры (`DB_SSL=true`, `DB_SSL_ROOT_CERT=/app/certs/root.crt`).

Скачать CA можно из консоли Managed PostgreSQL или командой:

```bash
# Единый CA Yandex для всех Managed-баз:
mkdir -p infra/ansible/files
curl -o infra/ansible/files/root.crt \
  https://storage.yandexcloud.net/cloud-certs/CA.pem
```

> Если подключаетесь к БД внутри VPC через пулер :6432 без TLS — выставьте
> `DB_SSL: "false"` в `app_env` плейбука и сертификат не нужен.

`root.crt` намеренно не коммитится (см. `.gitignore`).
