# Ultra-Local Records — contexto del proyecto

Tienda de discos online + comunidad (blog y agenda) para una tienda real de Poblenou (Barcelona), con vocación de crecer hacia un ERP ligero de gestión de almacén. Este documento es el contexto para seguir desarrollando; léelo entero antes de tocar código.

## Qué es esto y para quién

Negocio físico que vende vinilos (nuevos y de segunda mano) en tienda, en Discogs y quiere venderlos también por web. La web debe ser mitad tienda, mitad comunidad (conserva el espíritu del blog actual en Blogger). El catálogo inicial vive en un Google Sheet que es, en realidad, un export de Discogs.

Idiomas: catalán (principal) y castellano. Público local. Operan dos personas, no hace falta sobre-ingeniería.

## Stack y arquitectura

- Front: Next.js (App Router, React, SSR por SEO) en `/web`. Solo habla con la API.
- Back: FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 en `/api`. Es el único que toca la base de datos.
- BD: PostgreSQL.
- Infra: Docker Compose con cuatro servicios (Caddy como reverse proxy con TLS automático, web, api, db). Caddy enruta `/api/*` a FastAPI y el resto a Next.js.
- Despliegue previsto: un VPS pequeño (10-20€/mes).

Arranque local: `cp .env.example .env` (rellenar `POSTGRES_PASSWORD` y `SECRET_KEY`), `docker compose up --build`. API docs en `http://localhost/api/docs`.

Tests: `cd api && python -m pytest` (usan SQLite en memoria, no necesitan Postgres). Mantenerlos verdes.

## Decisiones de diseño que NO hay que romper

Estas decisiones están tomadas a conciencia; si algo parece que las contradice, es probable que sea un error:

1. **`releases` vs `items`.** Un `release` es el álbum (metadatos: artista, título, sello, carátula...). Un `item` es una línea de stock, con su propio precio — pero su granularidad depende de `condicion`:
   - **`segona_ma`**: cada `item` es una copia física única con su propio grading (`estado_disco`/`estado_funda`), `cantidad` siempre 1. Una tienda de segunda mano vende ejemplares únicos, no "producto × cantidad" — esto NUNCA cambia para segona_ma. El mismo álbum puede tener varias copias a precios distintos.
   - **`nou`**: un disco nuevo no tiene grading que distinguir entre copias, así que UNA fila `item` representa `cantidad` unidades físicas idénticas (stock agregado). Recepciones sucesivas del mismo release/nou se suman a la misma fila con un coste medio ponderado (ver `erp.py::recibir_comanda`), en vez de crear una fila por unidad. Las reservas de una línea `nou` (carrito, petición, club) no usan `status`/`reserved_*` como segona_ma —eso solo tiene un titular posible a la vez—, sino la tabla `stock_holds` (`StockHold`) más `Item.cantidad_reservada`, porque varias reservas distintas pueden coexistir sobre la misma línea agregada.

   El resto del negocio (compra/venta, checkout, TPV, club, Discogs) es el mismo circuito para las dos condiciones; solo cambia cómo se modela y reserva el stock.

2. **Reserva atómica de ejemplares** (`api/app/services/reservations.py`). Para segona_ma, como cada copia es única, al entrar en checkout se reserva con un `UPDATE ... WHERE status='disponible'` comprobando filas afectadas, NUNCA con un SELECT previo + UPDATE (condición de carrera). Reserva de ~20 min, se libera de forma perezosa. Es la pieza más delicada; hay tests que la cubren. Para `nou` (stock agregado), el mismo principio (UPDATE condicionado, nunca SELECT+UPDATE) se aplica sobre `Item.cantidad`/`cantidad_reservada` vía `reserve_stock`/`confirm_stock_sale`/`StockHold`, en vez de `status`.

3. **Snapshots en los pedidos.** `order_items.precio` copia el precio al comprar; `orders.direccion_envio` guarda la dirección como JSON. Los pedidos históricos NUNCA cambian aunque cambie el catálogo o la libreta de direcciones. Nunca recalcular totales leyendo precios actuales.

4. **Auth sin contraseñas.** Google (OIDC) + magic link por email. La sesión es propia: JWT de acceso corto (~15 min) + refresh token rotatorio en cookie httpOnly. Solo se guardan hashes de tokens, nunca el token en claro. Tabla `identities` para vincular proveedores externos (hoy Google, mañana otros).

