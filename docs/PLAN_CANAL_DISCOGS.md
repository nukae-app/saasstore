# Plan: centro de control de ventas online (Discogs + web), la app como fuente de verdad

Versión 2 (2026-10-01). Sustituye a la v1 (propuesta de "Discogs como canal"). Lo ya hecho está en §1.

## 0. Visión

La sección de Discogs deja de ser "una herramienta de sincronización" y pasa a ser un **centro de
control de lo que se vende online**: ver el estado de todo, actuar sobre ello y dejar que lo rutinario
se sincronice solo. La BD de la app es la única fuente de stock y precios; Discogs es un **canal de
venta** (publicar/actualizar/retirar listings; recibir pedidos), como la web o el TPV.

Decisiones de producto (2026-10-01):
- **Los pedidos de Discogs siguen entrando en "Vendes web"** (`/admin/vendes-web`, `origin='discogs'`):
  esa pantalla es la lista **unificada** de pedidos online (web, Discogs, suscripción). El centro de
  control de Discogs no duplica pedidos: su pestaña "Comandes" es una vista filtrada de los mismos
  `orders`, más lo propio del canal (sincronización, conflictos, sin coincidencia).
- **Modelo genérico de canal, interfaz específica de Discogs.** Hoy solo Discogs; a futuro puede
  añadirse Amazon u otro portal sin rehacer tablas ni servicios.
- **Avisos configurables por el usuario** (qué eventos y por qué vía); nada impuesto (§6).
- Recargo de precio: **mismo precio que la web**. Publicación: **manual con revisión** al principio.
  `nou`: **un único listing "virtual de 1"** por línea.

---

## 1. Estado

### 1.1 Hecho y desplegado en nukaesaas (commits `e47eb06`, `1e5a888`)
- **Fase 0 de seguridad:** interruptor `discogs_habilitat` respetado en todos los flujos; token
  validado contra `/oauth/identity` al guardarlo; `GET /admin/secrets/discogs-account`; User-Agent real.
- **Modo "solo lectura"** (`discogs_solo_lectura`, Configuració): un `ReadOnlyToken` hace que el cliente
  HTTP rechace todo lo que no sea GET/HEAD (único punto de bloqueo); escribir en Discogs (publicar,
  borrar listing, marcar Shipped) queda inactivo y los endpoints manuales devuelven 409. Tokens
  `discogs_token_dev` / `discogs_token_prod` en el secret del tenant (`DISCOGS_TOKEN_ENV`, el compose
  local usa `dev`); el `discogs_token` antiguo queda como respaldo. Al guardar por primera vez el token
  prod el tenant arranca en solo lectura (si la adopción no está hecha).
- **Primera carga "Discogs manda"** (`services/discogs_inventory_sync.py`, compartido por el script
  `scripts/sync_discogs_inventory.py` y la pantalla `/admin/canals/discogs`): simulación sin guardar,
  informe por item (CSV), freno de seguridad (0 listings o >20 % a retirar), marca de adopción hecha
  por tenant, `--limit` sin retiradas. Corre en Celery (`tasks/discogs.py`); estado/progreso/informe en
  Redis (`services/discogs_jobs.py`). Aplicar exige una simulación de menos de 24 h.
- **Backup de solo lectura:** `scripts/backup_discogs_inventory.py` (JSON + CSV + manifest).

### 1.2 Hallazgos en producción (recordstore, 2026-10-01)
- Tokens `discogs_token_prod` y `discogs_token_dev` presentes; el efectivo autentica la cuenta
  `ultralocal` (pendiente de confirmar que es la cuenta vendedora de la tienda).
- `discogs_habilitat = True`, **`discogs_solo_lectura = False`** (el token se puso directamente en AWS,
  así que el modo automático no saltó), adopción no hecha.
- Catálogo web: `nou` disponible 2.731 líneas (2.431 con `codi_discogs`), `segona_ma` disponible 349
  (347 con `codi_discogs`); 3.223 releases, 3.206 con `discogs_release_id`. El único pedido existente
  es de origen `subscripcio`. No hay crontab en el EC2.

