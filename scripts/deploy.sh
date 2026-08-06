#!/usr/bin/env bash
# Construeix les imatges api/web en local (Mac), les puja a ECR i les
# desplega a l'EC2 amb `docker compose pull` + `up -d` (sense build al servidor).
#
# Ús: scripts/deploy.sh
set -euo pipefail

AWS_REGION="eu-west-1"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
IMAGE_TAG="$(git rev-parse --short HEAD)"
SSH_HOST="ubuntu@54.76.9.1"
REMOTE_DIR="/home/ubuntu/recordshop"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Login a ECR ($ECR_REGISTRY)"
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

echo "==> Build + push api (tag: $IMAGE_TAG)"
docker buildx build --platform linux/amd64 \
  -t "$ECR_REGISTRY/recordshop-api:$IMAGE_TAG" \
  -t "$ECR_REGISTRY/recordshop-api:latest" \
  --push ./api

echo "==> Build + push web (tag: $IMAGE_TAG)"
docker buildx build --platform linux/amd64 \
  -t "$ECR_REGISTRY/recordshop-web:$IMAGE_TAG" \
  -t "$ECR_REGISTRY/recordshop-web:latest" \
  --push ./web

echo "==> Desplegant a $SSH_HOST"
ssh "$SSH_HOST" "cd $REMOTE_DIR && git pull --ff-only"
scp docker-compose.prod.yml "$SSH_HOST:$REMOTE_DIR/docker-compose.prod.yml"

# shellcheck disable=SC2087
ssh "$SSH_HOST" ECR_REGISTRY="$ECR_REGISTRY" IMAGE_TAG="$IMAGE_TAG" AWS_REGION="$AWS_REGION" bash -s <<'REMOTE'
  set -euo pipefail
  cd /home/ubuntu/recordshop
  aws ecr get-login-password --region "$AWS_REGION" \
    | docker login --username AWS --password-stdin "$ECR_REGISTRY"

  # Materialitza .env.grafana des de Secrets Manager (clau GRAFANA dins de
  # recordshop/prod): Alloy no és Python, no sap llegir Secrets Manager pel
  # seu compte com fa _load_secrets_from_aws() per a api/worker/beat, així
  # que necessita un fitxer real. Es regenera a cada desplegament, mai es
  # guarda en pla al repo (.env.grafana és a .gitignore).
  aws secretsmanager get-secret-value --secret-id recordshop/prod --region "$AWS_REGION" \
    --query SecretString --output text \
    | python3 -c "import json,sys; print('GRAFANA_API_KEY=' + json.load(sys.stdin)['GRAFANA'])" > .env.grafana

  docker compose -f docker-compose.prod.yml pull
  docker compose -f docker-compose.prod.yml up -d
  # El Caddyfile i el config d'Alloy són bind-mounts d'un sol fitxer: quan
  # `git pull` els reemplaça (nou inode), el contenidor es queda apuntant a
  # l'inode antic fins que es reinicia — `up -d` NOMÉS recrea un servei si
  # canvia la seva definició al compose (imatge/env/etc.), no si només
  # canvia un fitxer muntat. Sense aquest restart explícit, un canvi al
  # Caddyfile o a l'alloy-config es desplegaria "amb èxit" i no s'aplicaria
  # mai fins al proper cop que canviï la imatge d'aquell servei.
  docker compose -f docker-compose.prod.yml restart caddy alloy
  # -a (no només dangling): cada desplegament deixa una imatge api+web amb
  # tag únic (el SHA de git) que mai es reclama sola i s'acumula fins
  # omplir el disc de 19GB de l'EC2 (ja ha passat un cop).
  docker image prune -af
  docker builder prune -af
REMOTE

echo "==> Fet. Desplegat $IMAGE_TAG a producció."
