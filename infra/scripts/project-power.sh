#!/usr/bin/env bash
# project-power.sh — включить/выключить весь проект в Yandex Cloud.
#
# Гасит/поднимает ТОЛЬКО платную вычислительную часть и управляемые кластеры,
# чтобы не платить за простой во время паузы между демо:
#   * Managed PostgreSQL  (handmade-postgres)
#   * Managed Redis        (handmade-redis)
#   * Kong instance group  (handmade-kong)
#   * Backend instance group (handmade-backend)
#   * Bastion              (handmade-bastion)
#
# НЕ трогает (дёшево / нужно для стабильности): Object Storage (бакеты), NLB и
# сеть. Поэтому публичный IP сайта (NLB) НЕ меняется. Данные в PG/Redis при
# stop сохраняются (останавливается только compute, диск остаётся).
#
# Запускать на ops-ВМ, где установлен и авторизован yc CLI.
#   ./project-power.sh stop      # выключить проект
#   ./project-power.sh start     # включить проект
#   ./project-power.sh status    # показать текущее состояние
set -uo pipefail

# --- yc CLI (на ops-ВМ лежит в ~/yandex-cloud/bin и часто не в PATH) ---------
YC="${YC_BIN:-$HOME/yandex-cloud/bin/yc}"
[ -x "$YC" ] || YC="$(command -v yc 2>/dev/null || true)"
[ -n "${YC:-}" ] && [ -x "$YC" ] || { echo "ОШИБКА: yc CLI не найден (задай YC_BIN)"; exit 1; }

PROJECT="${PROJECT_NAME:-handmade}"
BASTION="${PROJECT}-bastion"
KONG="${PROJECT}-kong"
BACKEND="${PROJECT}-backend"
PG="${PROJECT}-postgres"
RD="${PROJECT}-redis"

# --- хелперы статуса (status поле из yc get --format json) --------------------
_jstat() { python3 -c 'import sys,json
try: print(json.load(sys.stdin).get("status","?"))
except Exception: print("НЕТ/ОШИБКА")'; }

inst_status() { "$YC" compute instance        get --name "$1" --format json 2>/dev/null | _jstat; }
ig_status()   { "$YC" compute instance-group  get --name "$1" --format json 2>/dev/null | _jstat; }
pg_status()   { "$YC" managed-postgresql cluster get --name "$1" --format json 2>/dev/null | _jstat; }
rd_status()   { "$YC" managed-redis cluster      get --name "$1" --format json 2>/dev/null | _jstat; }

print_status() {
  printf '  %-26s %s\n' "PostgreSQL ($PG)"      "$(pg_status   "$PG")"
  printf '  %-26s %s\n' "Redis ($RD)"           "$(rd_status   "$RD")"
  printf '  %-26s %s\n' "Kong IG ($KONG)"       "$(ig_status   "$KONG")"
  printf '  %-26s %s\n' "Backend IG ($BACKEND)" "$(ig_status   "$BACKEND")"
  printf '  %-26s %s\n' "Bastion ($BASTION)"    "$(inst_status "$BASTION")"
}

bastion_ip() { "$YC" compute instance get --name "$BASTION" --format json 2>/dev/null \
  | python3 -c 'import sys,json
try: print(json.load(sys.stdin)["network_interfaces"][0]["primary_v4_address"]["one_to_one_nat"]["address"])
except Exception: print("?")'; }

case "${1:-status}" in
  stop)
    echo "==> Останавливаю проект (асинхронно)…"
    "$YC" compute instance-group   stop --name "$KONG"    --async >/dev/null 2>&1 || true
    "$YC" compute instance-group   stop --name "$BACKEND" --async >/dev/null 2>&1 || true
    "$YC" compute instance         stop --name "$BASTION" --async >/dev/null 2>&1 || true
    "$YC" managed-postgresql cluster stop --name "$PG"    --async >/dev/null 2>&1 || true
    "$YC" managed-redis cluster      stop --name "$RD"    --async >/dev/null 2>&1 || true
    echo "Команды отправлены. Текущее состояние:"
    print_status
    echo "Полная остановка занимает несколько минут. Проверка: $0 status"
    ;;
  start)
    echo "==> Поднимаю проект (асинхронно)…"
    # Сначала хранилища данных, потом приложение (контейнеры --restart always
    # сами переподключатся к БД, так что строгий порядок не обязателен).
    "$YC" managed-postgresql cluster start --name "$PG"    --async >/dev/null 2>&1 || true
    "$YC" managed-redis cluster      start --name "$RD"    --async >/dev/null 2>&1 || true
    "$YC" compute instance-group   start --name "$BACKEND" --async >/dev/null 2>&1 || true
    "$YC" compute instance-group   start --name "$KONG"    --async >/dev/null 2>&1 || true
    "$YC" compute instance         start --name "$BASTION" --async >/dev/null 2>&1 || true
    echo "Команды отправлены. Текущее состояние:"
    print_status
    echo
    echo "Поднятие занимает несколько минут (кластеры дольше всех). Контейнеры стартуют сами."
    echo "Сайт остаётся на прежнем IP NLB."
    echo "ВНИМАНИЕ: публичный IP бастиона МЕНЯЕТСЯ при рестарте (сейчас: $(bastion_ip))."
    echo "Если нужен Ansible/Grafana — обнови инвентарь: (cd infra/terraform && terraform apply),"
    echo "и при необходимости поправь настройку grafana_dashboard_url в админке."
    ;;
  status)
    echo "Состояние проекта:"
    print_status
    ;;
  *)
    echo "Использование: $0 {stop|start|status}"; exit 1;;
esac
