#!/usr/bin/env bash
# Lectura puntual de solo lectura: lista los tenants reales en producción
# (recordshop y nukaesaas) para poder distinguirlos de los secretos
# huérfanos en AWS Secrets Manager (saaswebstore/tenants/<uuid>) creados
# por el bug de aislamiento de tests corregido en api/tests/conftest.py.
# NO escribe nada, no modifica stock ni pedidos: un único SELECT contra la
# tabla tenants vía el contenedor `api` ya desplegado.
set -euo pipefail

echo "== recordshop (ubuntu@54.76.9.1) =="
echo "SALTADO: la instancia EC2 (i-0083f88d5909ec93c) está parada (Client.UserInitiatedShutdown, 2026-08-28 22:33:46 GMT)."

echo "== nukaesaas (ssh alias 'nukaesaas') =="
ssh nukaesaas \
  "cd /home/ubuntu/nukaesaas && docker compose -f docker-compose.nukaesaas.yml exec -T api python -c \"from app.database import SessionLocal; from app.models import Tenant; db = SessionLocal(); [print(t.id, t.slug) for t in db.query(Tenant).all()]\""
