# Core vs. Vertical — arquitectura y nomenclatura (propuesta)

Este documento reemplaza el enfoque de `docs/NOMENCLATURA.md` (que trataba el problema como "un solo negocio con subdominios inconsistentes") por el enfoque correcto: **esto es una plataforma SaaS multi-vertical** (hoy discos, mañana floristería/quesos/vinos...), y lo que hace falta es separar arquitectónicamente **Core** (lo reutilizable por cualquier vertical) de **Vertical** (lo específico de cada tipo de tienda). La convención de idioma también cambia: **inglés como canónico en DB y API**, con traducciones (i18n) como capa aparte para todo lo que ve el usuario.

**Estado: propuesta, no aplicada.** No se ha tocado modelo, schema, endpoint ni componente.

---

## 1. Lo que existe hoy (diagnóstico)

El proyecto ya tiene un arranque de multi-tenant/multi-vertical, pero incompleto y sin capa de separación real:

- `Tenant.vertical` es un `String(30)` **sin ningún constraint en BD** (ni `Enum`, ni `CheckConstraint`). Solo se valida en un punto: el endpoint `POST /superadmin/tenants` (`Literal["vinils", "floristeria"]` en `superadmin.py`). Un INSERT directo o un tenant dado de alta por otra vía no tiene ninguna validación.
- El catálogo de verticals soportados está **duplicado en 3 sitios sin fuente común**: el `Literal` del backend, un array `VERTICALS` hardcodeado en `web/app/superadmin/page.jsx`, y una serie de `vertical === 'floristeria' ? ... : ...` repartidos por el admin (que tratan implícitamente "cualquier cosa que no sea floristeria" como "vinils" — un tercer vertical nuevo caería en el comportamiento de discos por defecto).
- Existe **un** caso de extensión real: `ReleaseFloristeria` (tabla aparte, 1:1 con `Release`, con `color`/`tipus_flor`/`durabilitat_dies`). Pero es asimétrico: los campos de disco (`artista`, `sello`, `formato`, `genero`, `tracklist`, `credits`, `discogs_release_id`, `spotify_album_id`, `estilos`, `pais`, `esta_sonant`) viven **directamente en `Release`**, sin extensión equivalente. Es decir: hoy no hay "core + vertical", hay "vinilo como base + floristería como añadido".
- **El backend no aísla nada por vertical.** `ReleaseIn`/`ReleaseOut` incluyen siempre los campos de disco y de floristería a la vez; `_upsert_floristeria()` en `admin.py` escribiría los campos de floristería igualmente para un tenant `vinils` si el payload los trajera — nada lo impide server-side. La decisión de "qué campos mostrar" es **enteramente responsabilidad del frontend** (`isVinils`/`isFloristeria` repartidos en `page.jsx`, `disc/[id]/page.jsx`, `cataleg/page.jsx`, `admin/catalogo/page.jsx`, `admin/layout.jsx`).
- Hay vocabulario de vertical **filtrado dentro de tablas/enums que deberían ser genéricos**: `OrderOrigen.discogs`/`.subscripcio` dentro de `Order` (tabla de pedidos, genérica), `CanalVenta.discogs` dentro de `VentaExterna` (TPV, genérico), `HistorialCompra`/`SolicitudCompraLinea` con columnas `artista`/`titulo`/`sello` directamente (en vez de una referencia genérica a producto).
- Hay copy hardcodeado (fuera de i18n) con vocabulario de discos en pantallas del admin que en estructura son genéricas: TPV, compras, resultado contable — ej. "Grading disc", "Discos comprats", "Cost vendes TPV / Discogs".
- Servicios inequívocamente de vertical "discos": `services/discogs.py`, `discogs_sync.py`, `services/spotify.py`, el "club del disc" completo (`Subscripcio` y todo lo que cuelga de él, con `generes_preferits` haciendo matching contra `Release.genero`).
- Lo genuinamente genérico hoy (confirmado por grep — cero menciones a discogs/spotify/vinil/floristeria) ya está limpio: `auth.py`, `cart.py`, `checkout.py`, `admin_users.py`, `blog.py`, `newsletter_public.py`, y los modelos `User`, `Address`, `Order`/`OrderItem` (salvo el enum mencionado), `Payment`, `Proveedor`, `Compra`, `Comanda`, `Despesa`, `Post`/`Pagina`/`Event`.

---

## 2. Principio de diseño objetivo

Tres capas, no dos:

- **Capa 0 — Traducción / UI.** Texto visible al usuario (i18n `ca`/`es`/`en`, labels de enums, copy del admin). Nunca determina estructura de datos ni nombres de campo.
- **Capa 1 — Core.** Todo lo que cualquier tienda física+online necesita sin importar qué vende: identidad/auth, direcciones, carrito, checkout, pedidos, pagos, compras a proveedor, ventas de mostrador/TPV, caja, contabilidad, CMS (blog/agenda), newsletter, y el "esqueleto" de producto (existe un Product, tiene un nombre, una imagen, un precio, una cantidad en stock, un estado). Nombrado en **inglés**.
- **Capa 2 — Vertical.** Lo que solo tiene sentido para un tipo de tienda: para discos, artista/sello/formato/tracklist/grading/Discogs/Spotify/club del disc; para floristería, color/tipo de flor/durabilidad; para un hipotético vertical de vinos, añada/cosecha/región. Cada vertical **extiende** el Core mediante tablas 1:1 (el patrón que `ReleaseFloristeria` ya empezó, generalizado a todos los verticals por igual, incluido discos). Nombrado también en **inglés**, con prefijo/namespace del vertical.

Regla práctica para clasificar un campo nuevo: **¿lo necesitaría una floristería o una quesería igual que una tienda de discos?** Si sí → Core. Si no → extensión de vertical, nunca mezclado en la tabla Core.

---

## 3. Convención de idioma (reemplaza la propuesta anterior en `NOMENCLATURA.md`)

- **DB y API: inglés**, tanto para nombres de tabla/columna/schema/parámetro como para **valores de enum** (`available`/`reserved`/`sold` en vez de `disponible`/`reservado`/`vendido`). Los valores de enum no son texto de usuario — el frontend los traduce a la etiqueta visible vía i18n, igual que ya hace con las claves de traducción. Esto es lo estándar en SaaS multi-tenant/multi-idioma: el dato es estable e independiente de idioma, la presentación no.
- **UI/i18n: catalán (principal) y castellano**, sin cambios — vive en `web/messages/*.json` y en la tabla `translations` para el admin. Con inglés en el dato ya no hace falta "traducir campos", solo mapear `enum value → label` en cada idioma, lo cual es más simple que el estado actual (hoy varias pantallas del admin hardcodean catalán directamente en el JSX en vez de usar una clave de traducción — esto debería corregirse igualmente, es independiente del idioma elegido para el dato).
- Esto además **resuelve gratis** la inconsistencia `status`/`estado`/`estat` detectada antes: el nombre canónico pasa a ser `status` (inglés), que ya es el que usan `Item`/`Order` hoy — menos migración que la propuesta anterior en castellano.
- Rutas públicas (`/cataleg`, `/disc/[id]`, `/carret`) siguen en catalán a propósito (SEO/marca, decisión de producto) — eso es Capa 0, no Capa 1/2, y no cambia.

---

## 4. Clasificación propuesta

### 4.1 Core (nombre inglés propuesto)

| Área | Modelo actual → Core propuesto | Notas |
|---|---|---|
| Plataforma | `Tenant` → `Tenant`, `PlatformAdmin` → `PlatformAdmin` | añadir tabla `Vertical` real (ver §5) en vez de string libre |
| Auth | `User`, `Identity`, `RefreshToken`, `AuthToken` | ya en inglés, sin cambios de fondo |
| Direcciones | `Address` | ya en inglés |
| Catálogo (esqueleto) | `Etiqueta` → `Tag`, `Seccio` → `Category`, `ReleaseEtiqueta` → `ProductTag` | |
| Producto (esqueleto) | `Release` → **`Product`** (solo campos genéricos: `id`, `tenant_id`, `name`, `description`, `image_url` principal, `category_id`, `ean`/barcode, `weight_g`, `coming_soon`, `available_at`, `created_at`) | todo lo demás de `Release` hoy es vertical:discos, ver §4.2 |
| Imágenes producto | `ReleaseImage` → `ProductImage` | |
| Stock (esqueleto) | `Item` → **`StockItem`** (`id`, `product_id`, `price`, `condition` [`new`/`used`, enum genérico], `quantity`, `quantity_reserved`, `status` [`available`/`reserved`/`sold`/`retired`], `reserved_until`, `reserved_by_cart_id`, `entry_date`, `cost_of_acquisition`, `purchase_id`) | `estado_disco`/`estado_funda`/`codi_discogs` salen a extensión de vertical, ver §4.2 |
| Carrito | `Cart`, `CartItem` | ya casi inglés |
| Pedidos | `Order`, `OrderItem`, `Payment` | limpiar `OrderOrigen` (ver §4.3) |
| ERP compras | `Proveedor` → `Supplier`, `Compra` → `Purchase`, `Comanda`/`ComandaLinea` → `PurchaseOrder`/`PurchaseOrderLine` | |
| ERP peticiones | `SolicitudCompra`/`Linea` → `PurchaseRequest`/`Line`, `PeticionCliente` → `CustomerRequest` | hoy tienen columnas `artista`/`titulo`/`sello` sueltas — deberían ser una referencia genérica a producto + un campo libre `product_description`, no vocabulario de disco |
| ERP ventas/caja | `VentaExterna` → `ExternalSale`, `CajaSession`/`Movimiento` → `CashSession`/`CashMovement`, `Devolucion*` → `SaleReturn`/`PurchaseReturn` | limpiar `CanalVenta` (ver §4.3) |
| Contabilidad | `Despesa` → `Expense`, `CompteBancari`/`MovimentBancari` → `BankAccount`/`BankMovement`, `TipusIva` → `TaxRate`, `MargeConfig` → `MarginConfig`, `TramEnviament` → `ShippingTier`, `PeriodeComptable` → `AccountingPeriod`, `CaixaDiaria` → `DailyCashSummary`, `ConfiguracioBotiga` → `StoreConfig` | `StoreConfig` debe perder los flags `discogs_habilitat`/`subscripcions_actives` (eso es config de vertical, no de tienda genérica, ver §5) |
| CMS | `Translation`, `Pagina` → `Page`, `Post`, `Event` | ya casi inglés |
| Newsletter | `NewsletterCampaign`, `NewsletterSend` | ya inglés |