### 1.3 Lagunas que quedan (el motivo de las fases siguientes)
| Acción en la app | Efecto en Discogs hoy |
|---|---|
| Alta `segona_ma` / `nou` con `discogs_release_id` | Crea listing (`nou`: 1 listing Mint) |
| Venta web pagada | Borra listing (`nou`: re-publica si queda stock) |
| Pedido Discogs marcado `enviado` | Marca Shipped + tracking como mensaje |
| **Cambio de precio** | **No se propaga** |
| **Retirar item** | **No borra el listing** |
| **TPV de `segona_ma`** | **No borra el listing** |
| **Devolución `segona_ma` a disponible** | **No re-publica** |
| **Pull de pedidos** | **Manual** (botón en Vendes web); recorre todo el histórico; `sense_match` y errores no se ven |

Causa común: cada flujo llama a Discogs por su cuenta (event hooks dispersos); los que nadie cableó
quedan desfasados → riesgo de **doble venta**. Y todo es best-effort: los fallos solo dejan una línea
de log.

---

## 2. Verificación de la API de Discogs

Verificado el 2026-10-01 con repositorios de terceros, foros de Discogs y clientes de la API. **La
documentación oficial (`discogs.com/developers`) devolvió 403 a la herramienta de consulta**, así que
nada de esto se ha probado todavía contra la cuenta real: antes de implementar cada parte se comprueba
el endpoint (los GET directamente; las escrituras con un listing de prueba controlado).

| Capacidad | Endpoint | Verificación | Uso en el plan |
|---|---|---|---|
| Crear / leer / editar / borrar listing | `POST /marketplace/listings`, `GET/POST/DELETE /marketplace/listings/{id}` | Confirmado (campos: `release_id`, `condition`, `sleeve_condition`, `price`, `status` For Sale/Expired/Draft, `comments`, `allow_offers`, `external_id`, `location`, `weight`, `format_quantity`) | Reconciliador. **`external_id`** permite guardar el id del item de la app en el listing y casar sin ambigüedad |
| Inventario del vendedor | `GET /users/{username}/inventory` (filtro `status`, orden, paginación) | Confirmado; ya en uso | Sincronización / auditoría |
| Pedidos | `GET /marketplace/orders` (filtros `status`, `created_after`, `created_before`, `archived`, orden), `GET /marketplace/orders/{id}`, `POST /marketplace/orders/{id}` (`status`, `shipping`) | Confirmado | Pull **incremental** (hoy se recorre todo) |
| Mensajes de pedido | `GET/POST /marketplace/orders/{id}/messages` (el POST admite `status`) | Confirmado; coincide con `push_shipped_status` actual | Marcar Shipped + seguimiento |
| Comisión | `GET /marketplace/fee/{price}` | Confirmado | Mostrar margen neto / recargo futuro |
| Precios sugeridos | `GET /marketplace/price_suggestions/{release_id}` | Confirmado: requiere autenticación y **ajustes de vendedor completos**; precios por estado del disco en la moneda del vendedor; objeto vacío si no hay sugerencia | Pestaña Preus |
| Estadísticas de mercado | `GET /marketplace/stats/{release_id}` | Confirmado: nº a la venta, precio más bajo, si está bloqueado para venta | Pestaña Preus |
| Exportar inventario | `POST/GET /users/{username}/inventory/export`, `.../{id}`, `.../{id}/download` | Confirmado (asíncrono, CSV) | Backup/auditoría alternativos |
| Carga masiva CSV | `/inventory/upload/add`, `/change`, `/delete` | **Existe, contrato exacto sin verificar** | Opcional (publicación masiva inicial); no necesario en v1 |
| Límite de llamadas | 60/min autenticado, ventana móvil de 60 s; cabeceras `X-Discogs-Ratelimit`, `-Used`, `-Remaining`; 429 al superarlo | Confirmado | Limitador compartido y adaptativo (§5) |
| Webhooks de pedidos | — | **No confirmado**: los "triggers" de plataformas de integración parecen sondeo; no hay constancia de webhooks nativos | Diseño por **sondeo** (cada 5–10 min) |