5. **Guest checkout.** `orders.user_id` es nullable; se puede comprar solo con email. FK con `ON DELETE SET NULL` para poder anonimizar cuentas (RGPD) conservando los pedidos (obligación fiscal de guardar facturas).

6. **Discogs es la fuente de ALTA, no de catálogo.** El cliente busca SIEMPRE en el Postgres local (rápido, sin límites). Discogs solo se consulta cuando el admin da de alta un disco nuevo (autocompletar carátula, sello, año, tracklist). Patrón "API + caché local". Endpoint admin `GET /admin/discogs/search`. Rate limit de Discogs ~60/min: el cliente nunca debe llegar ahí. El alta debe permitir SIEMPRE meter datos a mano (segunda mano rara que no está en Discogs).

## Estado actual (qué está hecho)

Backend de la tienda casi completo y con tests verdes:
- Stock agregado para discos nuevos: una línea `Item` con `cantidad`/`cantidad_reservada` en vez de una fila por copia (ver punto 1 de "Decisiones de diseño"). Cubre recepción de comandas, alta manual, carrito/checkout, TPV, devoluciones, sync de Discogs ("listing virtual de 1": como mucho 1 listing activo por línea mientras haya stock) y club del disco (varias asignaciones pueden compartir la misma línea).
- Catálogo con filtros (artista, sello, formato, género, precio); solo muestra releases con copias disponibles.
- Carrito persistente (logueado o anónimo por cookie).
- Checkout en dos pasos (`/checkout/start` reserva, `/checkout/confirm` crea la venta web ya `pagado`; no hay opción de pago manual/transferencia, así que no tiene sentido un pedido "pendiente de pago" sin pasarela). `numero_seguiment`/`transportista` se rellenan al marcar como `enviado`. Falta integrar la pasarela real (Stripe/Revolut Pay) entre `/start` y `/confirm`.
- Auth completa (Google + magic link + refresh rotatorio + permisos admin).
- Admin: alta de releases/items, búsqueda Discogs, listado y cambio de estado de pedidos (cancelar devuelve el stock a la venta), CRUD básico de posts y eventos.
- Blog y agenda: endpoints públicos de lectura.
- 13 tablas modeladas, Alembic conectado para autogenerar migraciones, script `scripts/import_catalog.py` para importar el CSV del sheet (idempotente, con `--enrich` para traer datos de Discogs).

## Estado actual (qué FALTA, por prioridad)

1. **Frontend de la tienda** (ahora es un placeholder que solo lista el catálogo): ficha de disco, carrito en pantalla, flujo de checkout, login, páginas de blog/agenda, i18n ca/es, diseño visual real.
2. **Panel de admin (UI)**: solo existen los endpoints. Falta la pantalla de alta de discos con búsqueda Discogs, la gestión de pedidos, etc.
3. **ERP — entradas de stock por compra** (NO modelado aún, solo esbozado): registrar compras a proveedor y compras a particulares en mostrador, con coste y trazabilidad. Esto convierte la tienda en "el programa de gestión del negocio".
4. **ERP — TPV / ventas en mostrador y en Discogs**: descontar stock por ventas físicas; registrar ventas hechas en Discogs para que el stock cuadre.
5. **Pasarela de pago**: Stripe (+ valorar Bizum vía Redsys), entre `/checkout/start` y `/confirm`. Tabla `payments`.
6. **Migración del blog de Blogger** (~300 posts): export XML → tabla `posts`, limpiando embeds de Mixcloud/Bandcamp/YouTube.
7. **Envíos**: tarifas reales + recogida en tienda (ya hay `metodo_envio` en el pedido).
8. **Producción**: probar Google OAuth end-to-end (implementado, no probado con credenciales reales), backups automáticos de Postgres fuera del VPS, dominio propio, consultar REBU (régimen especial de bienes usados) con el gestor para la facturación de segunda mano.

## Estructura de archivos

```
api/
  app/
    main.py            FastAPI, monta routers, SessionMiddleware (para OAuth)
    config.py          Settings (pydantic-settings, lee .env)
    database.py        engine, SessionLocal, Base, get_db
    models.py          las 13 tablas — el corazón del diseño
    schemas.py         Pydantic in/out
    routers/           catalog, auth, cart, checkout, admin, blog
    services/          reservations (stock atómico), discogs, security (JWT), emailer
  alembic/             migraciones (env.py conectado a models)
  scripts/import_catalog.py
  tests/               pytest, usan SQLite
web/
  app/                 Next.js App Router (layout, page placeholder, lib/api.js)
infra/Caddyfile
docker-compose.yml
.env.example
```

