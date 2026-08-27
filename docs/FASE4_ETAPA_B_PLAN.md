# Fase 4 Etapa B — plan de ejecución para el resto de dominios

Documento de trabajo (no arquitectura) para retomar en otra sesión y ejecutar
**todo lo que queda de un tirón**, dominio a dominio, sin pausar a confirmar
entre uno y el siguiente salvo que algo salga genuinamente mal. Está pensado
para que una sesión nueva, sin memoria de esta conversación, pueda arrancar
directamente leyendo este archivo.

Contexto general (arquitectura, fases previas) en
`docs/ARQUITECTURA_CORE_VERTICAL.md` — leerlo primero si hace falta
refrescar el porqué de todo esto. Este documento es solo el "cómo" y el
"qué queda" de la Etapa B.

## Qué es la Etapa B

La Etapa A (completa, §16 del doc de arquitectura) ya renombró **todas** las
columnas Core en Postgres a inglés vía `mapped_column("nombre_ingles", ...)`,
sin tocar el atributo Python. La Etapa B es quitar ese passthrough: renombrar
el **atributo Python** del modelo para que coincida con el nombre de columna
que ya existe, y propagar el cambio a `schemas.py`, routers, servicios,
scripts y **cada página de frontend que consuma esos campos por su nombre
JSON**. La base de datos no se toca en absoluto en esta etapa — cero
migraciones Alembic.

## Ya hecho (no re-tocar)

- **CMS / newsletter / configuración de precios**: `Pagina`, `Post`, `Event`,
  `NewsletterCampaign`, `NewsletterSend`, `TipusIva`, `MargeConfig`,
  `TramEnviament`.
- **ERP / Comptabilitat** (dos sesiones): `Proveedor`, `Compra`, `Comanda`,
  `ComandaLinea`, `SolicitudCompra`, `SolicitudCompraLinea`,
  `HistorialCompra`, `Despesa`, `CompteBancari`, `MovimentBancari`,
  `PeriodeComptable`, `CaixaDiaria`, `ConfiguracioBotiga`.

Verificar con este grep antes de empezar cualquier dominio de la lista de
abajo — si sale vacío para una clase, es que ya está hecha y no toca:

```bash
cd api/app && python3 - << 'EOF'
import re
content = open("models.py").read()
pattern = re.compile(r'(\w+)(?:\s*:\s*Mapped\[[^\]]+\])?\s*=\s*mapped_column\(([^)]*(?:\([^)]*\)[^)]*)*)\)', re.S)
class_pattern = re.compile(r'^class (\w+)\(', re.M)
classes = [(m.start(), m.group(1)) for m in class_pattern.finditer(content)]
def class_for_pos(pos):
    best = None
    for start, name in classes:
        if start <= pos: best = name
        else: break
    return best
for m in pattern.finditer(content):
    attr, args = m.group(1), m.group(2)
    first = args.strip().split(",")[0].strip()
    if first.startswith(('"', "'")) and first.strip('"\'') != attr:
        print(f"{class_for_pos(m.start())}.{attr} -> column {first.strip(chr(39)+chr(34))!r}")
EOF
```

Cualquier línea que imprima ese script es un campo pendiente de Etapa B.

## Restricciones que no cambian (de CLAUDE.md y de lo aprendido en ERP)

- **Nunca** renombrar nombres de tabla (`__tablename__`) ni nombres de clase
  Python (`Etiqueta` sigue siendo `Etiqueta`, no `Tag`). Solo atributos y
  campos de schema.
- **Nunca** renombrar valores/nombres de miembros de Enum
  (`MetodoPago.bono_cultural`, `EstadoComanda.esborrany`, `ItemStatus.disponible`...).
  Solo el nombre del atributo que apunta al enum (`condicion`→`condition`,
  la clase `CondicionItem` y sus miembros `segona_ma`/`nou` no se tocan).
- Antes de tocar la BD real de dev (rebuild/restart de contenedores, cambios
  visibles en `http://localhost:8080`), confirmar con el usuario — sigue
  siendo un entorno con tenants reales, no solo fixtures de test.

## Metodología (la que funcionó en los 13 sub-lotes de ERP, replicar igual)

Por cada dominio de la lista de abajo, en este orden:

1. `models.py`: quitar el `mapped_column("col_name", ...)` y renombrar el
   atributo directamente a `col_name`. Revisar `__table_args__` de esa clase
   por si hay `UniqueConstraint`/`CheckConstraint`/`Index` con el nombre de
   columna **como string** (no se actualizan solos, hay que tocarlos a mano
   — esto ya causó un fallo real detectado por pytest en Etapa A, ver §16).