### 4.2 Vertical: Records (discos) — nuevo, extensión simétrica a floristería

| Nuevo | Contenido (movido desde Core actual) |
|---|---|
| `RecordProduct` (extiende `Product` 1:1, como hace `ReleaseFloristeria` hoy) | `artist`(artista), `label`(sello), `catalog_number`(referencia), `format`(formato), `music_genre`(genero), `country`(pais), `styles`(estilos), `tracklist`, `credits`, `discogs_release_id`, `spotify_album_id`, `now_playing`(esta_sonant) |
| `RecordStockDetail` (extiende `StockItem` 1:1) | `media_condition`(estado_disco), `sleeve_condition`(estado_funda), `discogs_code`(codi_discogs) |
| `RecordWeightByFormat` (era `PesFormat`) | tabla auxiliar de peso por formato de vinilo — específica de discos, no genérica |
| `SpotifyConnection` | ya es 100% música, se queda tal cual pero movida conceptualmente al módulo vertical |
| Club del disco: `RecordClubSubscription` (era `Subscripcio`), `RecordClubConfig`, `SubscriptionCharge`(`CobramentSubscripcio`), `SubscriptionAssignment`(`Assignacio`) | el mecanismo (cobro recurrente + asignación de caja curada) podría generalizarse a Core en el futuro si un segundo vertical lo necesita (ej. "caja mensual de quesos"), pero hoy solo lo usa discos — se deja en vertical y se revisita si aparece un segundo caso de uso real |
| Servicios | `services/discogs.py`, `discogs_sync.py`, `services/spotify.py`, `services/subscripcions.py` |

### 4.3 Vertical: Floristry (ya existe, solo renombrar)

| Nuevo | Contenido |
|---|---|
| `FloristryProduct` (era `ReleaseFloristeria`) | `color`, `flower_type`(tipus_flor), `durability_days`(durabilitat_dies) |

### 4.4 Fugas de vertical dentro de enums Core (limpiar)

- `OrderOrigen`: valores `discogs`/`subscripcio` dentro de un enum por lo demás genérico (`web`). Propuesta: `Order.origin` pasa a string libre validado por un registro **por vertical** (cada vertical declara sus propios orígenes posibles), no un enum fijo en el modelo Core.
- `CanalVenta`: mismo caso con `discogs` dentro de `mostrador`/`otro`. Misma solución.

---

## 5. Vertical como registro real, no string libre

Sustituir el string sin validar por un **registro único** (una tabla `verticals` o, si se prefiere sin tocar BD todavía, un módulo Python `app/verticals/registry.py` con un diccionario), que sea la única fuente de verdad para:

- id (`records`, `floristry`...) y etiqueta por idioma (para el `<select>` de superadmin — hoy hardcodeado por duplicado en `web/app/superadmin/page.jsx`)
- qué tablas de extensión aplica (`RecordProduct`+`RecordStockDetail` para `records`, `FloristryProduct` para `floristry`)
- qué feature flags activa por defecto (`discogs_enabled`, `spotify_enabled`, `subscriptions_enabled` — hoy `discogs_habilitat`/`subscripcions_actives` son columnas sueltas en `StoreConfig`; deberían ser un JSON/tabla `tenant_features` genérica, para que un vertical nuevo no obligue a añadir columnas a `StoreConfig` cada vez)

El endpoint `GET /superadmin/tenants` (creación) y `GET /config/public` (lectura por el frontend) leen de este registro en vez de tener cada uno su propia lista. Esto también resuelve el bug latente de que un vertical nuevo, hoy, cae automáticamente en el comportamiento de "records" en el admin de catálogo por no tener `else if` explícito.

**Aislamiento server-side real**: los endpoints de catálogo/admin deberían serializar solo la extensión que corresponde al `tenant.vertical` (vía el schema Pydantic correcto según el registro), en vez de devolver siempre ambos conjuntos de campos como ocurre hoy. Esto no es solo estética de nomenclatura — hoy nada impide que un tenant de floristería reciba u escriba campos de Discogs a través de la API si el payload los trae.

---

## 6. Plan por fases (propuesta, sin ejecutar)

1. **Registro de verticals** (§5) — bajo riesgo, no toca datos existentes, solo añade la fuente de verdad y hace que superadmin/frontend lean de ahí.
2. **Extensión simétrica de discos**: crear `RecordProduct`/`RecordStockDetail`, migrar datos desde `Release`/`Item`, actualizar `ReleaseOut`→ separar en `ProductOut` (core) + `RecordProductOut` (extensión) igual que ya se hace con floristería. Alto volumen de cambio (toca catálogo público, admin, Discogs sync) pero mecánico y ya hay precedente (`ReleaseFloristeria`) que sirve de plantilla.
3. **Aislamiento server-side por vertical** en los endpoints de catálogo/admin (§5) — depende de 1 y 2.
4. **Rename Core a inglés** (`Release`→`Product`, `Item`→`StockItem`, `Compra`→`Purchase`, etc.) — mecánico, alto en número de archivos tocados pero bajo en riesgo lógico si se hace después de 2 (evita renombrar dos veces).
5. **Limpiar fugas de vertical en enums Core** (`OrderOrigen`, `CanalVenta`) — depende del registro de verticals.
6. **Sacar copy hardcodeado del admin a i18n** (independiente del resto, se puede hacer en paralelo).
7. **Config de features por tenant** (`tenant_features` genérico en vez de columnas sueltas en `StoreConfig`).

No se toca `estado_disco`/`estado_funda` como concepto (grading de vinilo) — eso siempre fue y sigue siendo vertical:records, solo cambia dónde vive (tabla de extensión en vez de columna de `Item`).

---

## 7. Decisiones confirmadas (2026-08-09)

1. **Idioma canónico: inglés**, en DB/API, tal como propone §3. Catalán/castellano quedan solo en i18n y en valores mostrados.
2. **Fase 2 (extracción `RecordProduct`/`RecordStockDetail`) se pospone.** Ahora se empieza solo por sentar las bases: registro de verticals (Fase 1) + rename a inglés del Core que ya es genérico. La extracción del catálogo de discos queda planificada pero no es el siguiente paso.
3. **El club de suscripción se diseña como capacidad Core desde ahora**, no como algo específico de discos — se espera un segundo vertical con suscripciones. Ver §8 para el rediseño.
4. **El registro de verticals es una tabla en BD**, gestionable desde superadmin sin deploy. Ver §9 para el modelo de datos propuesto.

---

## 8. Rediseño: suscripción como capacidad Core

Con la decisión del punto 3, el "club del disco" deja de ser un módulo 100% vertical:records y se separa en un **mecanismo Core de caja recurrente** (cobro periódico + selección de items + envío) más una **extensión de preferencias por vertical** (qué criterio se usa para elegir qué va en la caja).

| Core (genérico, cualquier vertical con suscripción) | Vertical:records (extensión) |
|---|---|
| `Subscription` (era `Subscripcio`): `id`, `tenant_id`, `user_id`, `status` (`pending_payment`/`active`/`paused`/`cancelled`), `address_id`, `frequency_months`(periodicitat_mesos), `quantity`(quantitat), `price_per_period`(preu_periode), `payment_processor_ref`(redsys_identifier/cof_txnid), `next_billing_date`, `created_at`, `cancelled_at` | `SubscriptionPreferenceRecords` (extiende `Subscription` 1:1, patrón igual que `RecordProduct`/`FloristryProduct`): `preferred_music_genres`(generes_preferits) — para un vertical de flores sería `SubscriptionPreferenceFloristry` con `preferred_colors`/`preferred_flower_types`, etc. |
| `SubscriptionConfig` (era `ConfiguracioSubscripcio`): `price_per_item`(preu_per_disc), `margin_min_pct`, `margin_max_pct`, `available_period_months`, `available_quantities` | — (config de precio/margen es genérica; el catálogo de géneros musicales que alimenta el selector sí es de vertical) |
| `SubscriptionCharge` (era `CobramentSubscripcio`): `id`, `subscription_id`, `period`, `amount`, `status`(`pending`/`charged`/`failed`), refs de pasarela, `created_at` | — |
| `SubscriptionAssignment` (era `Assignacio`): `id`, `charge_id`, `subscription_id`, `stock_item_id`, `status`(`proposed`/`confirmed`/`skipped`/`no_match`), `order_id`, `created_at`, `confirmed_at` | — |
| `StockItem.subscription_pool` (ya existe en `Item.subscripcio_pool`) — marca un item disponible para el pool de asignación de cajas; es genérico, se queda en Core tal cual | — |
| Interfaz Core de "selector": el mecanismo de proponer qué `StockItem` va en cada caja se define como un punto de extensión (una función/estrategia por vertical), no una tabla | Implementación concreta: `services/records/subscription_selector.py` (era `services/subscripcions.py`), con `GENERES_DISCOGS` como taxonomía de vertical:records |

