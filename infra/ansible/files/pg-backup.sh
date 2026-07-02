#!/usr/bin/env bash
# Nightly logical PostgreSQL dump, shipped OFFSITE to the private S3 bucket.
#
# Managed PG already keeps 7 days of snapshots, but those die with the cluster;
# this dump survives cluster deletion and allows point-in-time restores by hand.
# Installed by deploy-services.yml as /opt/handmade/pg-backup.sh + a daily cron
# on the first backend node. Config comes from /opt/handmade/pg-backup.env.
set -euo pipefail

ENV_FILE=/opt/handmade/pg-backup.env
# shellcheck disable=SC1090
source "$ENV_FILE"

STAMP=$(date +%Y-%m-%d_%H%M)
FILE="pg_${DB_NAME}_${STAMP}.sql.gz"
WORKDIR=/opt/handmade/pg-backups
mkdir -p "$WORKDIR"

# 1) Dump via the official postgres client image (server is Managed PG 17).
docker run --rm \
  -e PGPASSWORD="$DB_PASSWORD" \
  postgres:17-alpine \
  pg_dump -h "$DB_HOST" -p "${DB_PORT:-6432}" -U "$DB_USER" -d "$DB_NAME" \
  --no-owner --no-privileges \
  | gzip > "$WORKDIR/$FILE"

# 2) Ship to the PRIVATE bucket (offsite relative to the DB cluster).
docker run --rm \
  -e AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY" \
  -e AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY" \
  -v "$WORKDIR:/data:ro" \
  amazon/aws-cli \
  s3 cp "/data/$FILE" "s3://$S3_PRIVATE_BUCKET/pg-backups/$FILE" \
  --endpoint-url "$S3_ENDPOINT"

# 3) Keep only the last 3 local dumps (S3 keeps the history).
ls -1t "$WORKDIR"/pg_*.sql.gz 2>/dev/null | tail -n +4 | xargs -r rm -f

echo "OK: $FILE uploaded to s3://$S3_PRIVATE_BUCKET/pg-backups/"
