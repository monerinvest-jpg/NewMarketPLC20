# infra/ — инфраструктура Yandex Cloud (Terraform + Ansible)

Самодостаточная инфраструктура для развёртывания маркетплейса в Yandex Cloud.
Воссоздана из инфра-репозитория `skboyinboxru/Hand-Made` и интегрирована в этот
проект (пути перенастроены под локальную раскладку). Полная пошаговая инструкция —
в [../DEPLOY.md](../DEPLOY.md).

## Структура

```
infra/
├── terraform/                 # Создание ресурсов YC
│   ├── providers.tf           #   провайдер yandex (ключ key.json), random, local
│   ├── variables.tf           #   все переменные (обязательные: cloud_id/folder_id/service_account_id)
│   ├── network.tf             #   VPC, подсети (a/b), NAT, security-группы kong/backend
│   ├── database.tf            #   Managed PostgreSQL 17 (app + kong БД/юзеры) + Redis/Valkey
│   ├── compute.tf             #   бастион, instance-группы kong и backend, cloud-init
│   ├── loadbalancer.tf        #   внешний NLB :80 → Kong :8000
│   ├── target_group.tf        #   target-группа Kong
│   ├── storage.tf             #   Object Storage: приватный бакет + статический S3-ключ
│   ├── mail.tf                #   Postbox: сервис-аккаунт-отправитель (SMTP-ключ)
│   ├── outputs.tf             #   выводы + ГЕНЕРАЦИЯ hosts.ini (с S3_*/SMTP_* в [all:vars])
│   ├── cloud-init.tpl         #   bootstrap узлов (docker, ssh-ключ)
│   ├── ansible.cfg            #   inventory=./hosts.ini (Ansible запускается ОТСЮДА)
│   └── terraform.tfvars.example
│
└── ansible/
    ├── deploy-services.yml    # Backend: образы → migrate → 5 сервисов → worker/beat → Kong
    ├── deploy-frontend.yml    # Frontend: контейнер handmade-frontend + Kong catch-all '/'
    ├── observability.yml      # Опц.: Prometheus + Grafana + node_exporter
    ├── group_vars/all/
    │   └── vault.yml.example  #   шаблон секретов (реальный — ansible-vault, опционально)
    └── files/
        └── README.md          #   сюда положить root.crt (CA Managed PostgreSQL)
```

## Развёртывание

Все 5 сервисов и worker/beat — контейнерами на общей backend-группе (порты 8001–8005),
Kong — один маршрут на префикс пути. Фронтенд — отдельным образом/плейбуком
(`deploy-frontend.yml`) за тем же Kong. Полная пошаговая инструкция — в
[../DEPLOY.md](../DEPLOY.md).

## Что отличается от исходного инфра-репозитория

- `ansible/deploy-services.yml` **заменяет** монолитный `deploy-backend.yml`
  (тот деплоил один образ `handmade-backend` на порт 3000 — он больше не собирается).
- В `network.tf` security-группа `backend` открывает порты **8001–8005** (под
  микросервисы) вместо прежнего одиночного 3000.
- Папка `Ansible/` переименована в `ansible/` (нижний регистр) — учтено в путях запуска.

## Быстрый порядок (детали — в DEPLOY.md)

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # заполнить cloud_id/folder_id/service_account_id
cp ~/key.json ./key.json                       # ключ сервис-аккаунта
terraform init && terraform apply              # создаёт ресурсы + hosts.ini

# собрать и запушить 6 образов (из корня репозитория) — см. DEPLOY.md §3

cp ~/pg_ca.crt ../ansible/files/root.crt       # CA Managed PostgreSQL
ansible -m ping all                            # из infra/terraform (ansible.cfg здесь)
ansible-playbook ../ansible/deploy-services.yml
curl http://$(terraform output -raw load_balancer_ip)/health
```