Esto significa que cuando llegue el segundo vertical con suscripción, solo hace falta: (a) su propia tabla `SubscriptionPreference<Vertical>`, (b) su propia implementación del selector, (c) activar el feature flag `subscriptions_enabled` en su fila de `tenant_features` (§9) — nada del Core de facturación/cobro/envío se toca.

---

## 9. Modelo de datos propuesto: registro de verticals (tabla en BD)

Diseño propuesto para discutir (no se escribe migración hasta aprobarlo, siguiendo la misma cautela que ya usa este proyecto para cambios de modelo ERP):

```
verticals
  id              string PK   -- "records", "floristry" (slug estable, usado en código)
  name_ca         string      -- etiqueta para el selector de superadmin
  name_es         string
  name_en         string
  active          bool        -- permite dar de alta un vertical y activarlo después
  created_at

tenant_features
  tenant_id       FK -> tenants.id
  feature_key     string      -- "discogs_sync", "spotify", "subscriptions", ...
  enabled         bool
  config          JSON null   -- parámetros propios del feature si hiciera falta (opcional)
  PK (tenant_id, feature_key)
```

- `Tenant.vertical` (string libre actual) pasa a ser `Tenant.vertical_id` con FK real a `verticals.id` — ya no es posible un valor no registrado.
- `tenant_features` sustituye a los flags sueltos hoy en `StoreConfig` (`discogs_habilitat`, `subscripcions_actives`) y a cualquier flag global en `config.py` (`spotify_enabled`, hoy global para toda la plataforma) — un vertical nuevo no obliga a añadir columnas a `StoreConfig`.
- Al dar de alta un tenant, `POST /superadmin/tenants` deja de tener el `Literal["vinils","floristeria"]` hardcodeado: valida contra `SELECT id FROM verticals WHERE active`, y siembra sus `tenant_features` por defecto según lo que tenga sentido para ese vertical (esto sí puede vivir como un pequeño mapeo en código — "qué features activa un vertical por defecto" — sin que eso invalide que el registro de verticals en sí es una tabla).
- `GET /config/public` sigue devolviendo `vertical` (ahora el `id` de la tabla) más el conjunto de `tenant_features` habilitadas, para que el frontend deje de tener sus propios `isVinils`/`isFloristeria` hardcodeados y pase a comprobar `features.includes('discogs_sync')`, etc.

¿Apruebas este modelo para escribir ya los modelos SQLAlchemy + migración Alembic (Fase 1), o quieres ajustar algo antes (nombres de columna, si `tenant_features.config` JSON hace falta ahora o se añade cuando haga falta, etc.)?

---

## 10. Fase 1 — implementada (2026-08-09)

- Tabla `verticals` (`id`, `name_ca`, `name_es`, `name_en`, `active`, `created_at`) + modelo `Vertical` en `models.py`, sembrada con `records` y `floristry` (slugs en inglés, sustituyen a `vinils`/`floristeria`).
- `Tenant.vertical` (string libre) → `Tenant.vertical_id` (FK a `verticals.id`), con relationship `Tenant.vertical`.
- Migración Alembic `a09cf2105676` (nueva tabla + remapeo de valores existentes `vinils`→`records`/`floristeria`→`floristry` + drop de la columna antigua). **Escrita a mano** (no autogenerada — no se ha consultado la BD real de este entorno) — revisar antes de aplicarla en un entorno con datos reales, y **no aplicada todavía contra ningún Postgres** (ni dev ni prod).
- `POST/GET /superadmin/tenants` y nuevo `GET /superadmin/verticals` (fuente única para el `<select>` del frontend, sustituye el array que estaba hardcodeado en `web/app/superadmin/page.jsx`).
- `GET /config/public` sigue devolviendo la clave `vertical`, ahora con el slug nuevo (`records`/`floristry`) en vez de `vinils`/`floristeria`.
- Frontend: `useTenantVertical.js` y los `isVinils`/`isFloristeria` de `page.jsx`, `cataleg/page.jsx`, `disc/[id]/page.jsx`, `admin/layout.jsx`, `admin/catalogo/page.jsx` actualizados a los slugs nuevos.
- De paso, se corrigió un bug preexistente en `superadmin.py::create_tenant`: el `return` final no incluía el campo de vertical que `TenantOut` exigía como obligatorio (habría fallado con `ValidationError` en cualquier alta de tenant real).
- `pytest`: 383 passed.

**Deliberadamente fuera de esta fase** (según lo acordado en §7, punto 2): no se ha tocado `ReleaseFloristeria`/`Release` (Fase 2), ni `ConfiguracioBotiga.discogs_habilitat`/`subscripcions_actives`/`Settings.spotify_enabled` (siguen siendo la fuente de verdad real de esos interruptores; la tabla `tenant_features` de §9 queda para cuando se aborde esa fase, para no mezclar el rename de identidad con el rewiring de gates de negocio como `require_discogs_enabled`).

**Pendiente antes de dar esto por cerrado**: aplicar la migración contra la base de datos real (dev y luego prod). Actualización: **aplicada en dev**, ver §11.

---

## 11. Fase 2 — implementada (2026-08-09)

Extracción simétrica de `RecordProduct`/`RecordStockDetail` desde `Release`/`Item`:

- **Modelo**: `Release` y `Item` quedan como core puro (ver §4.1). Los campos de discos (`artista`, `sello`, `referencia`, `formato`, `anio`, `genero`, `pais`, `estilos`, `tracklist`, `credits`, `discogs_release_id`, `spotify_album_id`, `esta_sonant` en `RecordProduct`; `codi_discogs`, `estado_disco`, `estado_funda` en `RecordStockDetail`) viven en tablas de extensión 1:1, exactamente simétricas a `ReleaseFloristeria`.
- **Compatibilidad hacia atrás en Python**: `Release`/`Item` exponen esos mismos nombres como *properties* con getter+setter que crean la fila de extensión de forma perezosa (`_ensure_record()`/`_ensure_record_detail()`). Esto significa que el 95% del código existente (constructores `Release(artista=...)`, lecturas `release.artista`, escrituras `release.genero = ...`) **no tuvo que tocarse** — solo los usos a nivel de clase en queries SQL (`Release.artista.ilike(...)`, `order_by(Release.artista)`, `select(Release.artista, ...)`), que sí necesitan un `JOIN`/`LEFT OUTER JOIN` explícito contra la tabla de extensión.
- **Alcance del rewrite de queries**: `catalog.py`, `admin.py`, `erp.py`, `admin_subscripcions.py`, `me.py` (routers); `catalog_sync.py`, `spotify.py`, `subscripcions.py`, `discogs_sync.py` (services); `import_catalog.py`, `enrich_releases.py`, `find_discogs_matches.py`, `enrich_images.py`, `backfill_ean.py`, `backfill_formato.py`, `sync_discogs_inventory.py`, `import_historial_compres.py` (scripts); más los tests que hacían lo mismo (`test_catalog_sync.py`, `test_comandas.py`, `test_backfill_formato_query.py`). El catálogo público (`catalog.py`) usa `LEFT OUTER JOIN` (un release floristry no tiene `RecordProduct` y aun así debe listarse); los flujos inequívocamente records-only (ERP de compras, Discogs sync, subscripciones, Spotify) usan `JOIN`/`outerjoin` según convenía a cada caso.
- **Bug real encontrado y corregido de paso**: `PATCH /admin/releases/{id}/esta-sonant` hacía un `UPDATE` masivo (`db.query(Release).filter(...).update({"esta_sonant": False})`) directamente sobre la columna — dejó de existir como columna mapeada, así que habría reventado con `AttributeError` en cuanto se llamara. Ahora apunta a `RecordProduct`.
- **Schema**: único cambio de contrato público — `ReleaseOut.artista` y `CartItemOut.artista` pasan de `str` (obligatorio) a `str | None` (un release de floristry legítimamente no tiene artista). Todo lo demás del JSON de la API queda idéntico, cero cambios en el frontend.
- **Migración** `0c06c9e78a72`: crea `release_records`/`record_stock_details`, backfill incondicional (todas las filas existentes, de cualquier vertical, preservando sus valores exactos), y `DROP COLUMN ... CASCADE` de las 13+3 columnas antiguas (el `CASCADE` en `items.codi_discogs` es necesario porque arrastraba el `UNIQUE(tenant_id, codi_discogs)`, recreado ya en `record_stock_details`).
- **Aplicada en dev**: verificado con los 3 releases/3 items reales existentes — los datos se preservaron exactamente (mismo `artista`, `formato`, etc., ahora servidos vía el join), y `GET /catalog` (con y sin filtro `q`/`artista`) responde correctamente contra Postgres real, no solo en los tests con SQLite.
- `pytest`: 383 passed.

**Pendiente**: aplicar esta migración en producción cuando toque desplegar (no se ha tocado ninguna base de datos de producción). El resto del plan de Fase 2 original (limpieza de `OrderOrigen`/`CanalVenta`) sigue pendiente para una fase posterior.

---

## 12. Fase 3 — aislamiento server-side por vertical (2026-08-09)