Hallazgo adicional: los estados de pedido incluyen **"In Progress"**, que **no está** en
`DISCOGS_ORDER_STATUS_MAP` (`services/discogs_sync.py`): hoy esos pedidos se ignoran con un aviso en el
log. Hay que decidir su equivalente local y añadirlo (fase D). Fuente: documentación de la API según
terceros, por confirmar con un pedido real.

---

## 3. Principios

1. La app manda en stock y precio. Discogs es un canal con dos direcciones: **salida** (publicar) y
   **entrada** (pedidos). Tras la carga inicial, nunca se modifica stock/precio de la app desde el
   inventario de Discogs.
2. **Reconciliación declarativa, no eventos:** cualquier cambio marca el item como "sucio"; un único
   reconciliador calcula el estado deseado y lo aplica. Se cierran las lagunas por construcción.
3. **Todo fallo es visible:** estado y error por item, nunca solo en el log.
4. **Un único punto** decide si se escribe en Discogs (interruptor + token + modo solo lectura).
5. **El dashboard se alimenta de caché local** (patrón "API + caché local"); Discogs solo se consulta
   al sincronizar o al actuar. Así no se gasta el límite de 60/min al abrir una pantalla.
6. **Presupuesto de llamadas compartido** entre todos los trabajos del mismo token (limitador común,
   adaptado con `X-Discogs-Ratelimit-Remaining`).
7. Operaciones masivas: siempre con vista previa y como trabajo con progreso.
8. Todo lo que se escribe en Discogs queda **auditado** (quién, qué, cuándo, resultado).

---

## 4. Estructura del centro de control

Ruta: `/admin/canals/discogs` (hoy ya existe como pantalla de carga inicial; pasa a tener pestañas).

| Pestaña | Contenido |
|---|---|
| **Resum** | KPIs: listings publicados, valor del inventario publicado, pendientes de publicar, con error, discrepancias, pedidos de Discogs abiertos. Salud: cuenta, modo, última sincronización, trabajos en curso, uso del límite de llamadas. |
| **Listings** | Una tabla app↔Discogs por item con estado de canal (publicado, pendiente, error, retirado, sin vincular) y precio app vs Discogs. Acciones por fila y masivas: publicar, actualizar precio, retirar, vincular release. Las acciones de escritura requieren modo lectura/escritura. |
| **Sincronització** | Lo ya construido (simulación y aplicar de la carga inicial) + sincronización app→Discogs con vista previa y aplicar + historial de ejecuciones + programación automática. |
| **Comandes** | Vista de los pedidos de Discogs (los mismos `orders` de "Vendes web"): abiertos, pendientes de envío, marcar enviado con seguimiento. Además lo propio del canal: pedidos **sin coincidencia** con la app y conflictos (pedido de un item ya vendido/retirado). Enlace a "Vendes web" para la lista unificada. |
| **Preus** | Sugerencias de precio de Discogs por estado, precio más bajo del mercado, comisión, y simulación de un reprecio masivo antes de aplicarlo. |
| **Alertes** | Bandeja de excepciones con acción en cada una: listing huérfano en Discogs, vendido pero aún publicado, error al publicar, precio divergente, release sin vincular, pedido sin coincidencia. |
| **Configuració** | Token y cuenta, modo (solo lectura / lectura y escritura), publicación automática o manual, frecuencias, **avisos** (§6). |

"Vendes web" mantiene su botón de sincronizar pedidos de Discogs, pero apuntando al mismo servicio y
mostrando el resultado completo (creados, actualizados, sin coincidencia, errores).

En `admin/catalogo`: el botón "Sync Discogs" pasa a "Enriquir dades" (proveedor de catálogo, solo
datos del disco); los botones por item publicar/quitar se sustituyen por el estado del canal con
enlace al centro de control.

