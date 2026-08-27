> **Actualización:** la propuesta de idioma canónico de este documento (castellano) queda **superada** por `docs/ARQUITECTURA_CORE_VERTICAL.md`, que adopta **inglés** como canónico en DB/API y enmarca el problema como separación Core/Vertical (el proyecto es una plataforma multi-vertical, no un solo negocio con subdominios). Lee ese documento primero. Este se mantiene como inventario de detalle de las inconsistencias encontradas en el Core (cantidad/precio/estado/fecha/etc.), útil para la Fase 4 de aquel plan, pero con los nombres canónicos traducidos a inglés en vez de castellano.

# Nomenclatura — glosario y convención (propuesta)

Este documento existe para resolver un problema real detectado en el proyecto: el mismo concepto de negocio se nombra de formas distintas según la tabla, el schema, el endpoint o el componente donde aparece (`cantidad`/`quantitat`, `precio`/`preu`, `status`/`estado`/`estat`, `fecha`/`data`, `telefono`/`telefon`, `direccion`/`adreça`, `proveedor`/`proveidor`, `notas`/`notes`...). Esto complica el mantenimiento y hace que cada subdominio nuevo "invente" su propia grafía.

**Estado de este documento: propuesta, no aplicada todavía.** Es la base para decidir contigo la convención y planificar el refactor por fases. No se ha tocado ningún modelo, schema, endpoint ni componente para generar esto.

---

## 1. Los tres niveles

- **Nivel 0 — Idioma de producto.** Catalán (principal) y castellano, para lo que ve el cliente final: textos de UI (i18n), contenido editorial (posts, páginas), y también los slugs de URL públicos (`/cataleg`, `/disc/[id]`, `/carret`, `/compte`). **Esto no cambia.** Es una decisión de producto, no de nomenclatura técnica, y hoy ya está bien resuelto vía `useTranslations` y rutas en catalán.
- **Nivel 1 — Vocabulario común.** Conceptos estructurales que se repiten en *todo* el dominio (hay una cantidad, un precio, un estado, una fecha, unas notas, un teléfono, una dirección, un proveedor...). Hoy cada subdominio los nombra en un idioma distinto. Deberían tener **un único nombre canónico**, igual en la tabla, en el schema Pydantic, en el parámetro de API y en la variable/prop del frontend.
- **Nivel 2 — Vocabulario específico.** Términos que solo existen en un subdominio (`tracklist`, `discogs_release_id`, `periodicitat_mesos`, `redsys_identifier`, `iva_pct`...). No hace falta generalizarlos, pero si el mismo concepto de Nivel 1 aparece camuflado con nombre propio dentro de un término "específico", hay que destaparlo (ver `estat_pagament` en Despesa, que en realidad es "estado" + "pago", no un concepto nuevo).

La regla práctica: **antes de nombrar un campo nuevo, comprobar si el concepto ya existe en el glosario de Nivel 1.** Si existe, usar ese nombre. Si no, es Nivel 2 y puede llevar el nombre que tenga más sentido en ese subdominio.

---

## 2. Glosario común (Nivel 1) — propuesta de término canónico

Idioma canónico propuesto para Nivel 1: **castellano**, porque es ya la grafía mayoritaria (catálogo, checkout, carrito, ERP de compras/ventas) y coincide con los ejemplos que el propio `CLAUDE.md` usa (`disponible`, `reservado`, `vendido`, `pendiente_pago`). El catalán queda para Nivel 0 (producto/UI), no para nombres de campo.

| Concepto | Término canónico | Variantes actuales a retirar | Dónde aparece hoy |
|---|---|---|---|
| Identificador | `id` | — | ya consistente en todo el proyecto |
| Creado en | `created_at` | — | ya consistente en todo el proyecto |
| Actualizado en | `updated_at` | — | ya consistente donde existe |
| Cantidad/unidades | `cantidad` | `quantitat` (Subscripcio, ConfiguracioSubscripcio, SubscripcioCatalogItemOut), i18n key `quantity` | subscripcions es catalán; el resto castellano |
| Precio | `precio` | `preu` (TramEnviament, Subscripcio.preu_periode, ConfiguracioSubscripcio.preu_per_disc) | comptabilitat/subscripcions catalán; catálogo/checkout/ERP castellano |
| Estado (máquina de estados) | `estado` | `status` (Item, Order — inglés), `estat` (Subscripcio, CobramentSubscripcio, Assignacio, NewsletterCampaign, NewsletterSend, MovimentBancari, Despesa.estat_pagament) | **la inconsistencia más extendida**: tres idiomas distintos para el mismo concepto |
| Notas / observaciones | `notas` | `notes` (Despesa, MovimentBancari.notes_conciliacio, PeriodeComptable) | comptabilitat en catalán/inglés, resto castellano |
| Fecha | `fecha` | `data` (CaixaDiaria, MovimentBancari.data_operacio/data_valor, Despesa.data_factura/venciment/pagament, PeriodeComptable.data_tancament) | comptabilitat/banc catalán, resto castellano |
| Teléfono | `telefono` | `telefon` (User, Proveedor, ConfiguracioBotiga) | el propio flujo de compra mezcla las dos: `User.telefon` pero `Address.telefono` |
| Dirección | `direccion` | `adreça`/`adreca` (ConfiguracioBotiga.adreca) | checkout/Address castellano; configuración de tienda catalán |
| Proveedor | `proveedor` / `proveedor_id` / `proveedor_nombre` | `proveidor` (Despesa.proveidor_id, Despesa.proveidor_nom, Proveedor.iban_proveidor) | la propia tabla `Proveedor` (castellano) tiene una columna en catalán |
| Idioma/lang | `idioma` | `lang` (Translation.lang) | único caso en inglés |
| Descripción/concepto de movimiento | `notas`/`descripcion` (según si es libre o corto) | `concepte` (Despesa, CajaMovimiento ya usa `concepto` — revisar) | mezcla puntual |

