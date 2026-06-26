# infra/ — инфраструктура Yandex Cloud (Terraform + Ansible)

Самодостаточная инфраструктура для развёртывания маркетплейса в Yandex Cloud.
Воссоздана из инфра-репозитория `skboyinboxru/Hand-Made` и интегрирована в этот
проект (пути перенастроены под локальную раскладку). Полная пошаговая инструкция —
в [../DEPLOY.md](../DEPLOY.md).

## Структура

```
infra/
├── terraform/                 # Создание ресурсов YC (Вариант A, рабочий по умолчанию)
│   ├── providers.tf           #   провайдер yandex (ключ key.json), random, local
│   ├── variables.tf           #   все переменные (обязательные: cloud_id/folder_id/service_account_id)
│   ├── network.tf             #   VPC, подсети (a/b), NAT, security-группы kong/backend
│   ├── database.tf            #   Managed PostgreSQL 17 (app + kong БД/юзеры) + Redis/Valkey
│   ├── compute.tf             #   бастион, instance-группы kong и backend, cloud-init
│   ├── loadbalancer.tf        #   внешний NLB :80 → Kong :8000
│   ├── target_group.tf        #   target-группа Kong
│   ├── outputs.tf             #   выводы + ГЕНЕРАЦИЯ hosts.ini (Ansible-инвентарь)
│   ├── cloud-init.tpl         #   bootstrap узлов (docker, ssh-ключ)
│   ├── ansible.cfg            #   inventory=./hosts.ini (Ansible запускается ОТСЮДА)
│   ├── terraform.tfvars.example
│   └── variant-b/             # ОПЦИЯ: по группе на сервис (для масштабирования)
│
└── ansible/
    ├── deploy-services.yml    # Выкат: образы → migrate → 5 сервисов → worker/beat → Kong
    ├── group_vars/all/
    │   └── vault.yml.example  #   шаблон секретов (реальный — ansible-vault, опционально)
    └── files/
        └── README.md          #   сюда положить root.crt (CA Managed PostgreSQL)
```

## Два варианта развёртывания

- **Вариант A (по умолчанию):** базовый `terraform/` + `ansible/deploy-services.yml`.
  Все 5 сервисов и worker/beat — контейнерами на существующей backend-группе
  (порты 8001–8005). Kong — один маршрут на префикс пути. Ничего дополнительного
  применять не нужно.
- **Вариант B (масштабирование):** см. `terraform/variant-b/README.md` — отдельная
  instance-группа на каждый сервис.

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