### Separación catálogo / canal
| | Proveedor de catálogo | Canal de venta |
|---|---|---|
| Nivel | Release | Item |
| Dirección | Solo lectura | Lectura y escritura |
| Qué hace | Buscar, enriquecer (carátula, tracklist, géneros, EAN, formato) | Publicar/actualizar/retirar listings, pedidos, seguimiento |
| Rutas | `/admin/catalog-provider/*` | `/admin/channels/discogs/*` |
| Servicio | `services/discogs.py` + `services/catalog_enrich.py` | `services/channels/discogs.py` |

Comparten solo `release.discogs_release_id`. `CATALOG_PROVIDERS` sigue siendo el punto de extensión
del catálogo; se añade un registro análogo `SALES_CHANNELS` para los canales.

---

## 5. Modelo de datos (genérico de canal)

- **`channel_listings`** (TenantScoped): `item_id`, `channel` (`discogs`, extensible), `external_id`
  (listing id; hoy `codi_discogs`), `status` (`pendent`, `publicat`, `error`, `retirat`),
  `published_price/condition/sleeve`, `desired_hash`, `last_synced_at`, `last_error`, `attempts`. UNIQUE
  parcial `(tenant_id, channel, external_id)` y `(tenant_id, channel, item_id)` activos.
  Migración: copiar `record_stock_details.codi_discogs` (~2.800 filas) → `channel_listings`
  (`publicat`); mantener `codi_discogs` como propiedad compatible hasta migrar todos los call sites.
- **`channel_events`** (registro de actividad): canal, acción, item/pedido, usuario o "sistema",
  petición resumida, resultado, error. Alimenta Alertes y la auditoría.
- **`channel_sync_runs`** (historial persistente; hoy el estado de trabajos vive en Redis y caduca a
  los 7 días): tipo, modo (simulación/aplicar), inicio/fin, resumen, informe.
- **`channel_settings`** por tenant y canal: modo, `publicacion_auto`, frecuencias, cursor del pull de
  pedidos, cuenta verificada. Recargo previsto en 0 (mismo precio que la web); se deja el campo.
- **Limitador de llamadas** en Redis por token (cubo de fichas) compartido por todos los trabajos y
  acciones manuales, ajustado con `X-Discogs-Ratelimit-Remaining`; ante 429, espera con retroceso.
- **Reconciliador:** `reconcile_item(item, canal)` calcula el estado deseado y compara con
  `channel_listings`. **Regla de publicación (decidida 2026-10-01): se publica mientras quede al menos
  una unidad real —no vendida ni retirada—, aunque esté reservada.** Una reserva (carrito, ~20 min) NO
  retira el listing: evita parpadeos y gasto del límite de llamadas; la ventana de doble venta se cubre
  detectándola en el pedido de Discogs y marcándola como conflicto en Alertes. Además hacen falta el
  canal activo, el release vinculado y, con `publicacion_auto` o aprobación manual; precio =
  `item.price`. Luego crea, actualiza o retira según el resultado. Se dispara al cambiar `quantity`, `price`, `status`, `condition` o el release
  (hook único en un servicio de stock, no en cada router); una tarea periódica reintenta errores y un
  barrido diario de solo comparación genera las alertas. Guarda el id del item en `external_id`.
  `nou`: "listing virtual de 1".
- **Pedidos entrantes:** sondeo programado (Celery beat, por tenant con canal activo, cada 5–10 min),
  **incremental** (`created_after` / orden por última actividad en vez de todo el histórico),
  idempotente por `discogs_order_id`, sin pisar estados locales terminales. Los conflictos y los pedidos
  sin coincidencia se registran como alerta accionable. Residual: la ventana entre una venta en
  Discogs y el siguiente sondeo puede provocar doble venta; se reduce con intervalo corto y la reserva
  atómica ya existente.

---

## 6. Avisos configurables