Hasta ahora `POST/PUT /admin/releases` aceptaba y persistía **ambas** extensiones (`RecordProduct` y `ReleaseFloristeria`) sin mirar el vertical del tenant — la única barrera era que el frontend ocultaba los campos que no tocaban (`isVinils`/`isFloristeria`). Un tenant floristry podía acabar con una fila `RecordProduct` si el payload traía `artista`/`sello` (de hecho ya pasaba: el release de `florqa` en dev tenía `artista='Hivernacle QA'`, un valor placeholder). Fase 3 cierra ese hueco:

- `routers/admin.py`: `RECORD_FIELDS` (nuevo, simétrico a `FLORISTERIA_FIELDS`) + `_upsert_record()` (simétrico a `_upsert_floristeria()`) + `_upsert_vertical_extension()`, que mira `request.state.tenant.vertical_id` y aplica **solo** la extensión que corresponde — la otra se ignora aunque venga en el payload. `create_release`/`update_release` ahora reciben `request: Request` para poder consultarlo.
- `spotify_album_id` se dejó fuera de `RECORD_FIELDS` a propósito: no forma parte de `ReleaseIn` (se rellena aparte, en el flujo de enrich de Discogs) — incluirlo habría hecho que cada `PUT /admin/releases/{id}` borrara el valor ya guardado. Esto salió a la luz como un `KeyError` real al correr los tests, no como algo hipotético.
- `schemas.py`: `ReleaseIn.artista` pasa a opcional, coherente con que un tenant floristry ya no necesita rellenarlo (el backend lo ignora igualmente si lo manda).
- `test_fase4.py::test_release_floristeria_round_trip` conmuta el tenant de pruebas a `vertical_id="floristry"` antes de ejercer el endpoint — antes el test pasaba con el tenant `records` por defecto, precisamente porque no había aislamiento que lo impidiera.
- Desplegado en dev (rebuild + restart de `api`/`web`) — sin migración de BD, es solo lógica de aplicación, no hay cambio de esquema.
- `pytest`: 383 passed.

**Fuera de alcance de esta fase**: no se tocó el lado de lectura (`ReleaseOut` sigue exponiendo ambos conjuntos de campos, simplemente vacíos para el vertical que no toca) ni `Item`/`ItemIn` (no hay dos verticales compitiendo por los mismos campos ahí, el riesgo de contaminación cruzada no existe igual que en `Release`).

---

## 13. Fase 7 — registro `tenant_features` (2026-08-09)

Sustituye las columnas sueltas `ConfiguracioBotiga.discogs_habilitat`/`subscripcions_actives` (§9) por la tabla `tenant_features` (`tenant_id`, `feature_key`, `enabled`, `config` JSON opcional) — un vertical nuevo con su propio interruptor ya no obliga a añadir una columna a `configuracio_botiga`.

- **Mismo patrón de passthrough que la Fase 2**: `ConfiguracioBotiga.discogs_habilitat`/`.subscripcions_actives` pasan a properties (getter+setter) que leen/escriben en `TenantFeature` vía `object_session(self)`. Todos los consumidores existentes (`require_discogs_enabled` en `admin.py`, `_subscripcions_actives` en `subscripcions_public.py`, `get_discogs_token_if_enabled` en `discogs_sync.py`, el PATCH genérico de `configuracio.py` con `setattr(config, k, v)`, y `ConfiguracioBotigaOut`/`Public` con `from_attributes=True`) siguieron funcionando **sin tocarlos** — cero cambios en el frontend, mismo truco que ya dio buen resultado en la extracción de `RecordProduct`.
- **Límite real del patrón, encontrado esta vez**: a diferencia de `Release.record` (una relación ORM 1:1 que SQLAlchemy resuelve sola en el flush), aquí la property necesita `object_session(self)` para consultar `TenantFeature` — y eso solo funciona si el objeto **ya está adjunto a una sesión**. Construir `ConfiguracioBotiga(discogs_habilitat=True)` como kwarg del constructor (que es justo como lo hacían `superadmin.py::create_tenant` y `tests/conftest.py`) falla en silencio porque en ese momento el objeto todavía no tiene sesión. Se corrigió en ambos sitios: crear sin ese kwarg, `db.add()` + `db.flush()`, y solo entonces asignar la property.
- **Bug real de test descubierto de paso** (no relacionado con `tenant_features` en sí, pero salió a la luz al tocar el fixture): `tests/conftest.py` necesitaba guardar `config = ConfiguracioBotiga(...)` en una variable para poder hacer el flush+asignación de arriba. Como el fixture es una función generadora que se queda suspendida en `yield session` durante todo el test, esa variable local mantenía el objeto vivo (con referencia fuerte) en el identity map de la sesión durante todo el test — así que `db.get(ConfiguracioBotiga, 1)` en el test devolvía el objeto cacheado de ANTES de cualquier cambio hecho por una petición HTTP (que usa otra sesión), no el valor recién commiteado. Antes, como el objeto nunca se guardaba en una variable, el recolector de basura lo liberaba casi enseguida y la caché quedaba "vacía" por casualidad — un test verde que dependía del timing del GC, no de una garantía real. Arreglado con `session.expire_all()` antes del `yield`, explícito y determinista en vez de accidental.
- **Migración** `8ac01b667f42`: crea `tenant_features`, backfill solo de las filas con el flag en `true` (sin fila = `false`, igual que el default de antes), `DROP COLUMN` de las dos columnas antiguas.
- **Aplicada en dev**: verificado que los 6 tenants reales conservaron su valor exacto (solo `recordstore` tenía `discogs_habilitat=true`, ahora vive como única fila en `tenant_features`), y `GET /config/public` responde correctamente contra Postgres real para dos tenants distintos.
- `pytest`: 383 passed.

**Fuera de alcance**: `spotify_enabled` (Settings, `.env`) se queda global a propósito — es un kill-switch de plataforma entera, no por tenant, así que no encaja en `tenant_features` sin cambiar su semántica (una decisión que no estaba pedida). No se tocó el admin UI de configuración (`admin/configuracio/page.jsx`): como el contrato JSON no cambió, sigue funcionando igual sin modificarlo.

---

## 14. Estado del plan y lo que queda

Hecho: Fase 1 (registro de verticals), Fase 2 (extracción `RecordProduct`/`RecordStockDetail`), Fase 3 (aislamiento server-side), Fase 7 (`tenant_features`), Fase 6 (i18n admin — ver §15), Fase 4 Etapa A (rename DB-only de columnas Core a inglés — ver §16). Las seis aplicadas y verificadas en dev.

**Pendiente, evaluado y aparcado deliberadamente** (no por olvido):

- **Fase 5 (limpiar `OrderOrigen`/`CanalVenta`)**: la propuesta original era convertirlos de Enum de Postgres a string libre validado por un registro por vertical. Al revisar los ~6 sitios reales que los usan, la fuga es puramente cosmética (un enum "core" con dos valores de vertical dentro) — no bloquea nada: añadir un origen nuevo para un vertical futuro sigue siendo una migración de una línea (`ALTER TYPE ... ADD VALUE`). El coste real (migración sobre `orders`/`ventas_externas`, tablas con datos de pedidos reales, más construir un registro que hoy no existe) supera el beneficio (limpieza conceptual). Se deja documentado como decisión aceptada, no como pendiente técnico. Nota: los *nombres de columna* `origen`/`canal` ya se renombraron a `origin`/`channel` en la Fase 4 Etapa A (§16) — lo que queda pendiente aquí es solo la fuga de vocabulario de vertical *dentro de los valores del enum* (`discogs`/`subscripcio`), no el nombre de la columna.
- **Fase 4 Etapa B (rename de atributos Python + Pydantic + frontend)**: la Etapa A (§16) dejó la BD en inglés sin tocar el contrato JSON; la Etapa B es el cambio real de superficie pública — schemas.py, routers, servicios y **cada página del frontend que consume esos campos** — sin suite de tests que cubra el frontend. No se ha empezado; necesita su propia sesión dedicada con margen para verificación manual del storefront y el admin, dominio a dominio (catálogo, luego checkout, luego ERP...), nunca todo de golpe. Antes de empezar, confirmar con el usuario el orden de dominios y si se aprueba cada lote antes del siguiente, dado el tamaño.

---

## 15. Fase 6 — i18n admin (implementada, 2026-08-25)

Las 8 pantallas del admin que todavía tenían copy en catalán hardcodeado directamente en el JSX (en vez de pasar por `useT()`/`t('clave', 'fallback')` contra la tabla `translations`) quedan convertidas: `compras`, `subscripcions`, `tpv`, `vendes-web`, `catalogo`, `configuracio`, `resultat` (+ su componente `CaixaDiaria`), `peticions`.

