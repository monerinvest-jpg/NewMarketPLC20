# Build context = repository root:  docker build -f services/sellers/Dockerfile .
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

COPY services/sellers/main.py ./service_main.py

RUN mkdir -p /app/uploads/products && chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