2. `schemas.py`: renombrar los campos de los `BaseModel` que envuelven ese
   modelo (ver mapeo de clases de schema por dominio más abajo).
3. Grep de todo `app/` (routers + services + scripts) buscando el nombre
   viejo del atributo, arreglar cada uso. Cuidado con colisiones: nombres
   como `notas`, `fecha`, `cantidad`, `tipo`, `estado` se repiten en modelos
   no relacionados — nunca hacer `replace_all` a ciegas sin comprobar el
   contexto de cada aparición.
4. `pytest` (usa `api/test.db`, SQLite en archivo, no en memoria — **borrar
   `test.db` a mano si algún test falla en el setup de un fixture antes del
   `yield`**, porque si no el teardown no corre y el archivo queda
   envenenado para toda ejecución siguiente; ya pasó una vez con
   `conftest.py` sin actualizar tras un rename de `ConfiguracioBotiga`).
   Grep `conftest.py` explícitamente por el nombre del modelo que se está
   tocando — ahí también hay constructores con kwargs viejos.
5. Arreglar los tests que rompan, con el mismo cuidado de scope del punto 3.
   Re-correr hasta 383/383 (o el número que toque en ese momento) en verde.
6. Grep del frontend (`web/app`, `web/components`) por los mismos nombres,
   arreglar cada consumidor. Distinguir variables/estado local de React
   (pueden quedarse en catalán/castellano como bookkeeping interno) de los
   nombres de campo que realmente viajan en el JSON de la API (esos sí hay
   que cambiarlos). Ojo especial a páginas **customer-facing**, no solo admin
   (home, footer, disc detail, carret, checkout, compte) — tienen igual o más
   blast radius que el admin y es fácil olvidarse de ellas.
7. `docker compose build api web && docker compose up -d --no-deps api web`,
   confirmar antes con el usuario si no se ha hecho ya en esta sesión.
8. QA manual en `http://localhost:8080` con Chrome DevTools MCP: flujo real
   de crear/editar/alternar con datos de prueba, no solo mirar que la
   pantalla cargue. Ver notas de QA por dominio más abajo.
9. Limpiar los datos de prueba creados en QA vía SQL directo, acotado con
   precisión (por id/valor único de test), verificado con `SELECT COUNT`
   antes/después para no tocar datos reales de otros tenants.
10. `pytest` final en verde antes de pasar al siguiente dominio.

### Lecciones ya aprendidas (para no repetir)

- El shadowing `atributo_llamado_date: Mapped[date]` (con `date` importado de
  `datetime`) funciona bien, ya probado en varias tablas — no da vueltas con
  esto si aparece.
- Los schemas de informes/agregados que quedan **aguas abajo** de un modelo
  renombrado pero no son un envoltorio 1:1 (p. ej. algo que hace un JOIN y
  expone un campo con otro nombre) se pueden dejar sin tocar a propósito si
  ya se decidió así en un dominio anterior — pero en los dominios nuevos de
  esta lista, decidir caso a caso, no asumir.
- Las claves de traducción en `api/scripts/seed_translations.py` que se
  construyen dinámicamente como `` t(`namespace.algo.${campo}`, fallback) ``
  necesitan que la clave seed cambie también si `campo` cambia de nombre, o
  la traducción cae en el fallback hardcodeado en inglés silenciosamente.

## ⚠️ Landmine a resolver ANTES de tocar `Address` u `Order`