- **Patrón aplicado, uniforme en las 8**: `import { useT } from '.../lib/i18n'` + `const t = useT();` en cada componente con texto visible (incluyendo modales y subcomponentes, no solo la página de nivel superior); mapas de labels estáticos (`ESTAT_LABEL`, `CATEGORIA_LABELS`, etc.) convertidos a funciones `xxxLabel(t, valor)` que llaman a `t(\`namespace.xxx.${valor}\`, FALLBACK[valor])`; interpolación de variables vía convención `{placeholder}` + `.replace()` (no hay soporte nativo de interpolación en `t()`); colisiones de nombre entre la función real `t` y variables locales (`.map(t => ...)`, parámetros de función llamados `t`) resueltas renombrando la variable local (`row`, `tram`, `iv`...), nunca la función de traducción.
- **Reutilización de claves existentes** donde el texto coincidía exactamente (`common.cancel`, `common.save`, `common.loading`, `common.condition.new/used`) para no duplicar; claves nuevas añadidas a `api/scripts/seed_translations.py` bajo comentarios `# Fase 6 (i18n admin) — ampliació de <archivo>` según el archivo de origen — se pasó de ~700 a 999 claves (×3 idiomas).
- **Excepción deliberada, ya existente antes de esta fase y respetada**: los documentos impresos (`ReceiptPrintArea` en `tpv/page.jsx`, la etiqueta de envío en `vendes-web/page.jsx`) se quedan en catalán fijo a propósito — un tique o etiqueta física no cambia de idioma según quién esté logueado en el admin en ese momento, igual que un PDF de comanda a proveedor.
- **Verificación por archivo** (sin suite de tests que cubra JSX, así que la red de seguridad fue manual): greps de texto acentuado/capitalizado fuera de `t(...)`, comprobación de que cada componente con texto tiene `useT()`, extracción de todas las claves `t('...')`/`` t(`...${var}`) `` usadas y cross-check contra `seed_translations.py` (incluyendo las claves dinámicas construidas por template literal, enumeradas a mano), `pytest` verde (383 tests, sin tocar ninguno), rebuild+reseed de los 6 tenants reales, y QA visual en `http://localhost:8080/admin/...` alternando CAT/ESP en cada pantalla, pestaña y modal — en `peticions`, al no haber datos de peticiones en ningún tenant, se creó y canceló una petición de prueba en el tenant de demo (`escaparate`) para poder verificar el render de fila/badge de estado con datos reales.
- **Bugs menores encontrados y corregidos de paso**: `tpv.title` mezclaba catalán/castellano en su valor `ca` (`"TPV — Venda en tienda"` → `"TPV — Venda a la botiga"`); la cabecera de estado en `vendes-web/page.jsx` usaba por error la clave `orders.tab.all`; un placeholder de email en `configuracio/page.jsx` (`botiga@exemple.com`) estaba fuera de `t()` sin traducir a los otros idiomas.
- `pytest`: 383 passed (sin cambios, esta fase es puramente de frontend + datos de seed).

**Fuera de alcance**: no se tocó ningún schema, endpoint ni modelo — Fase 6 es ortogonal al resto del plan Core/Vertical, solo dependía de que la infraestructura de i18n (`translations`, `useT()`) ya existiera.

---

## 16. Fase 4 Etapa A — completa (implementada, 2026-08-25)

Primer batch del rename DB-only a inglés (§6, punto 4): solo cambia el nombre de columna en Postgres, el atributo Python del modelo se queda igual (`mapped_column("nombre_ingles")`), así que `schemas.py`, routers, servicios, scripts y frontend no se tocan — el contrato JSON de la API es idéntico antes y después. Piloto en 3 tablas pequeñas y simétricas, elegidas por ser Core inequívoco y de bajo riesgo (§4.1: `Etiqueta`→`Tag`, `Seccio`→`Category`, tipos de IVA):

- `etiquetes`: `nom_ca`→`name_ca`, `nom_es`→`name_es`, `activa`→`active`, `posicio`→`position`.
- `seccions`: mismos 4 campos.
- `tipus_iva`: `nom`→`name`, `actiu`→`active`.

- **Solo columnas, no nombre de tabla**: `__tablename__` (`etiquetes`, `seccions`, `tipus_iva`) se deja sin tocar en esta etapa — cambiarlo también habría sido DB-only en sentido estricto, pero arrastra strings Python (`ForeignKey("etiquetes.id")`, `secondary="release_etiquetes"`) que están fuera del alcance mínimo pactado para Etapa A. Se revisita si hace falta, junto con el rename de la clase Python, en Etapa B.
- **`alembic revision --autogenerate` no vale para esto**: autogenerate compara metadata de SQLAlchemy contra el estado de la BD columna por columna: no tiene forma de inferir que `nom_ca`→`name_ca` es un rename y no "borra una y añade otra" — habría generado `DROP COLUMN` + `ADD COLUMN`, perdiendo los datos. La migración (`7c5f2b01749b`) está escrita a mano con `op.alter_column(..., new_column_name=...)`, que sí hace un `ALTER TABLE ... RENAME COLUMN` real.
- **Verificado**: `pytest` 383 passed sin tocar ningún test (confirma que efectivamente nada fuera de `models.py` dependía del nombre de columna); aplicada en dev con rebuild+restart de `api`/`web`; snapshot de datos antes/después idéntico en las 6 tenants reales (mismo `slug`/valores/orden, ahora bajo las columnas nuevas); smoke test de `GET /catalog/etiquetes` contra Postgres real confirma que el JSON de salida (`nom_ca`, `activa`, etc.) es exactamente el mismo que antes de la migración.
- **Efecto secundario cosmético, no funcional**: los índices creados por `index=True` en la migración original (p.ej. `ix_etiquetes_activa`) conservan su nombre antiguo tras el rename — Postgres no renombra el índice automáticamente al hacer `RENAME COLUMN`. El índice sigue funcionando correctamente (referencia la columna por posición interna, no por nombre); es solo un desajuste cosmético entre el nombre del índice y el de la columna que indexa. Puede limpiarse en una pasada posterior si molesta, no es bloqueante.

Tras el piloto, se extendió el mismo patrón a **todas** las tablas Core restantes, en dos batches adicionales:

### Batch 2 — resto de tablas Core sin SQL en crudo (migración `99ad9189db2a`)

184 renames de columna sobre 34 tablas: `users`, `addresses`, `releases` (solo campos core; `artista`/`sello`/etc. viven en `release_records`, vertical, fuera de alcance), `release_images`, `cart_items`, `orders`, `payments`, `proveedores`, `compras`, `comandas`, `comanda_items`, `historial_compres`, `solicitudes_compra`, `solicitud_compra_items`, `peticiones_cliente`, `caja_sessions`, `caja_movimientos`, `devolucions_venta`, `devolucions_compra`, `marges_config`, `trams_enviament`, `tipus_iva` (columnas que se habían quedado fuera del piloto: `percentatge`, `es_rebu`, `per_defecte_nou`, `per_defecte_segona_ma`), `configuracio_botiga`, `despeses`, `comptes_bancaris`, `moviments_bancaris`, `periodes_comptables`, `caixa_diaria`, `pagines`, `posts`, `events`, `newsletter_campaigns`, `newsletter_sends`, `stock_holds`.

- **Bug real encontrado por `pytest`, no por revisión manual**: `Proveedor.__table_args__ = (UniqueConstraint("tenant_id", "nombre"),)` y el equivalente en `Comanda` (`"num_comanda"`) referencian el nombre de columna como **string**, no como atributo Python — a diferencia de `Proveedor.nombre` en el resto del código (que sigue funcionando vía el atributo sin cambios), `UniqueConstraint`/`Index`/`CheckConstraint` con argumentos string usan el nombre de columna tal como vive en la BD. Al renombrar `nombre`→`name` sin actualizar el `UniqueConstraint`, `pytest` falló inmediatamente al montar el esquema SQLite de test (`ConstraintColumnNotFoundError: no column named 'nombre'`) — exactamente la red de seguridad que se esperaba de la suite verde. Corregido actualizando los `__table_args__` de `proveedores`, `comandas`, `periodes_comptables` (`mes`→`month`) y `caixa_diaria` (`data`→`date`) a los nombres nuevos.
- Antes de tocar nada se hizo un grep de todo `app/` buscando `text("...")` con cualquiera de los nombres de columna a renombrar, para detectar SQL en crudo que un rename silencioso podría romper sin que ningún test lo note (SQLite/Postgres no comprueban en tiempo de import que un `text()` referencie una columna real). Solo aparecieron los dos partial index de `order_items`/`ventas_externas` (ver Batch 3) — nada más en todo el backend depende de un nombre de columna Core como string.
- Verificado igual que el piloto: `pytest` 383 passed; aplicada en dev; snapshot de `orders`/`users` antes/después idéntico; smoke test de `GET /catalog/etiquetes`, `GET /config/public`, `GET /pagines`, `GET /events` contra Postgres real.

### Batch 3 — `items`, `order_items`, `ventas_externas` (migración `b45384f7d18d`)

Las tres tablas que CLAUDE.md señala como "la pieza más delicada" del sistema (reserva atómica de stock vía `UPDATE ... WHERE` condicionado, nunca `SELECT`+`UPDATE`), dejadas aparte a propósito por tener SQL en crudo que referencia nombres de columna como texto:

- `items` tiene dos `CheckConstraint` con la condición como string (`"cantidad >= 0"`, `"cantidad_reservada >= 0 AND cantidad_reservada <= cantidad"`).
- `order_items` y `ventas_externas` tienen sendos índices únicos parciales (`ix_order_items_item_id_unico_segona_ma`, `ix_ventas_externas_item_id_unico_segona_ma`) con `postgresql_where=text("condicion = 'segona_ma'")`.

Ni el `CheckConstraint` ni el `Index` se pueden dejar apuntando al nombre antiguo mientras se renombra la columna (Postgres no permite `RENAME COLUMN` de una columna que una constraint/índice referencia por nombre en una expresión) — la migración primero hace `DROP CONSTRAINT`/`DROP INDEX` de los cuatro, luego los 15 `RENAME COLUMN` (`precio`→`price`, `condicion`→`condition`, `cantidad`→`quantity`, `cantidad_reservada`→`reserved_quantity` en `items`; equivalentes en `order_items`/`ventas_externas`, más `canal`→`channel`, `metodo_pago`→`payment_method`, `descripcion`→`description`, etc.), y por último recrea las cuatro constraints/índices con la condición ya en inglés (`"quantity >= 0"`, `"condition = 'segona_ma'"`).

