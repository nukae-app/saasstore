# Infra — notes operatives

Referenciat des de `terraform/rds.tf` (migració a `storage_encrypted`) i des d'aquí: capacitat real i pla d'escalat.

## Capacitat validada amb test de càrrega (k6)

Script a `../loadtest/catalog_checkout.js` (veure capçalera del fitxer per l'ús complet). Resultats amb la infra dels commits `ce591ee` (pool SQLAlchemy) i `c692139` (2 processos Uvicorn):

| VUs concurrents (`SCENARIO=browse`, només lectura) | Resultat |
|---|---|
| 30 | Net — p95 257ms, 0% errors |
| 60 | Bé — p95 689ms, 0% errors |
| 100 | Degrada — timeouts parcials, sense caiguda total del servei |

**Important**: aquests números són amb trànsit de **lectura** (catàleg + fitxa de disc). El flux de checkout (reserva d'estoc, escriptures a Postgres) **no s'ha provat sota càrrega** — abans de confiar en aquests números per capacitat real, cal repetir amb `SCENARIO=checkout` (pocs VUs, fora d'hores: reserva estoc real, veure capçalera de l'script).

Configuració actual que sustenta aquests números:
- EC2 `t2.medium` (2 vCPU) — `terraform/ec2.tf`, var `ec2_instance_type`.
- Uvicorn amb `UVICORN_WORKERS=2` (un per vCPU) — `api/Dockerfile`.
- Pool SQLAlchemy `DB_POOL_SIZE=10` / `DB_MAX_OVERFLOW=10` **per procés** — `api/app/config.py`. Amb 2 workers, l'api gasta fins a 2×20=40 connexions en el pitjor cas.
- RDS `db.t4g.micro`, `max_connections≈79` (`SHOW max_connections`).

## Quan el trànsit real s'acosti a aquests límits

**1. Vertical primer (ràpid, barat, sense canvis de codi)**

Pujar la instància EC2 (p. ex. `t3.large` → 2 vCPU/8GB, o `t3.xlarge` → 4 vCPU/16GB):

1. `var.ec2_instance_type` a `terraform/variables.tf` + `terraform apply` (l'EC2 es recrea; és amb IP elàstica, no canvia).
2. Pujar `UVICORN_WORKERS` al `.env` de producció en proporció als vCPU nous (2 vCPU → 2 workers, 4 vCPU → 4 workers).
3. Recalcular el pressupost de connexions: `(UVICORN_WORKERS × (DB_POOL_SIZE+DB_MAX_OVERFLOW)) + marge pel worker/beat` ha d'entrar còmode sota el `max_connections` de RDS. **Si es puja l'EC2 però no la RDS, la base de dades (encara `db.t4g.micro`, límit independent de l'EC2) pot ser el nou coll d'ampolla abans que la CPU.** Si cal, pujar també `var.db_instance_class`.
4. Fer-ho fora d'hores: aturar/arrencar la instància per canviar de tipus és uns 2 min de downtime.
5. **Tornar a validar amb el mateix test de càrrega** (browse + checkout) abans de donar-ho per bo — no assumir el número nou, mesurar-lo igual que aquí.

**2. Horitzontal (només si vertical ja no dona per més, o cal alta disponibilitat real)**

Bloquejants a resoldre abans de poder córrer >1 instància darrere d'un ALB/ASG:

- **Uploads a disc local**: `api/app/routers/admin.py` (`upload_release_image`, `UPLOADS_DIR = "/app/uploads"`) escriu directament al disc de l'EC2 amb `open(filepath, "wb")`; `docker-compose.prod.yml` el comparteix com a volum local entre `api` i `caddy`. Amb 2+ instàncies, una imatge pujada a una no existeix a l'altra. Cal moure-ho a S3 (boto3 ja és dependència del projecte, es fa servir per Secrets Manager a `config.py`) i que `ReleaseImage.url` guardi la URL de S3/CloudFront.
- **Redis local**: cal ElastiCache (gestionat) perquè totes les instàncies vegin el mateix estat de cua de Celery.
- **Celery `beat`**: ha de seguir sent una única instància sempre (mai >1 rèplica) o les tasques programades es dupliquen — cal un lock distribuït si es vol tolerància a fallades del propi `beat`.

Sense aquests tres canvis, muntar un Auto Scaling Group directament trencaria coses (imatges que desapareixen segons a quina instància et toqui, tasques de Celery duplicades).
