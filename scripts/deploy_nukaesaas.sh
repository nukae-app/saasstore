#!/usr/bin/env bash
# Construeix les imatges api/web en local (arm64, per a Graviton), les puja
# a ECR i les desplega a l'EC2 de "nukaesaas" amb `docker compose pull` +
# `up -d` (sense build al servidor). Copia de scripts/deploy.sh — NO toca
# res de recordshop (host, repos ECR i directori remot són tots diferents).
#
# Requereix una entrada `Host nukaesaas` a ~/.ssh/config (mateix patró SSM
# ProxyCommand que ja hi ha per a 54.76.9.1, amb l'instance-id de
# `terraform output instance_id` a infra/terraform-nukaesaas/).
#
# Ús: scripts/deploy_nukaesaas.sh
set -euo pipefail

AWS_REGION="eu-west-1"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_TAG="$(git rev-parse --short HEAD)"
SSH_HOST="nukaesaas"
REMOTE_DIR="/home/ubuntu/nukaesaas"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Subidas del admin en S3 + CloudFront (infra/terraform-uploads). Se leen ANTES de
# construir nada: si el stack no está aplicado, el deploy se corta aquí y no toca el servidor.
UPLOADS_BUCKET="nukaesaas-uploads-${AWS_ACCOUNT_ID}"
UPLOADS_CDN_HOST="$(terraform -chdir=infra/terraform-uploads output -raw cdn_domain)"
[ -n "$UPLOADS_CDN_HOST" ] || { echo "ERROR: terraform-uploads no está aplicado (sin cdn_domain)"; exit 1; }

echo "==> Login a ECR ($ECR_REGISTRY)"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "==> Build + push api arm64 (tag: $IMAGE_TAG)"
docker buildx build --platform linux/arm64 \
  -t "$ECR_REGISTRY/nukaesaas-api:$IMAGE_TAG" \
  -t "$ECR_REGISTRY/nukaesaas-api:latest" \
  --push ./api

echo "==> Build + push web arm64 (tag: $IMAGE_TAG)"
docker buildx build --platform linux/arm64 \
  -t "$ECR_REGISTRY/nukaesaas-web:$IMAGE_TAG" \
  -t "$ECR_REGISTRY/nukaesaas-web:latest" \
  --push ./web

echo "==> Desplegant a $SSH_HOST"
ssh "$SSH_HOST" "mkdir -p $REMOTE_DIR"
scp docker-compose.nukaesaas.yml "$SSH_HOST:$REMOTE_DIR/docker-compose.nukaesaas.yml"
scp infra/Caddyfile "$SSH_HOST:$REMOTE_DIR/Caddyfile"
scp infra/alloy-config.alloy "$SSH_HOST:$REMOTE_DIR/alloy-config.alloy"

# Token de Grafana Cloud (stack punycrane5): viu a Secrets Manager
# (recordshop/prod, clau GRAFANA), que el rol de l'EC2 de nukaesaas NO pot
# llegir — es llegeix des d'aquí (credencials locals d'AWS) i s'escriu al
# servidor com a .env.grafana (mode 600), passant per stdin (mai per
# arguments de línia de comandes) i sense quedar al repo.
echo "==> Escrivint .env.grafana al servidor"
aws secretsmanager get-secret-value --secret-id recordshop/prod --region "$AWS_REGION" \
  --query SecretString --output text \
  | python3 -c "import json,sys; print('GRAFANA_API_KEY=' + json.load(sys.stdin)['GRAFANA'])" \
  | ssh "$SSH_HOST" "umask 077 && cat > $REMOTE_DIR/.env.grafana"

# URL pública del collector de Faro (RUM del navegador, app labotigaaquesta
# a Grafana Cloud): no és un secret (va al JS que baixa el visitant). El web
# la llegeix en runtime (layout.jsx), així que n'hi ha prou amb tenir-la al
# .env del servidor, que docker compose fa servir per interpolar el compose.
FARO_COLLECTOR_URL="https://faro-collector-prod-eu-west-6.grafana.net/collect/237acf4206e1fc52519d44711fee374d"

# shellcheck disable=SC2087
ssh "$SSH_HOST" ECR_REGISTRY="$ECR_REGISTRY" IMAGE_TAG="$IMAGE_TAG" AWS_REGION="$AWS_REGION" FARO_COLLECTOR_URL="$FARO_COLLECTOR_URL" UPLOADS_BUCKET="$UPLOADS_BUCKET" UPLOADS_CDN_HOST="$UPLOADS_CDN_HOST" bash -s <<'REMOTE'
  set -euo pipefail
  cd /home/ubuntu/nukaesaas
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"

  # Idempotent: afegeix o actualitza la línia al .env sense tocar la resta.
  if grep -q '^NEXT_PUBLIC_FARO_COLLECTOR_URL=' .env; then
    sed -i "s|^NEXT_PUBLIC_FARO_COLLECTOR_URL=.*|NEXT_PUBLIC_FARO_COLLECTOR_URL=$FARO_COLLECTOR_URL|" .env
  else
    echo "NEXT_PUBLIC_FARO_COLLECTOR_URL=$FARO_COLLECTOR_URL" >> .env
  fi

  # Subidas del admin → S3 (idempotente, mismo patrón que arriba).
  setenv() {
    if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
  }
  setenv UPLOADS_BACKEND s3
  setenv S3_UPLOADS_BUCKET "$UPLOADS_BUCKET"
  setenv UPLOADS_CDN_HOST "$UPLOADS_CDN_HOST"

  docker compose -f docker-compose.nukaesaas.yml pull
  docker compose -f docker-compose.nukaesaas.yml up -d
  # Caddyfile i alloy-config són bind-mounts d'un sol fitxer: scp els
  # reemplaça (nou inode) i el contenidor es queda amb l'antic fins que es
  # reinicia; `up -d` no els recrea si només canvia el fitxer.
  docker compose -f docker-compose.nukaesaas.yml restart caddy alloy
  docker image prune -af
  docker builder prune -af
REMOTE

echo "==> Fet. Desplegat $IMAGE_TAG a nukaesaas."
