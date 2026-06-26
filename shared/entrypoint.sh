#!/usr/bin/env sh
# Container command dispatcher.
#
# The Yandex Cloud deploy (Ansible) runs the same backend image with different
# commands: `migrate` as a one-shot job, the web server in the backend instance
# group, and `worker` for the Celery container. `beat`/`seed` are provided for
# completeness. Any other argument is exec'd verbatim so the image stays generic.
set -e

cmd="${1:-web}"
shift || true

case "$cmd" in
  migrate)
    exec alembic upgrade head
    ;;
  web)
    # Each service image ships its own service_main.py (from services/<svc>/main.py).
    # APP_MODULE overrides the ASGI target if needed.
    exec uvicorn "${APP_MODULE:-service_main:app}" --host 0.0.0.0 --port 8000 "$@"
    ;;
  worker)
    exec celery -A app.tasks.celery_app worker --loglevel=info "$@"
    ;;
  beat)
    exec celery -A app.tasks.celery_app beat --loglevel=info "$@"
    ;;
  seed)
    exec python scripts/seed.py "$@"
    ;;
  *)
    exec "$cmd" "$@"
    ;;
esac