**Nota sobre `estado`:** unificar el *nombre del campo* no implica unificar los *valores del enum*. Cada tabla sigue teniendo su propio Enum con sus propios valores (`disponible/reservado/vendido/retirado` para Item, `pendiente_pago/pagado/...` para Order, `activa/pausada/cancel·lada` para Subscripcio). Lo único que cambia es que la columna se llamará `estado` en todas partes en vez de `status`/`estat` según la tabla.

---

## 3. Glosario específico por subdominio (Nivel 2)

No requieren unificación entre sí — son legítimamente distintos porque son conceptos distintos — pero cada subdominio debería ser **internamente coherente** en su propio idioma una vez fijado el Nivel 1:

- **Catálogo/Discogs**: `codi_discogs` es la única grafía catalana suelta entre `discogs_release_id`/`discogs_order_id`/`discogs_sale_id`/`discogs_buyer` (inglés/castellano). Candidato a renombrar a `codigo_discogs` o `discogs_id` por consistencia con el resto de `discogs_*`.
- **Checkout/pedidos**: castellano consistente, salvo `numero_seguiment` (catalán) dentro de una tabla `Order` por lo demás castellana → candidato a `numero_seguimiento`.
- **ERP/stock**: `Compra` (recepción real) vs `Comanda` (pedido a proveedor, sin equivalente castellano) — son conceptos distintos, está bien que tengan nombres distintos, pero conviene documentar explícitamente la diferencia (este glosario es un buen sitio).
- **Blog/CMS**: `Post.contenido` (castellano) vs `Pagina.contingut`/`Pagina.tipus` (catalán) — mismo subdominio, dos idiomas. Candidato a unificar en `contenido`/`tipo`.
- **Comptabilitat**: el subdominio más coherente internamente (`despeses`, `comptes`, `moviments`, `caixa`, `periodes`, `iva`, todo en catalán) — aquí la pregunta de fondo es si comptabilitat se mantiene como "isla" en catalán o se alinea también al castellano de Nivel 1. Ver decisión en la sección 7.
- **Subscripcions**: enteramente catalán (`estat`, `quantitat`, `periodicitat_mesos`, `preu_periode`) — mismo dilema que comptabilitat.

---

## 4. Las 4 capas donde se aplica el término canónico

Un término de Nivel 1 debe verse igual en:

1. **DB** (`models.py`, columna de la tabla)
2. **Schema Pydantic** (`schemas.py`, campo in/out)
3. **API** (query param / body / path param del router)
4. **Frontend** (prop de componente, clave de estado, clave del payload)

Hoy la capa 4 ya en su mayoría *hereda* literalmente los nombres del backend sin traducir (`web/app/lib/api.js` no tiene capa de mapeo) — lo cual es bueno, porque significa que unificar el Nivel 1 en el backend se propaga casi gratis al frontend. La única traducción activa hoy está en `cataleg/page.jsx`, que convierte params de URL en inglés (`format`, `genre`, `min`, `max`) a los nombres del backend (`formato`, `genero`, `precio_min`, `precio_max`) — esto es un caso legítimo de frontera pública en inglés (URL amigable) que puede mantenerse como excepción documentada, no como inconsistencia a corregir.

---

## 5. Duplicados de schema a resolver (limpieza estructural, no de idioma)

Detectados durante el inventario, no están relacionados con el idioma pero sí con falta de nomenclatura común de *schemas*:

- `AddressIn` está definido **dos veces** con forma distinta: `schemas.py` (sin `predeterminada`) y `me.py` (con `predeterminada`). Deberían fusionarse en uno.
- `MeOut` (schemas.py, minimal) vs `MeFullOut` (me.py, superset) — dos DTOs de usuario con nombres distintos y solape parcial.
- `EventOut` (schemas.py, público) vs `EventAdminOut` (admin.py) — mismo modelo `Event`, dos nombres para in/out según contexto público/admin, mientras que `EtiquetaOut`/`SeccioOut` sí se reutilizan igual en ambos contextos. Fijar un patrón único: o siempre se reutiliza el mismo `XOut`, o siempre se distingue `XOut`/`XAdminOut` — hoy es ad hoc.
- `me.py::OrderItemOut` no es un DTO del modelo `OrderItem` sino un objeto distinto (con `pendent_arribada` derivado) — nombre engañoso, confundible con el modelo real.