Cada usuario admin elige qué avisos recibe y por qué vía; por defecto **ninguno por correo** (todo se
ve siempre en Alertes). Catálogo de eventos previsto: nuevo pedido de Discogs, pedido sin coincidencia
o en conflicto, error al publicar/actualizar un listing, sincronización fallida o encallada,
discrepancias por encima de un umbral, límite de llamadas agotado. Vías: correo (ya existe
`services/emailer.py`) y, más adelante, notificación de la app nativa de admin. Tabla de preferencias
por usuario y evento; el envío cuelga de `channel_events`.

---

## 7. Primera ejecución (carga inicial) — implementada

Discogs manda **una sola vez**: crea items de listings que no existen, alinea precios y retira lo que
ya no está a la venta; después manda la app. Ver §1.1 para las salvaguardas y la pantalla. Orden
operativo: activar solo lectura → confirmar la cuenta (`ultralocal`) → backup → simulación → revisar
el informe → aplicar → desactivar solo lectura.

Importante: tras la carga, `channel_listings` se puebla desde los `codi_discogs` ya reconciliados y la
auditoría de discrepancias pasa a ser de solo lectura.

---

## 8. Decisiones

Resueltas (2026-10-01): recargo = mismo precio que la web; publicación = manual con revisión al
principio, automática más adelante; `nou` = un listing virtual de 1; avisos = configurables por
usuario; modelo genérico de canal; pedidos de Discogs siguen en "Vendes web".

Abiertas:
1. **Estado "In Progress" de pedidos** (§2): decidir equivalente local al ver un pedido real.
2. **Items sin `discogs_release_id`** (~17 releases): cola "pendiente de vincular" en Listings; no se
   publican hasta tener release.
3. **Hilo de segundo plano del enriquecimiento masivo de datos** (`/discogs/sync/images/start`):
   pasarlo a Celery como el resto.

---

## 9. Fases

- **A. Base — HECHA en código (2026-10-01), sin desplegar:**
  - Migración `c3d9a7e15f28`: `channel_listings`, `channel_events`, `channel_sync_runs` (con RLS como el
    resto de tablas por tenant; probada en Postgres real: cadena completa desde cero, copia de datos,
    subida/bajada/subida). Copia los `codi_discogs` actuales a `channel_listings` (`publicat`).
    **El `Dockerfile` ejecuta `alembic upgrade head` al arrancar la API: desplegar aplica la migración.**
  - `codi_discogs` sigue siendo la columna en uso; `channel_listings` es su reflejo con estado,
    reconstruido de forma idempotente por `services/channel_listings.py::backfill_discogs_listings`
    (se ejecuta al terminar una carga real). Cuando el reconciliador (fase C) escriba, se invierte.
  - Limitador de llamadas compartido por Redis y por token (`services/ratelimit.py`), enganchado en un
    único punto, el cliente HTTP: hueco de 1,1 s entre llamadas y pausa común ante 429 o poco margen
    (`X-Discogs-Ratelimit-Remaining`); sin Redis cae al espaciado local.
  - Registro de actividad (`services/channel_events.py`): publicar, retirar y marcar enviado dejan una
    fila con el resultado, también `skipped` en modo solo lectura; los endpoints manuales registran al
    usuario.
  - Historial persistente (`services/channel_runs.py`): cada simulación/aplicación queda en
    `channel_sync_runs` con su informe; el informe se lee de Redis y, si caducó, de la BD. Endpoint
    `GET /admin/discogs/inventory/runs` y panel "Historial" en la pantalla.
  - **Aplazado a B/C:** la tabla `channel_settings` (modo, publicación automática, frecuencias, cursor de
    pedidos): hoy nada la usaría; se crea con la primera pestaña que la necesite.
- **B. Dashboard — HECHA en código (2026-10-01), sin desplegar.** La pantalla `/admin/canals/discogs` pasa a
  tener 7 pestañas (Resum, Listings, Sincronització, Comandes, Preus, Alertes, Configuració), con aviso global
  del trabajo en curso y el número de alertas abiertas. Todo sale de la caché local
  (`routers/admin/channel_discogs.py`: `/overview`, `/listings`, `/settings`, `/events`). Tabla `channel_settings`
  (migración `d5b2f8c31a47`): publicación automática (apagada), retirada programada, recargo, sondeo de pedidos
  y su cursor. Menú: Catàleg › Discogs.
