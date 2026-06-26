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

echo "All services built and pushed!"