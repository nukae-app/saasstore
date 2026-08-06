#!/usr/bin/env bash
# Sincronitza la BD amb l'inventari real de Discogs (scripts.sync_discogs_inventory
# dins del contenidor api), injectant el token de producció NOMÉS per a
# aquesta execució puntual — mai al .env compartit amb api/worker/beat.
#
# El token viu al secret recordshop/prod de AWS Secrets Manager (el mateix
# que ja fa servir l'app), sota la clau DISCOGS_TOKEN_SCRIPT (no DISCOGS_TOKEN):
# _load_secrets_from_aws() (app/config.py) carrega totes les claus del secret
# com a variables d'entorn a api/worker/beat, però com que Settings no té cap
# camp `discogs_token_script`, aquesta clau hi queda inert. Mentre encara
# estem de proves, això evita que push_item_to_discogs / remove_item_from_discogs
# (que es disparen amb qualsevol alta/baixa des de l'admin) toquin el
# Marketplace real. Quan es vulgui activar Discogs de veritat per a l'app,
# cal afegir/canviar la clau DISCOGS_TOKEN (sense _SCRIPT) al secret.
#
# Pensat per cridar-se per cron de l'host (no des de dins de Docker); l'EC2
# ja té permís secretsmanager:GetSecretValue sobre aquest secret (rol IAM,
# veure infra/terraform/iam.tf):
#   0 5 * * * /home/ubuntu/recordshop/scripts/run_discogs_sync.sh >> /home/ubuntu/recordshop/logs/discogs_sync.log 2>&1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SECRET_ID="${DISCOGS_SECRET_ID:-recordshop/prod}"
AWS_REGION="${AWS_REGION:-eu-west-1}"

DISCOGS_TOKEN="$(
  aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ID" --region "$AWS_REGION" \
    --query SecretString --output text \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('DISCOGS_TOKEN_SCRIPT',''))"
)"

if [ -z "$DISCOGS_TOKEN" ]; then
  echo "No s'ha trobat la clau DISCOGS_TOKEN_SCRIPT dins del secret $SECRET_ID" >&2
  exit 1
fi

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

docker compose -f "$COMPOSE_FILE" exec -T -e DISCOGS_TOKEN="$DISCOGS_TOKEN" api \
  python -m scripts.sync_discogs_inventory