- **C. Reconciliador — HECHA en código, sin desplegar.** `services/channel_reconciler.py` (plan puro desde la
  caché local: publicar / actualizar precio / retirar / vincular release; regla de reservas del §5) y
  `services/channel_apply.py` (aplicador: retira → actualiza → publica; freno del 20 %; no escribe en solo
  lectura; cada operación deja evento y actualiza `channel_listings` y `codi_discogs`). Endpoints
  `POST /reconcile/preview` y `POST /reconcile` (trabajo en segundo plano). Tarea programada cada 15 min
  (`discogs.reconcile_scheduled`): retira sola lo que ya no se vende; publica y actualiza precios solo con la
  publicación automática activada; solo tras la carga inicial y en lectura/escritura; deja para revisión manual
  los listings en error (un 404 podría ser algo vendido en Discogs). `update_listing` nuevo.
  **Decisión de producto aplicada:** publicar por primera vez es manual por defecto (`publicacion_auto`); reponer
  un listing que ya se publicó antes (p. ej. tras una venta en Discogs) sigue siendo automático.
  **Reflejo automático `codi_discogs` → `channel_listings`** (hook de flush en `models/channels.py`): cualquier
  flujo que asigne o borre el código —alta, botón manual, reposición de `nou`, importaciones— deja el vínculo al
  día en la misma transacción. Sin él, el plan vería el item "sin listing" y propondría publicarlo otra vez
  (listing duplicado en Discogs). Si el código pasa de un item a otro (consolidación) el nuevo lo hereda.
- **D. Comandes — HECHA en código, sin desplegar.** Los pedidos de Discogs siguen siendo los mismos `orders` de
  "Vendes web" (la pestaña es una vista filtrada, con `GET /admin/orders?origen=discogs` y el cambio de estado
  existente). Sondeo **incremental** con cursor (`services/channel_orders.py`: `sort=last_activity`, se para al
  llegar a actividad anterior al cursor; la primera vez, 60 días), tarea cada 5 min con la frecuencia de cada
  tenant (`discogs.orders_poll`), solo tras la carga inicial y también en solo lectura. Estado **"In Progress"
  mapeado a `pagado`**. Incidencias (sin coincidencia, conflicto con lo que la app ya no tenía a la venta,
  estado desconocido) quedan en el registro de actividad y como alerta, una sola vez. El botón de "Vendes web"
  usa el mismo servicio y muestra el resultado completo.
- **E. Alertes + Avisos — HECHA en código, sin desplegar.** Migración `e6c3a9d42b58`: `channel_alerts`
  (deduplicadas por `ref_key`; resuelta que reaparece se reabre; descartada no) y `notification_prefs`.
  Alertas generadas por pedidos, fallos de listing, fallos de trabajos (programados o inesperados) y la
  **auditoría** (`services/channel_audit.py`, solo lectura de Discogs: listing huérfano, ya no está en Discogs,
  precio distinto; se cierran solas; cada noche y a demanda; solo tras la carga inicial). Avisos por correo
  elegidos por cada usuario admin (por defecto ninguno), agrupados: un correo por usuario y evento al terminar la
  operación. Eventos: nueva comanda, incidencia de comanda, error de listing, sincronización fallida,
  discrepancias de auditoría.
- **F. Preus — HECHA en código, sin desplegar.** `services/channel_pricing.py`: precios sugeridos y estadísticas
  de mercado por release y comisión (solo lectura, caché de 6 h; error claro si faltan los ajustes de vendedor en
  Discogs), simulación masiva en segundo plano (hasta 500 items; sugerencia para el estado de cada disco, factor,
  redondeo, umbral y recargo del canal) y aplicar (cambia el precio **en la app**, salta lo editado desde
  entonces; luego Listings propone propagarlo a Discogs).