`Order.direccion_envio` (columna ya renombrada a `shipping_address` en
Etapa A) es un **snapshot JSON** copiado en el momento de la compra
(CLAUDE.md, decisión de diseño #3: "los pedidos históricos nunca cambian").
Los pedidos ya existentes en la BD real de dev (y en producción cuando la
haya) tienen ese JSON con las claves **en catalán/castellano**
(`nombre_destinatario`, `linea1`, `ciudad`, `cp`...) porque así las escribió
`services/orders.py` en su momento — renombrar `Address` no reescribe el
JSON ya guardado en pedidos antiguos.

Antes de tocar el dominio "Usuarios y direcciones" ni "Carrito y checkout",
decidir con el usuario:

- ¿El código que lee `order.shipping_address` para imprimir la etiqueta de
  envío / mostrar el pedido debe soportar **ambos** formatos de clave (viejo
  y nuevo) según la fecha del pedido?, o
- ¿Se deja el *shape* del JSON snapshot en catalán/castellano para siempre
  (solo se renombra la tabla `Address` y el modelo Python, no lo que
  `orders.py` escribe dentro del JSON al hacer checkout)?

Esto no tiene una respuesta "correcta" obvia — es una decisión de producto,
no solo de código. No arrancar ese dominio sin haberla tomado.

---

## Dominios pendientes, en orden sugerido (de menor a mayor riesgo)

Orden sugerido: primero los aislados y de bajo riesgo, dejando para el
final el catálogo/stock (la reserva atómica) y checkout (flujo de compra
real + el landmine del JSON de arriba). El usuario puede reordenar.

### 1. Devoluciones — `DevolucionVenta`, `DevolucionCompra`

Aisladas, sin flujo de checkout ni reserva de stock de por medio.

| Clase | Atributo viejo → nuevo |
|---|---|
| `DevolucionVenta` | `cantidad`→`quantity`, `motivo`→`reason`, `destino_item`→`item_destination`, `fecha`→`date`, `notas`→`notes` |
| `DevolucionCompra` | `cantidad`→`quantity`, `motivo`→`reason`, `fecha`→`date`, `notas`→`notes` |

Schemas: `DevolucionVentaIn/Out`, `DevolucionCompraIn/Out`.

Frontend: no hay página dedicada — están embebidas en el flujo de
`admin/vendes-web` (devolución de venta web) y `admin/compras` (devolución a
proveedor). Localizar por grep de `devolucion` en `web/app/admin/`.

QA: crear una venta/compra de prueba, devolverla, confirmar que el stock del
`Item` involucrado vuelve al estado esperado (`disponible` o `cantidad`
incrementada según `condicion`), limpiar después.

### 2. Peticiones de cliente — `PeticionCliente`

| Clase | Atributo viejo → nuevo |
|---|---|
| `PeticionCliente` | `canal`→`channel`, `artista_lliure`→`free_artist`, `titulo_lliure`→`free_title`, `notas_cliente`→`client_notes`, `estado`→`status`, `precio_estimado`→`estimated_price`, `metodo_entrega_triat`→`chosen_delivery_method`, `notas_admin`→`admin_notes` |

Schemas: `PeticionClienteAdminOut`, `PeticionCatalogarIn`, `PeticionPrecioIn`,
`PeticionVincularIn`, `PeticionVincularItemIn`, `PeticionTiendaIn`,
`ReservaRecollidaOut`.

Frontend: `web/app/admin/peticions/page.jsx`,
`web/app/[locale]/compte/peticions/page.jsx`, más el formulario público de
"no lo encuentras, pídelo" (buscar en `web/app/[locale]/disc/[id]/page.jsx`
o `cataleg`).

QA: crear una petición de prueba desde el store público (mismo patrón que
Fase 6 usó para probar el badge de estado), pasarla por catalogar →
resolver, verificar en `compte/peticions` como cliente. Cancelar/limpiar al
final (mismo patrón que Fase 6 QA de `peticions`).

### 3. TPV / mostrador — `VentaExterna`, `CajaSession`, `CajaMovimiento`

| Clase | Atributo viejo → nuevo |
|---|---|
| `VentaExterna` | `condicion`→`condition`, `cantidad`→`quantity`, `descripcion`→`description`, `canal`→`channel`, `metodo_pago`→`payment_method`, `precio_venta`→`sale_price`, `fecha`→`date`, `nombre_cliente`→`client_name`, `notas`→`notes`, `cobrat_at`→`paid_at`, `iva_pct`→`vat_pct`, `iva_import`→`vat_amount` |
| `CajaSession` | `fecha_apertura`→`opened_at`, `fondo_inicial`→`opening_float`, `fecha_cierre`→`closed_at`, `total_ventas_efectivo`→`total_cash_sales`, `total_entradas`→`total_cash_in`, `total_salidas`→`total_cash_out`, `conteo_real`→`actual_count`, `notas`→`notes` |
| `CajaMovimiento` | `tipo`→`type`, `concepto`→`concept`, `importe`→`amount`, `fecha`→`date` |

Ojo: `CajaSession`/`CajaMovimiento` (caja física del mostrador, abrir/cerrar
turno) son tablas **distintas** de `CaixaDiaria` (ya migrada, es la
cuadrícula mensual de conciliación) — no confundir ni fusionar.

Schemas: `VentaExternaIn`, `VentaExternaLoteLineaIn`, `VentaExternaLoteIn`,
`VincularUsuariTicketIn`, `VentaExternaOut`, `CajaSessionIn`,
`CajaCierreIn`, `CajaSessionOut`, `CajaMovimientoIn`, `CajaMovimientoOut`.

Frontend: `web/app/admin/tpv/page.jsx` (grande — abrir/cerrar sesión de
caja, registrar ventas, movimientos de caja, recibo imprimible en catalán
fijo a propósito, no tocar eso).

QA: abrir sesión de caja de prueba, registrar una venta y un movimiento de
caja, cerrar sesión con conteo real, verificar el cuadre. Limpiar
(`caja_sessions`/`caja_movimientos`/`ventas_externas` de test) al final.

### 4. Usuarios y direcciones — `User`, `Address`

⚠️ Ver el landmine del JSON snapshot de arriba antes de arrancar este.

| Clase | Atributo viejo → nuevo |
|---|---|
| `User` | `nombre`→`name`, `telefon`→`phone`, `rol`→`role`, `activo`→`active`, `idioma`→`language`, `notas_internes`→`internal_notes` |
| `Address` | `nombre_destinatario`→`recipient_name`, `linea1`→`address_line1`, `linea2`→`address_line2`, `ciudad`→`city`, `cp`→`postal_code`, `provincia`→`province`, `pais`→`country`, `telefono`→`phone`, `predeterminada`→`is_default` |

Schemas: `MeOut`, `AddressIn` (revisar si falta un `AddressOut` explícito o
si se sirve inline).

Frontend: `web/app/admin/usuaris/page.jsx`, `web/app/[locale]/compte/page.jsx`,
`web/app/[locale]/login/page.jsx`, formulario de dirección en
`web/app/[locale]/checkout/page.jsx`.

Riesgo: dominio de auth — sensible, pero sin lógica de stock ni pagos de por
medio (aparte del landmine del JSON, que es el punto real de cuidado).

QA: editar el propio usuario admin de prueba (nombre/teléfono/idioma), crear
una dirección nueva desde `compte`, verificar que aparece correctamente en
el selector de checkout.

### 5. Catálogo — `Etiqueta`, `Seccio`, `Release`, `ReleaseImage`, `Item`, `StockHold`

⚠️ La más grande y la de más riesgo real. Incluye `Item`, la tabla que
CLAUDE.md marca explícitamente como "la pieza más delicada" del sistema
(reserva atómica vía `UPDATE ... WHERE status='disponible'`/`cantidad`
condicionado en `services/reservations.py`, nunca `SELECT`+`UPDATE`).
Dejarla para el final a propósito, con margen extra de QA.

| Clase | Atributo viejo → nuevo |
|---|---|
| `Etiqueta` | `nom_ca`→`name_ca`, `nom_es`→`name_es`, `activa`→`active`, `posicio`→`position` |
| `Seccio` | `nom_ca`→`name_ca`, `nom_es`→`name_es`, `activa`→`active`, `posicio`→`position` |
| `Release` | `titulo`→`title`, `descripcion`→`description`, `imagen_url`→`image_url`, `pes_g`→`weight_g`, `properament`→`coming_soon`, `data_disponibilitat`→`available_at` |
| `ReleaseImage` | `posicio`→`position`, `tipus`→`type`, `font`→`source` |
| `Item` | `precio`→`price`, `condicion`→`condition`, `cantidad`→`quantity`, `cantidad_reservada`→`reserved_quantity`, `fecha_entrada`→`entry_date`, `subscripcio_pool`→`subscription_pool`, `coste_adquisicion`→`acquisition_cost` |
| `StockHold` | `cantidad`→`quantity` |

Nota aparte, **fuera de esta lista a propósito**: `Release.seccio_id` (FK a
`seccions.id`) nunca se renombró ni en Etapa A — decidir si entra en este
lote (renombrar a `section_id`, columna incluida, sería una mini-migración
Alembic) o se deja para otra pasada. Confirmar con el usuario, no asumir.

Schemas: `ItemOut`, `ItemIn`, `ItemUpdate`, `EtiquetaOut/In`, `SeccioOut/In`,
`ReleaseImageOut`, `ReleaseOut`, `ReleaseIn`, `CatalogPage`,
`CatalogAgingBucketOut`, `CatalogAgingItemOut`, `CatalogAgingItemsOut`,
`CatalogAgingOut`, `RefillSugerenciaOut`.

Frontend (customer-facing, alto blast radius): `web/app/[locale]/cataleg/page.jsx`
+ `CatalogFilters.jsx`, `web/app/[locale]/disc/[id]/page.jsx`,
`web/app/[locale]/carret/CarretClient.jsx`, `web/app/[locale]/checkout/page.jsx`,
`web/app/[locale]/page.jsx` (home, carrusel de novedades) — y también
`web/components/store/*` en general.

Frontend (admin): `web/app/admin/catalogo/page.jsx`, `web/app/admin/etiquetes/page.jsx`,
`web/app/admin/compras/page.jsx` (alta/recepción de items), `web/app/admin/subscripcions/page.jsx`
(`subscripcio_pool`).

QA: mínimo un ciclo completo — buscar en catálogo, ver ficha de disco,
añadir al carrito, entrar en checkout hasta la reserva (`/checkout/start`),
confirmar que `Item.reserved_quantity`/`StockHold` se mueven bien tanto para
`segona_ma` (copia única) como para `nou` (stock agregado), verificar alta
manual de un item nuevo desde el admin, y el flujo de club del disco si hay
tiempo. Revertir cualquier reserva/venta de prueba a mano (no dejar `Order`
huérfanos).

### 6. Carrito y checkout — `CartItem`, `Order`, `Payment`, `OrderItem`

⚠️ Ver el landmine del JSON snapshot de arriba. Dejar para el final junto
con Catálogo porque toca el flujo de compra real end-to-end.

| Clase | Atributo viejo → nuevo |
|---|---|
| `CartItem` | `cantidad`→`quantity` |
| `Order` | `email_contacto`→`contact_email`, `coste_envio`→`shipping_cost`, `metodo_envio`→`shipping_method`, `metodo_pago`→`payment_method`, `direccion_envio`→`shipping_address`, `notas`→`notes`, `idioma`→`language`, `cobrat_at`→`paid_at`, `numero_seguiment`→`tracking_number`, `transportista`→`carrier`, `avisada_recollida_at`→`pickup_notified_at`, `origen`→`origin` |
| `Payment` | `proveedor`→`provider`, `importe`→`amount`, `moneda`→`currency`, `estado`→`status` |
| `OrderItem` | `precio`→`price`, `condicion`→`condition`, `cantidad`→`quantity`, `iva_pct`→`vat_pct`, `iva_import`→`vat_amount` |

Nota: `Order.origen` apunta al enum `OrderOrigen` — el enum y sus miembros
(`web`/`discogs`/`subscripcio`...) no se tocan (Fase 5, aparcada). Solo el
atributo `origen`→`origin`.

Schemas: `CartAdd`, `CartItemOut`, `CartOut`, `CheckoutConfirm`, `OrderOut`,
`OrderStatusUpdate`, `OrderPendentTiendaItemOut`, `OrderPendentTiendaOut`,
`OrderMarcarPagadoTiendaIn`.

Frontend (customer-facing): `web/app/[locale]/carret/CarretClient.jsx`,
`web/app/[locale]/checkout/page.jsx`, `web/app/[locale]/compte/comandes/page.jsx`
+ `[id]/page.jsx`.

Frontend (admin): `web/app/admin/vendes-web/page.jsx` (incluye la etiqueta
de envío imprimible — en catalán fijo a propósito, no tocar), `web/app/admin/tpv/page.jsx`
(recibo, igual fijo en catalán).

QA: ciclo de compra completo real (añadir al carrito → checkout/start →
checkout/confirm) con un email de prueba, verificar el pedido en
`compte/comandes` como cliente y en `admin/vendes-web` como admin, marcar
como enviado y verificar `tracking_number`/`carrier`, cancelar y verificar
que el stock vuelve. Limpiar el `Order`/`Payment`/`OrderItem` de prueba
después.

---

## Cómo arrancar la próxima sesión

1. Leer este archivo entero.
2. Correr el grep de la sección "Ya hecho" para confirmar que el estado no
   ha cambiado desde que se escribió esto.
3. Preguntar al usuario UNA vez si quiere correr todos los dominios
   pendientes seguidos (como se hizo con ERP) o prefiere confirmar entre
   cada uno — y si el orden sugerido le vale o quiere reordenar.
4. Resolver el landmine de `direccion_envio`/`shipping_address` con el
   usuario antes de llegar al dominio 4 o 6 (no hace falta resolverlo si se
   empieza por Devoluciones/Peticiones/TPV).
5. Ejecutar dominio a dominio con la metodología de arriba, actualizando
   este archivo (tachar o mover a "ya hecho" cada dominio terminado) para
   que quede como registro vivo igual que `ARQUITECTURA_CORE_VERTICAL.md`.
