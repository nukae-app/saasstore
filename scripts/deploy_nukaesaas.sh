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

# shellcheck disable=SC2087
ssh "$SSH_HOST" ECR_REGISTRY="$ECR_REGISTRY" IMAGE_TAG="$IMAGE_TAG" AWS_REGION="$AWS_REGION" bash -s <<'REMOTE'
  set -euo pipefail
  cd /home/ubuntu/nukaesaas
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"

  docker compose -f docker-compose.nukaesaas.yml pull
  docker compose -f docker-compose.nukaesaas.yml up -d
  docker compose -f docker-compose.nukaesaas.yml restart caddy
  docker image prune -af
  docker builder prune -af
REMOTE

echo "==> Fet. Desplegat $IMAGE_TAG a nukaesaas."