---

## 6. Paginación — patrón a unificar

| Patrón encontrado | Dónde |
|---|---|
| `page` + `page_size` | `GET /catalog`, `GET /posts` |
| `limit` + `offset` | `admin.py` (releases, aging items, discogs sync items) |
| `limit` solo (sin offset) | `admin_users.py` (`GET /admin/users`), `admin_subscripcions.py` |
| Sin paginación | la mayoría de `erp.py`, `comptabilitat.py`, `configuracio.py`, `admin_newsletter.py` |
| `order_by` con allowlist | solo `admin_users.py` |

Propuesta: `page`/`page_size` como estándar único para listados con paginación real (ya es el patrón público, el más visible), y decidir caso a caso si los listados admin sin paginación hoy (por volumen bajo: proveedores, configuración) realmente la necesitan o pueden quedar como "lista completa" a propósito.

---

## 7. Plan de refactor por fases (propuesta — no ejecutado)

Cada fase es un PR separado con su propia migración Alembic, para no mezclar riesgo. Orden de menor a mayor impacto:

**Fase 0 — Decisión de política.** Confirmar contigo: idioma canónico de Nivel 1 (castellano, según sección 2), si comptabilitat/subscripcions se alinean también o quedan como excepción documentada, y si `estado` sustituye a `status`/`estat` en todos los sitios (incluido `Item.status`/`Order.status`, que es el cambio de más impacto porque toca `reservations.py` — "la pieza más delicada" del proyecto según `CLAUDE.md` — y todo el frontend que compara literalmente contra `'reservado'`/`'disponible'`).

**Fase 1 — Bajo riesgo, sin lógica de negocio de por medio.** Renombrar columnas de texto libre y fechas que no participan en comparaciones de código: `Despesa.notes`→`notas`, `Despesa.proveidor_id/nom`→`proveedor_id/nombre`, `MovimentBancari.notes_conciliacio`→`notas_conciliacion`, `CaixaDiaria.data`→`fecha`, `Despesa.data_factura/venciment/pagament`→`fecha_*`, `ConfiguracioBotiga.telefon/adreca`→`telefono/direccion`, `Translation.lang`→`idioma`, `Order.numero_seguiment`→`numero_seguimiento`, `Post.tipus`/`Pagina.contingut`→castellano.

**Fase 2 — Cantidad y precio en subscripcions.** `Subscripcio.quantitat`→`cantidad`, `preu_periode`→`precio_periodo`, `ConfiguracioSubscripcio.preu_per_disc`→`precio_por_disco`, `quantitats_disponibles`→`cantidades_disponibles`. Impacto medio: toca `admin_subscripcions.py`, `subscripcions_public.py`, `me.py` y las páginas de frontend de subscripció.

**Fase 3 — `estado` unificado.** La de más impacto: `Item.status`→`estado`, `Order.status`→`estado`, `Subscripcio.estat`→`estado`, `CobramentSubscripcio.estat`→`estado`, `Assignacio.estat`→`estado`, `NewsletterCampaign/Send.estat`→`estado`, `Despesa.estat_pagament`→`estado_pago`, `MovimentBancari.estat`→`estado_conciliacion`. Requiere tocar `reservations.py`, todos los routers que filtran por estado, y el frontend (`CarretClient.jsx` compara literalmente contra strings). Se recomienda hacerla sola, con `pytest` en verde antes y después, y probar el flujo de checkout manualmente (es el camino más delicado del negocio).

**Fase 4 — Paginación.** Unificar a `page`/`page_size` donde tenga sentido.

**Fase 5 — Duplicados de schema.** Fusionar `AddressIn`, decidir `MeOut`/`MeFullOut`, fijar el patrón `XOut`/`XAdminOut`.

**Fase 6 — Frontend.** Una vez el backend esté unificado, revisar que las props/variables del frontend usen el mismo nombre canónico (mayormente ya lo hacen porque no hay capa de mapeo).

---

## 8. Decisiones pendientes de tu confirmación

1. ¿Castellano como idioma canónico de Nivel 1 (recomendado, sección 2), o prefieres otra base?
2. ¿Comptabilitat y subscripcions se alinean también al castellano, o se documentan como excepción intencional en catalán?
3. ¿Se aborda la Fase 3 (`status`/`estat` → `estado`) a pesar de tocar `reservations.py` y el checkout, o se deja fuera de alcance por ahora?
4. ¿Orden de fases tal cual está propuesto (menor a mayor riesgo), o prioridad distinta?

En cuanto confirmes esto puedo generar la Fase 1 (la de menor riesgo) como primer PR concreto: cambios en `models.py` + migración Alembic + `schemas.py` + routers + frontend afectado, con `pytest` en verde.
