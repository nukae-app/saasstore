# Ultra-Local Records — tienda + comunidad

Monorepo: front Next.js (`/web`) + API FastAPI (`/api`) + PostgreSQL, orquestado con Docker Compose y Caddy como reverse proxy con TLS automático. El front solo habla con la API; nada más toca la base de datos.

```
.
├── docker-compose.yml
├── .env.example          # copia a .env y rellena
├── infra/Caddyfile       # /api/* -> FastAPI, resto -> Next.js
├── api/
│   ├── app/
│   │   ├── models.py     # el diseño de datos (releases/items, pedidos, auth sin contraseñas)
│   │   ├── routers/      # catalog, auth, cart, checkout, admin, blog
│   │   └── services/     # reservas atómicas, cliente Discogs, seguridad, email
│   ├── alembic/          # migraciones
│   └── scripts/import_catalog.py   # importación única del CSV del sheet
└── web/                  # Next.js (App Router). Diseño provisional a propósito.
```

## Arrancar en local

```bash
cp .env.example .env        # rellena POSTGRES_PASSWORD y SECRET_KEY como mínimo
docker compose up --build
```

- Web: http://localhost
- API (docs interactivas): http://localhost/api/docs

## Primera migración

Las migraciones se autogeneran a partir de `app/models.py` (Alembic ya está conectado a los modelos):

```bash
docker compose run --rm api alembic revision --autogenerate -m "esquema inicial"
docker compose run --rm api alembic upgrade head
```

A partir de aquí, cada cambio en `models.py` → `revision --autogenerate` → revisar el archivo generado → `upgrade head`. El contenedor de la API ejecuta `alembic upgrade head` en cada arranque.

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

## Crear el primer admin

Tras hacer login una vez (Google o magic link), promociona tu usuario:

```bash
docker compose exec db psql -U ultralocal -c "UPDATE users SET rol='admin' WHERE email='tu@email.com';"
```

## Decisiones de diseño (resumen)

- **`releases` vs `items`**: el álbum y sus copias físicas son cosas distintas. Cada `item` es una copia única (grading, precio propio) y se vende como mucho una vez (`order_items.item_id` es UNIQUE).
- **Reserva atómica**: el checkout reserva con `UPDATE ... WHERE status='disponible'` comprobando filas afectadas. Las reservas caducan a los 20 min y se liberan de forma perezosa.
- **Snapshots**: el pedido copia el precio y la dirección en el momento de la compra; el histórico nunca cambia.
- **Sin contraseñas**: Google (OIDC) + magic link. La sesión es propia: JWT corto + refresh token rotatorio en cookie httpOnly. Solo se guardan hashes de tokens.
- **Guest checkout**: `orders.user_id` es nullable; se compra con email. FK con `SET NULL` para poder anonimizar cuentas (RGPD) conservando pedidos.
- **Pago en Fase 1**: manual (transferencia/Bizum), el pedido nace `pendiente_pago`. Stripe entra en Fase 2 entre `/checkout/start` y `/checkout/confirm`.

## Pendiente (fases siguientes)

- Migración del blog de Blogger (export XML → tabla `posts`).
- Frontend real (diseño, ficha de disco, carrito, checkout, admin UI).
- Stripe + Bizum, tarifas de envío reales, emails transaccionales bonitos.
- i18n ca/es en el front.
- Backups automáticos de Postgres fuera del VPS (`pg_dump` + cron).