- **G. Limpieza — PARCIAL.** Hecho: el botón del catálogo pasa a "Enriquir dades" (solo datos del disco) y los
  botones por item publicar/quitar se sustituyen por un enlace al centro de control; se retiran los manejadores
  muertos. **No hecho a propósito:** retirar `sync_stock_listing` y los endpoints
  `/admin/discogs/sync/items/{id}/push|listing` (los usan los flujos de venta, TPV, devoluciones y comandas, y
  ahora quedan consistentes gracias al reflejo y a la regla de publicación manual), ni eliminar la columna
  `codi_discogs` (la usa casi toda la app). Pendiente a futuro: mover esos flujos a "marcar el item como sucio" y
  quitar el código antiguo, y separar las rutas del catálogo (`/admin/catalog-provider/*`). Tampoco se ha tocado
  `scripts/run_discogs_sync.sh` (de recordshop).

- **H. Còpies de seguretat — HECHA en código (2026-10-01).** Sección en Configuració del canal Discogs
  (`BackupsPanel`). Migración `f7d4b1e83c69` (`channel_backups`, con RLS; el contenido va comprimido en la propia
  tabla). **Alcance: solo el catálogo del tenant, nunca toda la base de datos** (la BD es compartida entre tiendas y
  un restore de RDS crea una instancia nueva, así que eso queda para el snapshot manual de AWS).
  - **Punto de restauración del catálogo** (`services/catalog_backup.py`): foto de `releases`, `release_records`,
    `items`, `record_stock_details` y `channel_listings` del tenant. A demanda y **automática antes de la carga
    inicial real** (si no se puede guardar, la carga aborta), **antes de aplicar precios** y **antes de restaurar**
    (para deshacer la propia restauración). Las automáticas se podan a 15; las manuales no.
  - **Restaurar** calcula primero qué cambiaría (filas a recrear, a corregir con valor actual y de la copia, y a
    eliminar) y lo enseña. **No toca lo que ya no es seguro:** un item vendido, reservado, en un carrito o con
    pedidos, devoluciones, peticiones o asignaciones POSTERIORES a la copia se deja como está y se lista como
    conflicto (si no, volvería a ponerse a la venta algo ya vendido); tampoco se borra una release que aún tiene
    items. Se aplica en una sola transacción (o entra todo o nada), con Core SQL, y los códigos únicos que cambian
    de item no chocan. Probado en Postgres real con claves foráneas activas.
  - **Copia de Discogs** (`services/discogs_backup.py`, compartido con `scripts/backup_discogs_inventory.py`):
    trabajo en segundo plano que lee todo el inventario (y, a elección, el histórico de pedidos); descarga en
    JSON o CSV. Solo lectura de Discogs: funciona en modo solo lectura.
  - **Límite a tener presente:** restaurar no puede saber si alguien editó a mano un precio tras la copia; por eso
    la vista previa enseña cada cambio antes de confirmar.

Prioridad: A → B → C → D → E → F. Lo primero para operar es publicar, actualizar y retirar con
seguridad; los pedidos entrantes van justo después (cada venta de Discogs que no baje a la app es
riesgo de doble venta).

## 10. Riesgos y notas
- Límite de llamadas: 3.000 operaciones ≈ 55 min; las cargas masivas son trabajos largos con progreso
  y reanudación. El limitador común evita que dos trabajos se pisen.
- La migración de `codi_discogs` toca ~2.800 filas en producción: probar en dev y revisar el archivo
  de Alembic antes de aplicar.
- La simulación de la pantalla actual hace los cambios en una transacción que se deshace al final: un
  item que vaya a cambiar queda bloqueado si alguien lo edita justo entonces (ventana de minutos).
- Primera ejecución real de Celery en producción para estos trabajos: el primer dry-run también lo
  prueba.
- Tests: reconciliador con cliente de Discogs falso; `pytest` debe seguir en verde (SQLite); cubrir TPV
  `segona_ma`, retirar, devolución, cambio de precio y conflicto de pedido.
- No hay `discogs_solo_lectura` activo en producción a día de hoy (§1.2): activarlo antes de tocar
  nada más.