- **Bug atrapado antes de aplicar, no en producción**: el primer borrador de la migración usaba `op.f("condition = 'segona_ma'")` para el `postgresql_where` — `op.f()` es para aplicar convenciones de nombrado a nombres de constraint/índice, no para construir una expresión SQL; habría fallado al ejecutar. Corregido a `sqlalchemy.text(...)`, el mismo helper que ya usa `models.py`.
- `services/reservations.py` (el módulo que hace los UPDATE atómicos) usa exclusivamente expresiones ORM a nivel de clase (`Item.cantidad_reservada`, `.values(cantidad_reservada=Item.cantidad_reservada - hold.cantidad)`) — cero SQL en crudo, así que sigue funcionando sin ningún cambio, confirmado por `pytest` (incluye `test_checkout_nou.py`, `test_erp.py`) y por un smoke test real: `POST /cart/items` + `POST /checkout/start` contra Postgres real en dev incrementó `items.reserved_quantity` y creó una fila en `stock_holds` correctamente; estado de prueba revertido a mano tras verificar (no se creó ningún `Order`, solo la reserva).
- Nombres de constraint/índice verificados contra la BD real antes de escribir la migración (`\d items`, `\d order_items`) para asegurar que los `DROP CONSTRAINT`/`DROP INDEX` apuntaban exactamente a los nombres existentes.
- `pytest`: 383 passed.

### Resumen y alcance

Entre el piloto y los dos batches: **~220 columnas renombradas en 37 tablas Core**, 3 migraciones (`7c5f2b01749b`, `99ad9189db2a`, `b45384f7d18d`), todas aplicadas y verificadas en dev. En ningún momento se tocó `schemas.py`, ningún router, ningún servicio, ningún script ni una sola línea de frontend — el contrato JSON de la API es idéntico byte a byte al de antes de empezar (confirmado con `GET /catalog` real: sigue devolviendo `precio`/`condicion`/`cantidad`/`properament`/etc., los nombres Python, no los nombres de columna nuevos).

**Deliberadamente fuera de esta fase**: tablas de extensión de vertical (`release_records`, `release_floristeria`, `record_stock_details`, `spotify_connections`, `pes_format`, toda la familia `configuracio_subscripcio`/`subscripcions`/`cobraments_subscripcio`/`subscripcio_assignacions`) — Etapa A es solo Core, per §4.1 vs §4.2/§4.3; nombres de tabla (`__tablename__`) — solo columnas, ver piloto; nombres de tipo Enum de Postgres (`condicion_item`, `order_status`, etc.) — se quedan en catalán/castellano, cosmético, no forma parte del contrato JSON; valores de enum (`disponible`/`reservado`/`vendido`, `discogs`/`subscripcio` en `OrderOrigen`) — eso es Fase 5, aparcada (§14).

**Pendiente**: aplicar las tres migraciones en producción cuando toque desplegar (no se ha tocado ninguna base de datos de producción). El siguiente paso natural es Fase 4 Etapa B (rename de atributos Python/Pydantic/frontend) — ver §14, requiere confirmación explícita del orden de dominios antes de empezar.

---

## 17. Auditoría de acoplamiento oculto en Core (2026-08-29)

**Estado: hallazgos verificados por grep/lectura directa de código, nada aplicado todavía.** Antes de planificar arquetipos de vertical para ~12-15 negocios distintos (§18), se auditó si quedaba acoplamiento a "discos" en zonas que el diagnóstico de §1 (2026-08-09) daba por genéricas, más allá de los campos de catálogo ya extraídos en Fase 2.

**Nota de estructura**: desde que se escribió §1, `models.py`/`routers/`/`schemas.py` pasaron a ser paquetes (`api/app/models/catalog.py`, `models/compras.py`, `models/stock.py`, `routers/erp/comandas.py`, etc.). Las rutas citadas a partir de aquí usan la estructura nueva; las de secciones anteriores pueden estar desactualizadas.

### 17.1 Flujo de compras/ERP

- **Bug real, no solo de nomenclatura — arreglado (Fase A, 2026-08-29)**: `api/app/services/enviament.py` (`pes_total_g`, cálculo de peso para tarifa de envío, usado en CUALQUIER checkout) caía a `PesFormat` (peso por formato de vinilo) y, si no había match, a `DEFAULT_PES_G = 350` con el comentario `"LP senzill amb funda"`. Confirmado en dev (no hipotético): el release `florqa` (floristry) tiene `weight_g` vacío y estaba usando en silencio el peso de un vinilo. Fix aplicado de forma aditiva: si `Release.formato` está informado (vertical records), comportamiento idéntico a antes (cero riesgo para discos); si no (cualquier otro vertical), se exige `weight_g` explícito y se lanza `PesNoConfigurat` → 422 en el checkout en vez de cobrar un envío incorrecto en silencio. Tests nuevos en `test_enviament.py`. 454 tests passed (1 fallo preexistente en `test_superadmin_tenant_features.py`, no relacionado, verificado con `git stash`).
- **Fase C — resuelto de forma distinta a lo planeado (2026-08-29)**: al investigar `HistorialCompra`/`SolicitudCompraLinea` para el fix aditivo previsto (§20 no aplica aquí), se encontró que el problema real no eran las columnas sueltas sino que `routers/erp/historial_compres.py` (el buscador "¿qué proveedor me trajo esto antes?") hace JOIN **a nivel de clase** contra `RecordProduct.artista`/`.sello`/`.formato` — un heurístico de recomendación por artista/sello que es inherentemente de discos (para café el criterio sería productor/origen, no "artista"), no una cuestión de nomenclatura. Decisión (con el usuario): **excluir la función para cualquier vertical que no sea `records`** en vez de generalizarla — `resum_historial_compres`/`buscar_historial_compres` devuelven `[]` si `request.state.tenant.vertical_id != "records"`, gateado por vertical (no por `tenant_features`, porque depende de si existe `RecordProduct`, no de una preferencia de tenant). El matching por `release_id` exacto (genérico, señal fuerte) se sacrifica también para no-records con este approach — aceptado como coste de la simplicidad. De paso, se relajó `SolicitudCompraLineaIn.check_producte` (antes `check_disco`): ya no exige `artist` además de `release_id`/`title` para una línea sin catálogo — `title` (Core, genérico) basta; `artist`/`label`/`format` quedan como detalle opcional. Sin migración: todas las columnas ya eran nullable. Tests nuevos en `test_historial_compres.py`/`test_solicitudes_compra.py`. 456 tests passed (mismo fallo preexistente y no relacionado en `test_superadmin_tenant_features.py`).
- **Corregido (Fase B, 2026-08-29)**: `api/app/routers/erp/comandas.py::recibir_comanda` (línea ~333) construía un mensaje de error 422 con `linea.release.artista` — para un vertical sin discos habría mostrado "None - <título>". Cambiado a usar solo `.title` (Core genérico). Nota de precisión sobre el hallazgo original: las otras referencias a `.artista`/`.titulo` en este archivo (`_resolve_release_by_discogs_id` y `resolver_comanda_csv`, ambas explícitamente del flujo de importación CSV de Discogs) son legítimamente específicas de vertical records, no un leak — se dejan tal cual.

### 17.2 Copys de admin — más profundo de lo que decía el diagnóstico original

Fase 6 (2026-08-25) tradujo el **idioma** de 8 pantallas, no eliminó el **vocabulario de vertical** — son problemas distintos:

- `web/app/admin/compras/page.jsx` está construido literalmente como pantalla de compra de discos: la búsqueda de Discogs (`discogsEnabled`, `pickDiscogs`, `resolveRelease`) está cableada dentro del flujo genérico de compra, no detrás de un submódulo de catálogo; los campos de grading (`estado_disco`/`estado_funda`) son estado de primera clase de la línea de compra. `seed_translations.py` tiene ~20 claves con texto literal "disc/discos/record" (`purchases.grading.disc`, `purchases.request.pending_records`, `purchases.modal.records`...).
- `admin/tpv/page.jsx`: mismo patrón — `estado_disco` se renderiza directo en las líneas de venta, el canal `discogs` está hardcodeado.
- `admin/configuracio/page.jsx`: `config.vat.hint` habla de "discos nous"/"2a mà REBU" como si fuera universal; `config.shop.record_club` como etiqueta genérica de configuración de tienda.
- `admin/resultat/page.jsx`: `resultat.channel.discogs`/`resultat.cogs_extern` ("Cost vendes TPV / Discogs") integrados en la pantalla de resultado contable genérica.

### 17.3 Resto de Core

Grep global de `discogs`/`spotify`/`vinil`/`Release`/`RecordProduct` fuera de los módulos ya reconocidos como vertical (`services/discogs.py`, `discogs_sync.py`, `services/spotify.py`, club de suscripción): sin hallazgos nuevos, coincide con el diagnóstico existente.

### 17.4 Consecuencia para el plan de arquetipos

