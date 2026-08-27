# NukaeStore — plataforma SaaS multi-tenant (nace de Ultra-Local Records)

Empezó como la tienda + comunidad de un solo negocio real (`recordstore`,
Ultra-Local Records: discos nuevos y de segunda mano en Poblenou, Barcelona).
Ha evolucionado a una plataforma multi-tenant que aloja varias tiendas
("tenants"), cada una con su propio dominio, catálogo, admin y datos
aislados — hoy con dos "verticals" soportados (discos y floristería) y
espacio para más.

Monorepo: front Next.js (`/web`) + API FastAPI (`/api`) + PostgreSQL,
orquestado con Docker Compose y Caddy como reverse proxy con TLS automático
(incluye TLS on-demand para dominios de tenant dados de alta en caliente). El
front solo habla con la API; nada más toca la base de datos.

Arquitectura multi-tenant y plan de fases: ver `docs/ARQUITECTURA_CORE_VERTICAL.md`.
Notas operativas de producción (capacidad, escalado): ver `infra/README.md`.

```
.
├── docker-compose.yml
├── docker-compose.prod.yml   # imágenes ECR, secretos vía AWS Secrets Manager
├── .env.example               # copia a .env y rellena
├── infra/
│   ├── Caddyfile               # producción: sitio + superadmin + tenants (TLS on-demand)
│   └── terraform/              # EC2 + RDS + ECR + IAM + Secrets Manager (AWS)
├── api/
│   ├── app/
│   │   ├── models/          # diseño de datos por dominio (catalog, orders, platform...)
│   │   ├── schemas/         # Pydantic in/out, mismo criterio de paquetes
│   │   ├── routers/         # catalog, auth, cart, checkout, blog, superadmin,
│   │   │                    # admin/, erp/, me/, comptabilitat/ (paquetes por dominio)
│   │   ├── services/        # reservas atómicas, Discogs, Redsys, seguridad, email...
│   │   ├── tenancy.py        # resolución de tenant por dominio + aislamiento server-side
│   │   └── tenant_secrets.py # secretos por tenant en AWS Secrets Manager
│   ├── alembic/              # migraciones
│   └── scripts/               # import_catalog, create_superadmin, backfills...
└── web/
    ├── app/[locale]/         # tienda pública (i18n)
    ├── app/admin/             # admin de cada tenant
    ├── app/superadmin/        # panel de plataforma (gestión de tenants)
    └── app/nukaestore/        # landing del producto SaaS
```

## Arrancar en local

```bash
cp .env.example .env        # rellena POSTGRES_PASSWORD y SECRET_KEY como mínimo
docker compose up --build
```

- Web: http://localhost:8080
- API (docs interactivas): http://localhost:8080/api/docs

El contenedor de la API ejecuta `alembic upgrade head` en cada arranque —
no hace falta ningún paso manual de migración para tener el esquema al día.
Al añadir un cambio nuevo en `app/models/`: `alembic revision --autogenerate
-m "..."`, revisar el archivo generado, `alembic upgrade head`.

## Importar el catálogo del Google Sheet

1. En el sheet: Archivo → Descargar → CSV (la pestaña del catálogo).
2. ```bash
   docker compose cp catalogo.csv api:/srv/catalogo.csv
   docker compose exec api python -m scripts.import_catalog catalogo.csv --limit 50   # prueba
   docker compose exec api python -m scripts.import_catalog catalogo.csv --enrich    # completo
   ```

`--enrich` consulta Discogs por cada CODI (≈1 disco/segundo por el rate limit) y trae carátula y release id. Es idempotente: se puede relanzar sin duplicar.

## Configurar Google login

1. https://console.cloud.google.com → APIs y servicios → Credenciales → ID de cliente OAuth (aplicación web).
2. URI de redirección autorizada: `http://localhost/api/auth/google/callback` (y la de producción).
3. Copia client id y secret al `.env`.

El magic link funciona sin configurar nada: en dev, el enlace se imprime en los logs de la API (`docker compose logs -f api`).

## Crear el primer admin de un tenant

Tras hacer login una vez (Google o magic link), promociona tu usuario:

```bash
docker compose exec db psql -U ultralocal -c "UPDATE users SET rol='admin' WHERE email='tu@email.com';"
```

## Crear el primer superadmin de plataforma

Arranque en frío del panel de superadmin (gestión de tenants, no de un tenant concreto):

```bash
docker compose exec api python -m scripts.create_superadmin --email tu@email.com
```

## Decisiones de diseño (resumen)

- **`releases` vs `items`**: el álbum y sus copias físicas son cosas distintas. Para segunda mano, cada `item` es una copia única (grading, precio propio) y se vende como mucho una vez; para nuevo, un `item` agrega stock (`cantidad`/`cantidad_reservada`).
- **Reserva atómica**: el checkout reserva con `UPDATE ... WHERE` condicionado comprobando filas afectadas (nunca `SELECT` + `UPDATE`). Las reservas caducan y se liberan de forma perezosa.
- **Snapshots**: el pedido copia el precio y la dirección en el momento de la compra; el histórico nunca cambia.
- **Sin contraseñas**: Google (OIDC) + magic link. La sesión es propia: JWT corto + refresh token rotatorio en cookie httpOnly. Solo se guardan hashes de tokens.
- **Guest checkout**: `orders.user_id` es nullable; se compra con email. FK con `SET NULL` para poder anonimizar cuentas (RGPD) conservando pedidos.
- **Pago**: Redsys (TPV virtual / Bizum) ya integrado entre `/checkout/start` y `/checkout/confirm`.
- **Multi-tenant**: cada fila de las tablas core lleva `tenant_id`; el aislamiento se aplica en dos capas — filtro de aplicación (`app/tenancy.py`) y Row-Level Security en Postgres como cinturón de seguridad extra. Los secretos específicos de cada tenant (Redsys, Discogs, Spotify) viven en AWS Secrets Manager, no en variables de entorno compartidas.

## Despliegue

Producción corre en AWS (EC2 + RDS + ECR + Secrets Manager), gestionado con
Terraform (`infra/terraform/`) y desplegado con `scripts/deploy.sh` (build +
push a ECR + `docker compose pull/up` remoto sobre `docker-compose.prod.yml`).
Detalle de capacidad y escalado en `infra/README.md`.

## Pendiente (por prioridad, ver `docs/ARQUITECTURA_CORE_VERTICAL.md` §14)

- Rename de atributos Python/Pydantic/frontend a inglés (Fase 4 Etapa B) — la BD ya está renombrada, el contrato JSON público todavía no.
- Migración del blog de Blogger (export XML → tabla `posts`).
- Frontend real de la tienda pública por vertical más allá del núcleo ya construido.
- Backups automáticos de Postgres fuera del VPS más allá del retention de RDS.
