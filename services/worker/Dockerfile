# Celery worker / beat image (shared library, no HTTP entrypoint).
# Build context = repository root:  docker build -f services/worker/Dockerfile .
# Run as:  worker  (Celery worker)  or  beat  (scheduler).
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY shared/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/app ./app
COPY shared/alembic ./alembic
COPY shared/alembic.ini ./alembic.ini
COPY shared/scripts ./scripts
COPY shared/entrypoint.sh ./entrypoint.sh

RUN mkdir -p /app/uploads/products && chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["worker"]