Construir un vertical nuevo (café, flores...) hoy heredaría estos bugs/acoplamientos, porque compras/TPV/envío/configuración/resultado — que se asumían Core puro — tienen ramas de comportamiento y copy pensadas solo para discos. Antes de escalar a 10-15 verticales hace falta una fase de saneamiento de estas pantallas (mismo patrón que Fase 3 aplicó al catálogo: feature-gate por `tenant_features`/vertical en vez de mostrar siempre los campos de discos, y sustituir el fallback de peso por un valor genérico o un campo obligatorio).

---

## 18. Plan de arquetipos de vertical para catálogo (propuesta, 2026-08-29)

**Estado: propuesta, no aplicada.** Verticales previstas: discos, café, flores, vino, queso, cerveza artesana, ropa, libros, juguetes, cosmética, plantas, alimentación (~12). Construir una tabla de extensión 1:1 por vertical (patrón `RecordProduct`/`FloristryProduct`) daría 12 tablas y 12 formularios de admin casi todos redundantes entre sí. Agrupando por qué campos comparten de verdad, salen 4-5 arquetipos:

| Arquetipo | Verticales | Campos compartidos propuestos | Qué varía dentro del arquetipo |
|---|---|---|---|
| **Media/catálogo** | Discos, Libros | autor/creador, editorial/sello, género, formato, id de catálogo externo, sinopsis | Discos necesita además `discogs_release_id`/`spotify_album_id` (libros no) — tablas separadas generadas de la misma plantilla, no compartidas físicamente (el matching externo de cada una es distinto) |
| **Consumible / alimentación-bebida** | Café, Vino, Queso, Cerveza artesana, Alimentación | productor/origen/denominación, peso o volumen, fecha de caducidad/consumo preferente, alérgenos/ingredientes | Un único campo `specs JSONB` acotado para el resto (grado alcohólico en vino/cerveza, tueste en café, curación en queso) — válvula de escape puntual, no sistema dinámico general |
| **Botánico / cuidado** | Flores, Plantas | color, necesidades de luz/riego, durabilidad, interior/exterior | Prácticamente idéntico entre las dos — tabla compartida real, no solo plantilla |
| **Retail simple** | Juguetes, Cosmética (si es solo accesorio sin control de ingredientes) | marca, rango de edad/target, dimensiones — mayormente ya cubierto por `Product` Core | Puede que no necesite tabla de extensión propia |
| **Variante talla/color** | Ropa | — | Extiende `StockItem`, no `Product` (una fila de stock por combinación talla×color, análogo a `RecordStockDetail`) — pendiente de confirmar el modelo de venta |

Puntos abiertos antes de escribir modelos/migraciones:

1. **Ropa**: ¿stock agregado por combinación talla/color (como discos "nou") o prenda individual con trazabilidad (como segona_ma)? Determina si `ClothingStockDetail` extiende `StockItem` con `cantidad` o necesita algo más parecido al modelo de ejemplar único.
2. **Cosmética**: ¿se controlan ingredientes/PAO de verdad, o es "producto con precio y stock"? Decide si cae en Consumible o en Retail simple.
3. **Orden recomendado**: primero el saneamiento de §17 (bug de peso de envío, feature-gating de compras/TPV/configuración/resultado por vertical) — construir arquetipos nuevos sobre un Core que todavía asume discos multiplicaría el problema en vez de resolverlo. Después, arquetipos de menor a mayor riesgo: Botánico y Retail simple primero (más simples, sirven de piloto), luego Consumible (el más grande, 5 verticales), luego Media/catálogo (ya tiene precedente exacto en discos) y Variante (el único que toca `StockItem`, más delicado por la reserva atómica de stock).

---

## 19. Saneamiento de compras/TPV/configuració — diseño refinado (propuesta, 2026-08-29)

Sustituye el planteamiento inicial de §17.4 ("feature-gate con condicionales sobre las pantallas existentes") por un mecanismo genérico, más barato de mantener a medida que se añadan verticales. También aplica el criterio de §17.1-17.2 de arreglar de forma **aditiva** lo que es Core compartido (peso de envío, `recibir_comanda`, `HistorialCompra`/`SolicitudCompraLinea`) sin tocar el comportamiento actual de `records`.

**Fase D — implementada con alcance acotado (2026-08-29).** Al investigar el frontend antes de tocar nada, dos hallazgos del diagnóstico original resultaron ser ya falsos (verificado por lectura de código, no asumido): el buscador de Discogs en `admin/compras` ya estaba correctamente gateado por `useDiscogsEnabled()` (lee `tenant_features`), y el filtro de canal `discogs` en `admin/tpv` ya estaba gateado por `shopConfig?.discogs_habilitat` — ninguno de los dos necesitó cambios. Lo que sí era un bloqueo real: el picker de ítems del modal "Compra particular" (`CompraParticularModal`, `NovaComandaModal`) exigía `artista` **y** `título` para poder añadir cualquier línea manual, incluso con Discogs desactivado — para una vertical sin discos esto bloqueaba completamente la compra a particulares. Decisión (con el usuario, alcance mínimo): desbloquear sin rehacer el picker completo (la opción de reconstruirlo como buscador genérico de §19.1 se descartó por ahora, es un proyecto de frontend mayor).

- `web/app/admin/compras/page.jsx`: las 3 funciones `addManual`/botones "Afegir" que exigían `artista.trim() && titulo.trim()` ahora solo exigen `titulo.trim()` (ya validado como seguro en el backend: `POST /admin/releases/check-duplicate` con `artista` vacío simplemente omite esa condición de búsqueda, no falla). Los selects de grading (`estado_disco`/`estado_funda`) se ocultan tras `vertical === 'records'` (hook `useTenantVertical`) en los dos sitios donde se renderizan.
- `web/app/admin/tpv/page.jsx`: sin cambios — ya seguro (grading solo se muestra si tiene valor, canal Discogs ya gateado).
- `web/app/admin/configuracio/page.jsx`: el panel `PesFormatPanel` (pesos por formato de vinilo, pestaña "Enviaments") y el toggle "Club del disc (subscripció)" (pestaña "Botiga") ahora solo se renderizan si `vertical === 'records'` — ambos dependen de mecanismos (`PesFormat`, el club de discos concreto) que hoy son 100% de discos, mostrarlos a otra vertical sería activar un interruptor que no hace nada. El hint de IVA (`config.vat.hint`) se generalizó de "vendes de discos nous" a "vendes de productes nous" (JSX + `seed_translations.py`, reseedado en los 6 tenants reales).
- **Verificado en el navegador contra el tenant real `florqa` (floristry)**, no solo leído: login vía magic link, promovido a admin por SQL. Confirmado que "Compra particular" acepta añadir una línea con solo título (sin grading mostrado), que "Nova sol·licitud" ya aceptaba título-solo de antes (round-trip completo probado: creada una solicitud real "Ram de proves" en `florqa`, queda en dev como dato de prueba), que la pestaña "Cerca proveïdor" muestra "Cap coincidència" en vez de intentar nada (confirma la exclusión de Fase C en producción, no solo en tests), y que en `configuracio` ya no aparecen ni el panel de pesos por formato ni el toggle de club del disc.
- Requirió reconstruir el contenedor `web` (no usa hot-reload, `next start` sobre imagen construida) — confirmado con el usuario antes de hacerlo, sin tocar la base de datos ni migraciones.
- `pytest`: 456 passed (mismo fallo preexistente y no relacionado).

**Hallazgo del storefront público — corregido (2026-08-29)**: durante la verificación de Fase D se observó que `/ca/compte` y su footer mostraban "Connecta Spotify" y un enlace "Discogs" para `florqa` (floristry). Causa: `Settings.spotify_enabled` (ver §13) es un kill switch **global** de plataforma, sin ningún check de vertical — a diferencia de Discogs, que ya usa `tenant_features` (por tenant). Fix:

- `routers/spotify.py`: `require_spotify_enabled` (gate del router protegido: `/init`, `/status`, `/library`...) y el endpoint público `GET /auth/spotify/enabled` ahora exigen además `tenant.vertical_id == "records"` — Spotify compara artistas escuchados contra el catálogo musical, no tiene sentido fuera de discos pase lo que pase con el flag global. Detalle no obvio: `require_spotify_enabled` necesita su propio `Depends(get_db)` (no basta con que otro parámetro del endpoint ya lo traiga) — es una dependencia de router, se ejecuta antes que los parámetros propios del endpoint, y `request.state.tenant` solo lo resuelve `get_db` como efecto secundario.
- Frontend: cero cambios adicionales — `useSpotifyEnabled`/`CompteLayoutClient` (ítem "Artistes" del menú) ya leían ese mismo endpoint, así que se ocultan solos. `StorefrontFooter.jsx`: el enlace a Discogs ahora depende de `config.vertical === 'records'` (ya disponible en la respuesta de `/config/public`).
- `AboutStripBlock.jsx` ya gateaba esto correctamente (`isVinils && config?.discogs_habilitat`) — no tocado.
- Tests nuevos en `test_spotify.py`. Verificado también en el navegador contra `florqa`: sin sección Spotify, sin "Artistes" en el menú de cuenta, sin enlace Discogs en el footer.
- `pytest`: 458 passed (mismo fallo preexistente sin relación).

**Nota**: se interpretó "solo para recordstore" como "solo para la vertical `records`", no como el tenant `recordstore` en concreto — consistente con el resto de esta fase (gate por vertical, no por tenant) y con que las otras 4 tiendas reales (`tienda-a`, `tienda-b`, `tienda-b-verif`, `escaparate`) también son vertical `records`.