## Convenciones

- Nombres de campos y enums en español/catalán (es el dominio del negocio): `disponible`, `reservado`, `vendido`, `pendiente_pago`...
- Cada copia de segunda mano NUNCA se vende dos veces: `order_items.item_id` (y `ventas_externas.item_id`) llevan un índice único PARCIAL (`WHERE condicion='segona_ma'`), no una UNIQUE simple — una línea `nou` sí puede aparecer en varias ventas a lo largo del tiempo, o con `cantidad > 1` en una misma línea.
- Al añadir tablas/campos: editar `models.py`, luego `alembic revision --autogenerate -m "..."`, revisar el archivo generado, `alembic upgrade head`.
- Antes de dar por bueno un cambio en el backend, `pytest` debe pasar.

---

# Prompts para continuar

Pega el que toque (o, con Claude Code, simplemente descríbelo: ya tiene este archivo como contexto).

## Prompt A — Frontend de la tienda

```
Lee CLAUDE.md para el contexto. Quiero construir el frontend real de la
tienda en /web (Next.js App Router), reemplazando el placeholder actual.

Páginas: home/catálogo con filtros (consumen GET /api/catalog), ficha de
disco (GET /api/catalog/releases/{id}) con botón de añadir al carrito,
página de carrito, flujo de checkout (start + confirm), y login (Google +
magic link). i18n catalán (principal) y castellano.

Respeta la arquitectura: el front solo habla con la API vía web/app/lib/api.js.
Empieza proponiendo una dirección de diseño visual antes de codear (la tienda
es independiente, de barrio, mezcla vinilo y comunidad; nada genérico).
No toques el backend salvo que falte algún endpoint, en cuyo caso dímelo primero.
```

## Prompt B — Panel de administración (UI)

```
Lee CLAUDE.md. Quiero la interfaz del panel de admin en /web, protegida por
rol admin. Pantallas: alta de disco (la clave) con búsqueda en Discogs
(GET /api/admin/discogs/search), selección de resultado, y campos manuales
de precio y grading antes de guardar (POST /api/admin/releases + /items).
El alta DEBE permitir meter datos a mano sin pasar por Discogs.
Además: listado y gestión de pedidos (GET /api/admin/orders, PATCH estado).
Los endpoints ya existen; esto es solo frontend.
```

## Prompt C — ERP: entradas de stock por compra (modelar primero)

```
Lee CLAUDE.md, sección ERP. Quiero modelar las ENTRADAS de stock por compra
antes de construir pantallas. Necesito registrar:
- Compras a proveedor (novedades): proveedor, fecha, coste por copia, nº de factura.
- Compras a particulares en mostrador (segunda mano): de quién, fecha, precio pagado.
Cada compra crea uno o varios `items` en el stock con su coste de adquisición,
para poder calcular margen al vender. Respeta el modelo releases/items existente.

Propón el modelo de datos (tablas nuevas, relación con items, qué campos),
discútelo conmigo y NO escribas la migración hasta que lo aprobemos. Luego
genera modelos SQLAlchemy + migración Alembic + endpoints + tests.
```

## Prompt D — ERP: TPV y ventas externas

```
Lee CLAUDE.md, sección ERP. Quiero registrar SALIDAS de stock que no son
ventas web: ventas en mostrador (un TPV simple que descuente stock al
instante) y ventas hechas en Discogs (marcar el item como retirado para
que cuadre el inventario). Reutiliza el patrón de reservas/estados de items
existente. Propón el flujo y los endpoints antes de codear.
```

## Prompt E — Pasarela de pago

```
Lee CLAUDE.md. Integra Stripe en el checkout, entre /checkout/start y
/checkout/confirm. Crea una tabla `payments` (pedido, proveedor, importe,
estado, referencia externa) y el webhook de confirmación. Mantén el pago
manual como opción alternativa. Valora Bizum vía Redsys y dime el esfuerzo.
No guardes nunca datos de tarjeta: eso es de Stripe.
```

## Prompt F — Migración del blog de Blogger

```
Lee CLAUDE.md. Tengo el export XML de un blog de Blogger (~300 posts en
catalán). Escribe un script en api/scripts/ que parsee el XML e inserte los
posts en la tabla `posts` (slug, título, contenido HTML, fecha, idioma,
legacy_blogger_url). Limpia o adapta los embeds de Mixcloud, Bandcamp y
YouTube. Idempotente por slug. Empieza preguntándome dónde está el XML.
```
