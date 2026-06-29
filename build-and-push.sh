#!/bin/bash
set -e  # остановить при первой ошибке

yc container registry configure-docker
REG=cr.yandex/crp8b0ggroptcd9dso2t

for s in identity catalog orders sellers platform worker; do
  echo "Building and pushing $s..."
  docker build -f services/$s/Dockerfile -t $REG/handmade-$s:latest .
  docker push $REG/handmade-$s:latest
  echo "Done $s"
done

# Frontend is an independent image (own context, own lifecycle). Built with NO
# VITE_API_URL so the SPA calls the API at the relative /api/v1 (same origin as
# the edge that serves it) — no backend hostname baked in.
echo "Building and pushing frontend..."
docker build -f frontend/Dockerfile -t $REG/handmade-frontend:latest frontend
docker push $REG/handmade-frontend:latest
echo "Done frontend"

echo "All images built and pushed!"