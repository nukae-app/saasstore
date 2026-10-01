# Plan: Discogs como canal de venta (la app es la fuente de verdad)

Estado: **propuesta, nada implementado** (2026-10-01). Decisiones abiertas en §9.

Objetivo: la BD de la app es la única fuente de stock y precios. Discogs pasa a ser
un canal de venta más (como la web o el TPV): la app publica, actualiza y retira
listings; Discogs solo devuelve pedidos. Se separa además la integración de
**catálogo** (datos de disco) de la de **canal** (Marketplace).

---

## 1. Estado actual (qué hay hoy)

### 1.1 Código
- `services/discogs.py`: cliente HTTP (búsqueda, release, listing). Throttle 1,1 s (~55/min).
  `USER_AGENT` es un placeholder (`ultralocalrecords.example`).
- `services/discogs_sync.py`: push/delete de listings, `sync_stock_listing` ("listing virtual
  de 1" para `nou`), pull de pedidos, `push_shipped_status`, `enrich_release_from_discogs`.
- `routers/admin/discogs_sync.py`: `/admin/discogs/sync/*` — mezcla catálogo (enrich, imágenes,
  stats) y canal (push, delete, orders).
- `scripts/sync_discogs_inventory.py`: reconcilia BD con el inventario real. **Discogs manda en
  precio** (pisa el precio de la app). Solo lectura sobre Discogs.
- `scripts/sync_discogs_orders.py`: pull de pedidos por CLI. `scripts/run_discogs_sync.sh` es de
  **recordshop** (compose y secret distintos), no sirve para nukaesaas.
- Vínculo con el listing: `record_stock_details.codi_discogs` (UNIQUE por tenant). Sin estado,
  sin precio publicado, sin error.
- Token: secret de AWS por tenant (`saaswebstore/tenants/<tenant_id>`, clave `discogs_token`),
  caché Redis 5 min. Interruptor `ConfiguracioBotiga.discogs_habilitat` (feature `discogs_sync`).

### 1.2 UI
- `admin/catalogo`: stats de sync, botón de sync masivo de datos (`/images/start`, hilo en segundo
  plano), push/quitar listing por item, enrich por release. Todo es "actualizar datos de disco",
  salvo push/quitar.
- `admin/vendes-web` (`page.jsx:188-211`): botón **"Sincronitzar amb Discogs"** = pull manual de
  pedidos (`POST /admin/discogs/sync/orders`). Solo muestra "noves/actualitzades"; los
  `sense_match` y errores no se ven.
- `admin/configuracio`: interruptor y token.

### 1.3 Qué se refleja hoy en Discogs

| Acción en la app | Efecto en Discogs |
|---|---|
| Alta `segona_ma` con `discogs_release_id` | Crea listing, guarda `codi_discogs` |
| Alta `nou` | Crea 1 listing (Mint) para toda la línea |
| Alta sin `discogs_release_id` | Nada |
| Venta web pagada | Borra listing (`nou`: re-publica si queda stock) |
| Pedido Discogs marcado `enviado` | Marca Shipped + tracking como mensaje |
| Borrar item / borrado masivo | Borra listing |
| Cancelar pedido pagado `nou` | Repone stock y re-publica |
| **Cambio de precio** | **No se propaga** |
| **Retirar item** | **No borra el listing** |
| **TPV de `segona_ma`** | **No borra el listing** (solo se sincroniza `nou`) |
| **Devolución `segona_ma` a disponible** | **No re-publica** |

### 1.4 Problemas detectados
1. **Event hooks dispersos:** cada flujo llama a Discogs por su cuenta; los que nadie cableó
   (precio, retirar, TPV `segona_ma`, devolución) quedan desfasados → riesgo de **doble venta**.
2. **Fallos invisibles:** todo es best-effort; solo una línea de log.
3. **`discogs_habilitat` no se respeta en todo:** alta/borrado/borrado masivo de items, cambio de
   estado de pedidos y `finalize_payment` usan `get_tenant_secrets(...).discogs_token` directo.
   Con token presente escriben en Discogs aunque el interruptor esté apagado.
4. **Pull de pedidos sin programar** (no hay cron en el EC2; Celery beat no lo incluye). Entre una
   venta en Discogs y el siguiente pull, el item sigue a la venta en la web.
5. **El pull recorre todas las páginas de órdenes** en cada ejecución (~1,1 s/página): no es apto
   para programarlo tal cual.
6. **Pedidos sin match** (listing que la app no conoce) solo se cuentan y se pierden en el log.
7. **Catálogo y canal mezclados** en rutas, botones y servicio.
8. **Regla "Discogs manda en precio"** del script de inventario contradice el objetivo.

### 1.5 Hallazgos en producción (nukaesaas, tenant `recordstore`, 2026-10-01)
- `discogs_habilitat = True` y hay token, pero autentica la cuenta **`paumarroyo`** con **0
  listings For Sale**: no es la cuenta de la tienda.
- Dry-run de `sync_discogs_inventory --tenant recordstore`: 0 crear, **2.778 retirar/descontar**.
  Ejecutarlo de verdad retiraría casi todo el catálogo. **No lanzar sin token correcto.**
- Catálogo web: `nou` disponible 2.731 líneas (2.584 uds, 2.431 con `codi_discogs`), `segona_ma`
  disponible 349 (347 con `codi_discogs`); 3.223 releases, 3.206 con `discogs_release_id`.
- Único pedido existente: 1 de origen `subscripcio`. Ninguno de origen Discogs.
- No hay crontab en el EC2.

---

## 2. Principios

1. La app manda en stock y precio. Discogs es un canal: **salida** (publicar) y **entrada**
   (pedidos). Nunca se modifica stock/precio de la app desde el inventario de Discogs.
2. **Reconciliación declarativa, no eventos:** cualquier cambio marca el item como "sucio"; un
   único reconciliador calcula el estado deseado y lo aplica. Se cierran las lagunas por
   construcción.
3. **Todo fallo es visible** (estado y error por item), nunca solo en el log.
4. **Un único punto** decide si se escribe en Discogs (interruptor + token + modo solo lectura).
5. Operaciones masivas: siempre con vista previa/dry-run y como job con progreso (límite ~55/min).

---

## 3. Separar catálogo y canal

| | Proveedor de catálogo | Canal de venta |
|---|---|---|
| Nivel | Release | Item |
| Dirección | Solo lectura | Lectura y escritura |
| Qué hace | Buscar, enrich (carátula, tracklist, géneros, EAN, formato), imágenes | Publicar/actualizar/retirar listings, pull de pedidos, tracking |
| Rutas | `/admin/catalog-provider/*` | `/admin/channels/discogs/*` |
| UI | Botón "Enriquir dades" en `admin/catalogo` | Herramienta `/admin/canals/discogs` |
| Servicio | `services/discogs.py` + `services/catalog_enrich.py` | `services/channels/discogs.py` |

Comparten solo `release.discogs_release_id` (clave para enriquecer y para saber qué publicar).
`CATALOG_PROVIDERS` (`verticals_registry.py`) sigue siendo el punto de extensión del catálogo; se
añade un registro análogo de canales (`SALES_CHANNELS`).

---

## 4. Modelo de datos

Nueva tabla `channel_listings` (TenantScoped):

| Campo | Notas |
|---|---|
| `id`, `tenant_id` | |
| `item_id` FK `items` | un listing activo por (item, canal) |
| `channel` | `discogs` (extensible) |
| `external_id` | listing id de Discogs (hoy `codi_discogs`) |
| `status` | `pendent`, `publicat`, `error`, `retirat` |
| `published_price`, `published_condition`, `published_sleeve` | último estado enviado |
| `desired_hash` | hash del estado deseado; si cambia, el item está "sucio" |
| `last_synced_at`, `last_error`, `attempts` | |

- UNIQUE parcial `(tenant_id, channel, external_id)` y `(tenant_id, channel, item_id)` activos.
- Migración: copiar `record_stock_details.codi_discogs` → `channel_listings` (status `publicat`).
  Mantener `codi_discogs` en lectura hasta migrar todos los call sites (property compatible),
  después retirarlo.
- Tabla `channel_sync_runs` (o similar): historial de ejecuciones (tipo, inicio, fin, resumen,
  errores) para la pestaña "Comandes"/auditoría.
- Cursor de pull de pedidos (último `created` procesado) en config del canal.
- Ajustes del canal por tenant: `recargo_pct`, `publicacion_auto`, `modo_solo_lectura`,
  `cuenta_verificada` (username de `/oauth/identity`).

---

## 5. Reconciliador (salida)

`reconcile_item(item, channel)`:
1. **Estado deseado:** se publica si `item` está disponible (`nou`: `quantity - reserved > 0`),
   el canal está activo, el release tiene `discogs_release_id`, y `publicacion_auto` o el item fue
   aprobado manualmente. Precio = `item.price` (+ recargo). Condición mapeada (`nou` → Mint).
2. **Diff** contra `channel_listings`: crear, actualizar precio/condición, retirar o nada.
3. **Aplicar** con el cliente (throttle, reintentos con backoff, 4xx → `error` sin reintento
   infinito). Guardar resultado en `channel_listings`.

Disparo:
- Cualquier cambio de `quantity`, `price`, `status`, `condition` o del release marca el item
  "sucio" (hook único en un servicio de stock, no en cada router) y encola `reconcile_item`.
- Tarea Celery periódica: reintenta `error`/`pendent` y recorre items sucios.
- Recuperación: barrido completo diario de solo comparación (genera discrepancias, §7).

Esto sustituye a `sync_stock_listing`, `push_item_to_discogs`/`remove_item_from_discogs` directos
y los botones por item, que pasan a ser "forzar reconciliación de este item".

`nou` (stock agregado): se mantiene **"listing virtual de 1"** (Discogs no tiene cantidad por
listing). Ver decisión §9.3.

---

## 6. Entradas: pedidos

- **Pull programado** (Celery beat, por tenant con canal activo, cada 5–10 min).
- **Incremental:** pide solo órdenes con `created` posterior al cursor (y las abiertas), no todo
  el histórico. Evita saturar el límite de la API.
- Idempotente por `discogs_order_id` (ya lo es). Nunca pisa estados locales terminales.
- **Conflictos** (orden de un item ya vendido/retirado en la app, o `sense_match`): se registran
  como discrepancia accionable, no solo en el log.
- Al vender en Discogs: item pasa a `vendido` (`segona_ma`) o descuenta 1 y reconcilia (`nou`),
  igual que hoy, pero vía el reconciliador.
- Shipped + tracking hacia Discogs al marcar `enviado`, igual que hoy, con resultado visible.
- El botón de **Vendes web** se mantiene como "forzar ahora", apuntando al mismo servicio y
  mostrando el resultado completo: creadas, actualizadas, **sin match, errores**.
- Riesgo residual de doble venta (la ventana entre venta en Discogs y pull): se reduce con
  intervalo corto y reserva atómica ya existente; documentar que Discogs no ofrece webhook de
  pedidos en el código actual.

---

## 7. Herramienta en la app: `/admin/canals/discogs`

Pestañas:
- **Resum:** publicados, pendientes, con error, discrepancias; última sync de pedidos; cuenta
  conectada.
- **Pendents:** items por publicar/actualizar/retirar; selección masiva; **vista previa** antes de
  ejecutar; job con barra de progreso (3.000 items ≈ 55 min a 1,1 s/llamada).
- **Discrepàncies** (auditoría de solo lectura contra el inventario de Discogs): precio distinto,
  listing huérfano en Discogs (no está en la app), item vendido/retirado aún publicado, items
  disponibles sin listing y sin `discogs_release_id` (necesitan vincular release). Acciones por
  fila: adoptar, retirar de Discogs, forzar actualización.
- **Comandes:** estado del último pull, historial de ejecuciones, pedidos sin match y conflictos.
- **Configuració:** token con comprobación de cuenta al guardar (`/oauth/identity`, mostrar
  username y exigir confirmación), recargo, publicación automática/manual, modo solo lectura.

En `admin/catalogo`: el botón de sync masivo pasa a "Enriquir dades" (proveedor de catálogo); los
push/quitar por item se sustituyen por el estado del canal (publicado/pendiente/error) con enlace
a la herramienta.

---

## 8. Primera ejecución: Discogs manda (carga única), después manda la app

Decisión (2026-10-01): lo que hay hoy en Discogs es la verdad de partida. La primera sincronización
es una carga única **Discogs → app**; a partir de ahí la app es la fuente de verdad y Discogs es solo
un canal (§2). Es el comportamiento que ya tiene `scripts/sync_discogs_inventory.py`:

| Situación | Primera ejecución |
|---|---|
| Listing en Discogs que no está en la app | Se crea el item, con el precio de Discogs |
| Listing en ambos | El precio de Discogs sustituye al de la app |
| Item de la app con `codi_discogs` que ya no está en Discogs | Se retira (`nou`: se descuenta 1) |
| Resto | Sin cambios |

Requisitos antes de ejecutarla de verdad:
1. **Token de la cuenta de la tienda**, verificado con `/admin/secrets/discogs-account` (fase 0).
   Con el token equivocado de hoy retiraría ~2.778 items (Discogs devuelve 0 listings).
2. **Informe por item en el dry-run** (CSV: item, acción, motivo, precio actual vs Discogs). Hoy solo
   imprime totales. Se revisa antes de escribir nada.
3. **Freno de seguridad:** el script aborta si Discogs devuelve 0 listings o si retiraría más de un
   porcentaje del catálogo (propuesta 20 %), salvo `--force`.
4. **Marca de "adopción hecha" por tenant:** tras la ejecución real queda registrada y el modo
   "Discogs manda" no se puede relanzar por error. Desde ese momento manda la app.

### Migración por pasos: modo "solo lectura" (implementado)

Tokens: el secret del tenant (`saaswebstore/tenants/<tenant_id>`) lleva `discogs_token_prod` (compte
venedor real) y `discogs_token_dev` (proves); `discogs_token` queda como respaldo antiguo. Se elige con
`DISCOGS_TOKEN_ENV` (`prod` por defecto; el compose local fija `dev`). Resolución en
`services/discogs_sync.py::resolve_discogs_token`.

Interruptor por tenant `discogs_solo_lectura` (Configuració, debajo del de Discogs):
- **Activo:** `get_discogs_token_if_enabled` devuelve un `ReadOnlyToken` (`services/discogs.py`); su
  cliente HTTP rechaza todo lo que no sea GET/HEAD (un único punto de bloqueo) y las funciones de
  escritura (publicar, borrar listing, marcar Shipped) son no-op. Los endpoints manuales de publicar/
  quitar listing devuelven 409. Se puede BAJAR: búsqueda, enrich, pull de pedidos, `sync_discogs_inventory`.
- **Efecto a tener en cuenta:** los cambios locales (vender, borrar, retirar) NO se propagan a Discogs
  mientras esté activo; la adopción Discogs→app los reconcilia después.
- **Seguridad automática:** al guardar por primera vez `discogs_token_prod`, si la adopción no está
  hecha y nadie ha decidido el modo antes, el tenant pasa solo a solo lectura.
- **Paso final:** con la adopción hecha, el admin lo desactiva y pasa a lectura y escritura.

Orden: desplegar fase 0 → introducir token prod (arranca en solo lectura) y verificar cuenta → backup →
dry-run con CSV y freno → revisión →
ejecución real → marcar adopción hecha → desactivar solo lectura → fases 1–4 (reconciliador, herramienta, pedidos).

Tras la adopción, `channel_listings` se puebla a partir de los `codi_discogs` ya reconciliados, y la
auditoría de discrepancias (§7) pasa a ser de solo lectura: la app nunca vuelve a pisar precios ni
stock desde Discogs.

Nota: la simulación de "qué haría el reconciliador" calculada solo con datos de la app (97 a
publicar, 44 a retirar, 2.778 ya publicados) **no** es la referencia de la primera ejecución: asume
que la app tiene razón y no se ha contrastado con Discogs.

---

## 9. Decisiones abiertas

1. **Recargo por canal.** Discogs cobra comisión. ¿Mismo precio que la web o `% recargo`?
   Propuesta: campo `recargo_pct` por tenant (por defecto 0).
2. **Publicación automática vs manual.** Propuesta: manual con revisión al principio
   (`publicacion_auto = false`), automática cuando haya confianza.
3. **`nou` con varias unidades.** Propuesta: mantener "listing virtual de 1". Alternativa: hasta
   N listings por línea (más complejidad en reconciliación y en pedidos).
4. **Items sin `discogs_release_id`.** Propuesta: cola "pendiente de vincular" en la herramienta
   (los 17 releases y los items sin vincular no se publican hasta tener release).
5. **Hilos de segundo plano.** El sync masivo actual usa `threading.Thread` dentro del proceso
   API. Propuesta: pasarlo todo a Celery (ya hay worker/beat/redis en nukaesaas).

---

## 10. Fases

0. **Seguridad (urgente, sin dependencias):**
   - Retirar/sustituir el token de `paumarroyo` en `recordstore` y verificar con la cuenta real.
   - Validar el token al guardar (`/oauth/identity`) y mostrar la cuenta.
   - Punto único `get_discogs_token_if_enabled` en TODOS los call sites (alta/borrado/bulk de
     items, cambio de estado de pedidos, `finalize_payment`, rutas admin).
   - `USER_AGENT` real.
1. **Modelo y reconciliador:** migración `channel_listings` + copia de `codi_discogs`; servicio
   `channels/discogs`; hook único de "sucio"; tarea Celery; modo solo lectura.
2. **Adopción y discrepancias** (solo lectura): job de adopción, auditoría, informe.
3. **Herramienta UI** `/admin/canals/discogs` (Resum, Pendents, Discrepàncies, Configuració).
4. **Pedidos programados:** pull incremental en Celery beat, pestaña Comandes, conflictos
   visibles, botón de Vendes web apuntando al nuevo servicio.
5. **Separar el catálogo:** rutas `/admin/catalog-provider/*`, botón "Enriquir dades", retirar
   push/quitar por item del catálogo.
6. **Limpieza:** eliminar `sync_stock_listing`, endpoints antiguos y `codi_discogs` legacy;
   revisar `scripts/run_discogs_sync.sh` (recordshop) y documentar.

## 11. Riesgos y notas
- Throttle: 3.000 operaciones ≈ 55 min; las cargas iniciales son jobs largos con reanudación.
- La migración de `codi_discogs` toca ~2.800 filas en producción: probar en dev y revisar el
  archivo de Alembic antes de aplicar.
- Tests: reconciliador con cliente de Discogs falso; `pytest` debe seguir en verde (SQLite);
  cubrir TPV `segona_ma`, retirar, devolución, cambio de precio y conflicto de pedido.
- No lanzar `sync_discogs_inventory` sin `--dry-run` hasta que el token sea el de la tienda.