**Deliberadamente fuera de esta fase**: el rediseño completo del picker de ítems como buscador genérico por proveedor (§19.1 original) — la opción de "rehacer el picker ahora" se ofreció y se descartó explícitamente a favor del fix mínimo. §19.2 (formulario de condición declarado por vertical) tampoco se construyó como mecanismo genérico — con una sola vertical (`records`) usando grading hoy, un gate directo por vertical es más simple y no hay nada que generalizar todavía; se revisita si aparece una segunda vertical con venta de segunda mano.

### 19.1 Buscador de referencias por proveedor (compras)

En vez de que `admin/compras` tenga el buscador de Discogs cableado a mano, cada vertical declara un `catalog_provider` opcional (ver §20): `discogs` para discos, potencialmente `openlibrary`/ISBN para libros, `null` para el resto. Backend: una interfaz común

```
class CatalogSearchProvider:
    def search(query: str) -> list[CatalogSearchResult]
    def enrich(external_id: str) -> dict  # campos ya mapeados a la extensión del vertical
```

con una implementación por proveedor (`DiscogsProvider` envuelve `services/discogs.py` existente, sin reescribirlo). Un único endpoint genérico `GET /admin/catalog-providers/search?q=...` resuelve internamente qué proveedor usar según el vertical del tenant (campo oculto si no hay ninguno). Frontend: un único componente de búsqueda en `admin/compras`, visible solo si el vertical tiene proveedor asignado; si no, solo queda el alta manual — ya es requisito existente de CLAUDE.md, no una excepción nueva.

### 19.2 Campos de condición/grading declarados por vertical (compras + TPV)

El grading (`estado_disco`/`estado_funda`) no se ata a "vertical == records" sino a si la extensión de `StockItem` de ese vertical declara campos de condición. Se generaliza el mismo mecanismo que ya usa `RecordStockDetail`: cualquier vertical con venta de segunda mano tiene su propia extensión de `StockItem` con sus propios campos de condición (discos: `estado_disco`/`estado_funda`; una futura vertical de ropa de segunda mano: su propia escala). Un único formulario genérico en `admin/compras` y `admin/tpv` renderiza "los campos de condición que declare la extensión de esta vertical, si los hay" — mismo principio que el buscador de referencias, sin lista de casos especiales por vertical.

Esto unifica con el plan de arquetipos (§18): el mismo mecanismo de "renderizar los campos que la extensión de este vertical declare" sirve tanto para el alta de catálogo como para compras/TPV — un solo renderer genérico dirigido por lo que cada vertical declara, no tres implementaciones distintas.

### 19.3 Configuració

Dos cambios independientes:
- **Generalizar copy** que hoy nombra discos aunque el concepto es genérico (el hint de IVA/REBU aplica a cualquier vertical con segunda mano, no solo discos).
- **Ocultar bloques según `tenant_features`** (p.ej. no mostrar "club de suscripción" si `subscriptions` no está activo para ese tenant) — la infraestructura (`tenant_features`) ya existe, solo falta que esta pantalla la consulte.

### 19.4 Resultat / contabilidad — aparcado

Se descarta meterlo en este saneamiento. Es una funcionalidad nueva (afecta IVA, márgenes, caja, movimientos bancarios — coste económico directo si hay un error), no un fix de acoplamiento. Queda pendiente para una sesión de diseño propia, con el mismo protocolo que ya usa el proyecto para cambios de modelo ERP: proponer el modelo, discutirlo, no migrar hasta aprobarlo.

---

## 20. Gestión de verticales en superadmin — ampliación del registro (propuesta, 2026-08-29)

Hoy (§5/§9, Fase 1) el registro de verticals solo guarda identidad (`id`, nombres i18n, `active`). Para soportar el mecanismo de §19 sin volver a tocar código en cada vertical nueva, se amplía:

```
verticals
  id                  string PK   -- ya existe
  name_ca/es/en       string      -- ya existe
  active              bool        -- ya existe
  catalog_provider    string null -- "discogs" | "openlibrary" | null — qué proveedor de búsqueda de referencias usa (§19.1)
  product_archetype   string      -- "record" | "consumable" | "botanical" | "retail_simple" | "apparel_variant" (§18) — qué tabla de extensión de Product/StockItem usa esta vertical
  default_features    JSON        -- {"discogs_sync": true, "subscriptions": false, ...} — qué tenant_features se siembran al crear un tenant de esta vertical (sustituye el mapeo hardcodeado que menciona §9)
```

Puntos de diseño:

- **`catalog_provider` y `product_archetype` no son texto libre**: se validan contra un registro en código de lo que hay realmente implementado (un `Literal`/enum de providers y de archetypes con código real detrás). Superadmin elige entre las opciones ya construidas, no inventa una combinación sin tabla/proveedor real — igual que hoy `POST /superadmin/tenants` valida contra `verticals.active` en vez de aceptar cualquier string.
- **`product_archetype` es prácticamente fijo tras la creación**: cambiarlo implicaría migrar datos de una tabla de extensión a otra, así que en la práctica lo fija quien da de alta la vertical en código (junto con la migración de su tabla de extensión); superadmin lo ve pero no lo cambia una vez hay datos.
- **`catalog_provider` y `default_features` sí son editables en caliente**, sin redeploy — es el valor real de esta ampliación: activar/desactivar un proveedor o ajustar qué features trae una vertical por defecto sin tocar código.
- **Las credenciales de API (token de Discogs, etc.) NO viven en `verticals`, siguen en `tenant_features.config`** (Fase 7, ya existe): el proveedor es una propiedad de la vertical (todas las tiendas de discos usan Discogs), pero el token/credencial es de cada tenant (dos tiendas de discos pueden tener cuentas Discogs distintas). Mezclar esto en `verticals` rompería el aislamiento multi-tenant.
- Endpoints: `GET/POST/PUT /superadmin/verticals` (hoy solo `GET`, §10) se amplía a CRUD completo con estas validaciones.

---

## 21. §20 — implementado, con seed de las 12 verticales previstas (2026-08-29)

**Nota de corrección sobre §10**: el CRUD completo (`GET/POST/PATCH /superadmin/verticals` + pantalla `superadmin/verticals`) ya existía antes de esta sesión — §10 decía "hoy solo GET", desactualizado (mismo tipo de deriva ya detectado antes con Fase 4 Etapa B). Solo faltaba la ampliación con `catalog_provider`/`product_archetype`/`default_features` descrita arriba, que es lo que se implementa aquí.

- **Modelo** (`models/platform.py::Vertical`): 3 columnas nuevas, todas nullable/con default, sin tocar nada existente. `app/verticals_registry.py` (nuevo módulo) centraliza qué hay realmente implementado: `CATALOG_PROVIDERS = ["discogs"]`, `PRODUCT_ARCHETYPES_IMPLEMENTED = ["record", "floristry"]` + `PRODUCT_ARCHETYPES_PLANNED` (los 5 arquetipos de §18, sin tabla propia todavía), `TENANT_FEATURE_KEYS` (las 5 claves que el código realmente consulta hoy — `discogs_sync`, `subscriptions`, `catalog_browse_mode`, `catalog_format_filter`, `catalog_genre_filter`; **Spotify no es una de ellas**, sigue siendo kill switch global + vertical, ver §13/Spotify más abajo).
- **Validación**: `VerticalCreateIn`/`VerticalUpdateIn` rechazan (422) cualquier `catalog_provider`/`product_archetype`/clave de `default_features` que no esté en el registro — impide que superadmin invente una combinación sin código real detrás.
- **Migración** `0a8e9cde93d3`: añade las 3 columnas + siembra las 10 verticales nuevas discutidas con el usuario (café, vino, queso, cerveza artesana, alimentación → arquetipo `consumable`; plantas → `botanical`; juguetes, cosmética → `retail_simple`; ropa → `apparel_variant`; libros → `media_catalog`), todas con **`active=False`** (registradas pero no ofrecidas todavía en el alta de tenant, porque ninguna tiene tabla de extensión real — evita que alguien cree un tenant esperando campos específicos que no existen). `records`/`floristry` (ya existentes) se rellenan con sus valores reales (`records`: `catalog_provider="discogs"`, `product_archetype="record"`, `default_features` con las 5 claves activas; `floristry`: `product_archetype="floristry"`, sin proveedor). **Aplicada en dev** (confirmado con el usuario antes de `alembic upgrade head`; el `Dockerfile` ya corre la migración automáticamente en el arranque del contenedor `api`).
- **Frontend** (`superadmin/verticals/page.jsx`): añadidos selects de proveedor/arquetipo y checkboxes de features (con las mismas 5 claves del registro, no texto libre), más 2 columnas nuevas en la tabla. Verificado en el navegador contra dev: las 12 verticales se listan con sus datos correctos, el diálogo de edición/creación funciona (confirmado que los checkboxes son independientes entre sí pese a un estilo visual circular preexistente del componente `Checkbox` compartido, no introducido por este cambio).
- **Deliberadamente fuera de esta fase**: `POST /superadmin/tenants` todavía no siembra `tenant_features` a partir de `default_features` (el propio §20 ya lo marcaba como un paso posterior); ningún código de negocio consulta todavía `product_archetype`/`catalog_provider` para decidir comportamiento — los checks de §19 (Spotify, grading, PesFormat, club del disc) siguen siendo `vertical_id == "records"` directo en código, no leen el registro. Unificar ambas cosas (que el código consulte el registro en vez de hardcodear el vertical) queda pendiente para cuando haya un segundo caso real que lo justifique.
- `pytest`: 463 passed (mismo fallo preexistente y no relacionado en `test_superadmin_tenant_features.py`).
