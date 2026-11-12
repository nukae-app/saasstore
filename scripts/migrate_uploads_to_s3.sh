#!/usr/bin/env bash
# Copia el volumen `uploads` de nukaesaas al bucket S3, separando lo público de lo privado:
#   <volumen>/*             -> s3://<bucket>/public/        (sin despeses/)
#   <volumen>/despeses/*    -> s3://<bucket>/private/despeses/
# Idempotente (sync): se puede repetir justo antes de activar UPLOADS_BACKEND=s3 para copiar
# lo subido entre medias. NO borra nada del volumen ni del bucket.
#
# Uso:   scripts/migrate_uploads_to_s3.sh dry   # solo muestra qué copiaría
#        scripts/migrate_uploads_to_s3.sh run   # copia de verdad
# Requiere haber aplicado infra/terraform-uploads (bucket + permiso del rol de la EC2).
set -euo pipefail

MODE="${1:-dry}"
case "$MODE" in dry|run) ;; *) echo "Uso: $0 dry|run"; exit 2 ;; esac

AWS_REGION="eu-west-1"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="nukaesaas-uploads-${AWS_ACCOUNT_ID}"
SSH_HOST="nukaesaas"
DRY=""; [ "$MODE" = "dry" ] && DRY="--dryrun"

# shellcheck disable=SC2087
ssh "$SSH_HOST" BUCKET="$BUCKET" DRY="$DRY" AWS_REGION="$AWS_REGION" bash -s <<'REMOTE'
  set -euo pipefail
  SRC="$(docker volume inspect nukaesaas_uploads --format '{{.Mountpoint}}')"
  echo "==> Origen: $SRC  ->  s3://$BUCKET"
  sudo du -sh "$SRC"; sudo find "$SRC" -type f | wc -l | xargs echo "ficheros:"

  echo "==> Público (public/), sin despeses/"
  sudo aws s3 sync "$SRC" "s3://$BUCKET/public/" --region "$AWS_REGION" \
    --exclude 'despeses/*' --cache-control 'public, max-age=31536000, immutable' --no-progress $DRY

  if sudo test -d "$SRC/despeses"; then
    echo "==> Privado (private/despeses/)"
    sudo aws s3 sync "$SRC/despeses" "s3://$BUCKET/private/despeses/" --region "$AWS_REGION" \
      --cache-control 'private, no-store' --no-progress $DRY
  fi
REMOTE
echo "==> Hecho ($MODE)."
